#!/usr/bin/env python3
"""Unit tests for capture_write.py — run: python3 test_capture_write.py"""
import hashlib, json, os, subprocess, sys, tempfile, uuid
import capture_write as cw
import run_ledger as rl

P = F = 0
def check(name, cond):
    global P, F
    if cond: P += 1; print(f"  PASS  {name}")
    else:    F += 1; print(f"  FAIL  {name}")

CWD = __file__.rsplit("/", 1)[0]
RID = f"cwtest-{uuid.uuid4().hex[:8]}"
VAULT = tempfile.mkdtemp(prefix="cwtest-vault-")
os.makedirs(os.path.join(VAULT, "raw"))
os.makedirs(os.path.join(VAULT, "wiki"))

def run(verb, *args, stdin=""):
    return subprocess.run([sys.executable, "capture_write.py", verb, "--vault-root", VAULT] + list(args),
                          input=stdin, capture_output=True, text=True, cwd=CWD)

# realistic bodies for the quality gate (>= QUALITY_MIN_BYTES of prose)
PAD = "lorem ipsum dolor sit amet, consectetur adipiscing elit sed do eiusmod. " * 20
GOOD = "# One\n\nbody [[stray]]\n\n" + PAD
STUB = ("Title: X\n\nURL Source: https://x.test/gone\n\n"
        "Warning: Target URL returned error 404: Not Found\n\n" + PAD)
SHELL = "Title: Page Not Found\n\nURL Source: https://x.test/gone\n\n" + PAD
SOUP = "\n".join(f'<span class="ltx_p" id="s{i}">text {i}</span>' for i in range(150))
# A web-page capture carries capture_probe.py's result; these synthetic results stand in for its runs
# (the probe suite, test_capture_probe.py, exercises the real chain).
PROBE_DIRS = []
PLAIN_PAGE = "<!DOCTYPE html><html><body><article><h1>One</h1><p>" + PAD + "</p></article></body></html>"
VISA = "Student visa holders ineligible."
COLLAPSED_PAGE = ("<!DOCTYPE html><html><body><article><h1>Terms</h1><p>" + PAD + "</p><details><summary>Visa terms"
                  "</summary><p>" + VISA + "</p></details></article></body></html>")


import importlib.util as _ilu, datetime as _dt
cp = None   # the probe's own functions build the fixtures' results; on code without capture_probe.py the legs fail, never crash
if os.path.isfile(os.path.join(CWD, "capture_probe.py")):
    _spec = _ilu.spec_from_file_location("capture_probe_for_fixtures", os.path.join(CWD, "capture_probe.py"))
    cp = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(cp)


CHECK_KEYS = ("collapsed", "sets", "labels", "pairing", "links", "failures", "ambiguous")   # capture_probe.CHECK_KEYS


def probe_record(url, page_html, engine, route="NOT-ROUTED", status="pass", stage="done", reason="", sha=None,
                 capture=None, fetch=None):
    """A result.json in the shape capture_probe.py's run_capture writes: every field the record of a
    capture carries, each agreeing with the page, the converter run and the check (computed here by the
    probe's own functions, its findings and verdict included). route is what the record claims (W8 claims
    NOT-ROUTED for a page that routes). capture is the body the probe converted, written as capture.md. A
    failed probe (status fail) made no capture; failed at start or at its controls, it fetched nothing
    either. fetch overrides fields of the fetch record (a curl failure under a 200 header, say)."""
    d = tempfile.mkdtemp(prefix="cwtest-probe-")
    PROBE_DIRS.append(d)
    capture = GOOD if capture is None else capture
    for name, text in (("page.html", page_html), ("converted.html", page_html), ("capture.md", capture)):
        with open(os.path.join(d, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    if cp is None:
        return {"schema": "capture-probe-result/2", "status": status, "stage": stage, "reason": reason, "url": url}, d
    root = cp.parse_html(page_html)
    markers = dict(cp.find_markers(root))
    markers = markers if route == "ROUTE" else {}
    base = cp.document_base(url, root)
    report = cp.check_capture(page_html, base, capture)
    converted = os.path.join(d, "converted.html")
    converter = ([sys.executable, "-B", "-m", "markitdown", converted] if route == "ROUTE"
                 else ["defuddle", "parse", converted, "--markdown"])
    ctype = "text/html; charset=utf-8"
    result = {"schema": cp.RESULT_SCHEMA, "status": status, "stage": stage, "reason": reason, "url": url,
              "created": _dt.datetime.now().isoformat(timespec="seconds"), "probe_sha256": cp._self_sha(),
              "controls": cp.require_controls(),
              "fetch": {"curl_exit": 0, "curl_stderr": "", "http_code": 200, "content_type": ctype, "effective_url": url,
                        "redirects": 0, "redirect_url": ""},
              "html_file": "page.html", "html_sha256": sha or hashlib.sha256(page_html.encode("utf-8")).hexdigest(),
              "content_type": ctype, "effective_url": url, "base_url": base, "route": route, "markers": markers,
              "engine": engine, "converted_file": "converted.html", "converter": converter,
              "capture_file": "capture.md", "capture_sha256": hashlib.sha256(capture.encode("utf-8")).hexdigest(),
              "check": {k: report.get(k, []) for k in CHECK_KEYS}}
    result["check"]["verdict"] = "suspected loss" if report["failures"] else "no loss found"
    if route == "ROUTE":
        result["pairing"] = report["pairing"]
    if status == "fail":
        for k in ("converted_file", "converter", "capture_file", "capture_sha256", "check"):
            result.pop(k, None)
        if stage in ("start", "controls"):
            for k in ("fetch", "html_file", "html_sha256", "content_type", "effective_url", "base_url", "route", "markers",
                      "engine", "pairing"):
                result.pop(k, None)
    if fetch:
        result["fetch"].update(fetch)
    return result, d


def save_record(result, d):
    path = os.path.join(d, "result.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result, fh)
    return path


def probe_result(url, page_html, engine, route="NOT-ROUTED", status="pass", stage="done", reason="", sha=None,
                 capture=None, fetch=None):
    return save_record(*probe_record(url, page_html, engine, route, status, stage, reason, sha, capture, fetch))

print("== sanitise ==")
check("control bytes stripped",  cw.sanitise("a\x00b\x07c") == "abc")
check("newlines kept",           cw.sanitise("a\nb\tc") == "a\nb\tc")
check("wiki links defanged",     cw.sanitise("see [[page]]") == r"see \[\[page]]")
check("bareword link defanged",  cw.sanitise("[eq](x1)") == "eq (x1)")
check("real url link kept",      cw.sanitise("[a](https://x.test/p)") == "[a](https://x.test/p)")
check("anchor link kept",        cw.sanitise("[a](#sec)") == "[a](#sec)")
check("dotted target kept",      cw.sanitise("[a](file.md)") == "[a](file.md)")
check("closed fence verbatim",   cw.sanitise("```json\n[[0, 10]] [eq](x1)\n```\n") == "```json\n[[0, 10]] [eq](x1)\n```\n")
check("unclosed fence defanged", cw.sanitise("```\n[[x]]") == "```\n" + r"\[\[x]]")
check("prose around fence defanged", cw.sanitise("see [[p]]\n```\n[[keep]]\n```\n[[q]]") == r"see \[\[p]]" + "\n```\n[[keep]]\n```\n" + r"\[\[q]]")

print("== slug ==")
check("slug from url",           cw.slug_from("https://x.test/A/B?q=1") == "x-test-a-b-q-1")
check("slug from title wins",    cw.slug_from("https://x.test", "My Great Paper!") == "my-great-paper")
check("slug never empty",        cw.slug_from("///") == "capture")

print("== write path ==")
rl.init(RID, 3)
r = run("write", "--url", "https://x.test/one", "--ledger-id", RID,
        "--engine", "defuddle", "--title", "One", stdin=GOOD)
dest = os.path.join(VAULT, "raw", "one.md")
check("write ok",                r.returncode == 0 and os.path.exists(dest))
body = open(dest).read() if os.path.exists(dest) else ""
check("frontmatter complete",    all(s in body for s in
      ('title: "One"', "source_url: https://x.test/one", "converted_from:",
       "converted_by: defuddle", "converted_on:")))
check("body sanitised",          r"\[\[stray]]" in body)
check("clean write not stamped", "capture_quality" not in body)
check("ledger appended",         rl.summary(rl.load(rl.path_for(RID)))["pages_captured"] == 1)
r = run("write", "--url", "https://x.test/one", "--ledger-id", RID, "--title", "One", stdin=GOOD)
check("existing path refused",   r.returncode == 2 and "immutable" in r.stderr)
r = run("write", "--url", "https://x.test/two", "--ledger-id", RID, "--title", "Two", stdin=GOOD)
check("second write ok",         r.returncode == 0)
r = run("write", "--url", "https://x.test/four", "--ledger-id", "missing-" + RID, stdin=GOOD)
check("missing ledger stops",    r.returncode == 2 and "STOP" in r.stderr)
r = run("write", "--url", "https://x.test/five", "--ledger-id", RID, stdin="   ")
check("empty stdin refused",     r.returncode == 2)

print("== quality gate ==")
r = run("write", "--url", "https://x.test/stub", "--ledger-id", RID, "--title", "Stub", stdin=STUB)
check("error stub refused",      r.returncode == 2 and "quality gate" in r.stderr)
r = run("write", "--url", "https://x.test/shell", "--ledger-id", RID, "--title", "Shell", stdin=SHELL)
check("404 shell refused",       r.returncode == 2 and "Page Not Found" in r.stderr)
r = run("write", "--url", "https://x.test/soup", "--ledger-id", RID, "--title", "Soup", stdin=SOUP)
check("html soup refused",       r.returncode == 2 and "HTML-dominant" in r.stderr)
check("refusals spend no budget", rl.summary(rl.load(rl.path_for(RID)))["pages_captured"] == 2)
r = run("write", "--url", "https://x.test/soup", "--ledger-id", RID, "--title", "Soup",
        "--allow-degraded", "tutorial page, HTML is the content", stdin=SOUP)
soup_dest = os.path.join(VAULT, "raw", "soup.md")
check("allow-degraded writes",   r.returncode == 0 and "DEGRADED" in r.stdout and os.path.exists(soup_dest))
check("acceptance stamped",      "capture_quality" in open(soup_dest).read())
check("ledger records degraded", rl.load(rl.path_for(RID))["captures"][-1].get("degraded") is not None)
r = run("write", "--url", "https://x.test/six", "--ledger-id", RID, "--title", "Six", stdin=GOOD)
check("budget spent refused",    r.returncode == 2 and "budget spent" in r.stderr)
r = run("check", stdin=GOOD)
check("check passes good body",  r.returncode == 0 and "PASS" in r.stdout)
r = run("check", stdin=STUB)
check("check rejects stub",      r.returncode == 3 and "REJECT" in r.stdout)
JSONSTUB = '{"data":null,"code":403,"name":"AbuseAlleviationError","message":"' + "blocked. " * 90 + '"}'
r = run("check", stdin=JSONSTUB)
check("json error stub refused", r.returncode == 3 and "JSON document" in r.stdout)
BRACED = "{ this page opens with a brace but is prose, not JSON }\n\n" + PAD
r = run("check", stdin=BRACED)
check("brace-opening prose passes", r.returncode == 0 and "PASS" in r.stdout)

print("== a declared degradation on a body the gate passes ==")
RID4 = f"cwtest4-{uuid.uuid4().hex[:8]}"
rl.init(RID4, 4)
WHY = "line-end hyphenation and flattened figure layouts remain"
r = run("write", "--url", "https://x.test/declared", "--ledger-id", RID4, "--title", "Declared",
        "--allow-degraded", WHY, stdin=GOOD)
dec_dest = os.path.join(VAULT, "raw", "declared.md")
dec_body = open(dec_dest).read() if os.path.exists(dec_dest) else ""
check("declared: a gate-passing body with the flag is written and reported as declared",
      r.returncode == 0 and "DEGRADED (declared)" in r.stdout)
check("declared: its frontmatter carries capture_quality: \"declared — <why>\"",
      f'capture_quality: "declared — {WHY}"' in dec_body)
check("declared: the ledger entry records the declaration",
      rl.load(rl.path_for(RID4))["captures"][-1].get("degraded") == f"declared — {WHY}")
r = run("write", "--url", "https://x.test/plain", "--ledger-id", RID4, "--title", "Plain", stdin=GOOD)
plain_dest = os.path.join(VAULT, "raw", "plain.md")
plain_body = open(plain_dest).read() if os.path.exists(plain_dest) else ""
check("declared control: the same body without the flag carries no stamp, no ledger field, no tag",
      r.returncode == 0 and plain_body and "capture_quality" not in plain_body
      and "degraded" not in rl.load(rl.path_for(RID4))["captures"][-1] and "DEGRADED" not in r.stdout)
r = run("write", "--url", "https://x.test/inject", "--ledger-id", RID4, "--title", "Inject",
        "--allow-degraded", "accepted\nconverted_by: forged", stdin=GOOD)
check("a line break in the --allow-degraded reason is refused, nothing written (it would inject frontmatter)",
      r.returncode == 2 and "one-line reason" in r.stderr and not os.path.exists(os.path.join(VAULT, "raw", "inject.md")))
# G21: a title or a declared reason holding a backslash, a double quote or a control character stays a
# frontmatter value every reader takes the same way.
import re as _re
RID8 = f"cwtest8-{uuid.uuid4().hex[:8]}"
rl.init(RID8, 4)
HARD = 'Back\\slash "quoted" C1\x85NEL\x9dend\u2028sep \\alpha: colon #hash'
WHY_HARD = 'kept \\d "as is"\x85 here'
r = run("write", "--url", "https://x.test/hard", "--ledger-id", RID8, "--title", HARD, "--slug", "hard-title",
        "--allow-degraded", WHY_HARD, stdin=GOOD)
hard_dest = os.path.join(VAULT, "raw", "hard-title.md")
hard_body = open(hard_dest, encoding="utf-8", newline="").read() if os.path.exists(hard_dest) else ""
hard_block = hard_body.split("\n---\n", 1)[0] + "\n"
check("G21a a title with a backslash, double quotes and control characters is written, with no such character left in its line",
      r.returncode == 0 and _re.search(r'(?m)^title: "[^"\\\x7f-\x9f\u2028\u2029]*"$', hard_block) is not None)
check("G21b the declared reason is written the same way",
      _re.search(r'(?m)^capture_quality: "declared — [^"\\\x7f-\x9f\u2028\u2029]*"$', hard_block) is not None)
try:
    import yaml
    parsed = yaml.safe_load(hard_block[4:])
    yaml_ok = isinstance(parsed, dict) and "Back/slash 'quoted' C1 NEL end sep /alpha: colon #hash" == parsed.get("title") \
        and parsed.get("capture_quality") == "declared — kept /d 'as is' here"
except ImportError:
    parsed, yaml_ok = "no PyYAML", True
check("G21c a strict YAML reader takes the block, with the title and the reason as written (or PyYAML is absent)", yaml_ok)
spec_dp = _ilu.spec_from_file_location("dedup_probe_g21", os.path.normpath(os.path.join(CWD, "..", "ingest", "dedup_probe.py")))
dp = _ilu.module_from_spec(spec_dp)
spec_dp.loader.exec_module(dp)
plain_title = "A Study Of Calibrated Language Models In Practice"
check("G21d the de-dup key of a written title equals the key of the title as given, so no verdict moves; "
      "control: the flat reader returns the title whole",
      str(dp.title_key(dp.frontmatter(hard_block.replace("\r\n", "\n") + "---\n").get("title", ""))) == str(dp.title_key(HARD))
      and str(dp.title_key(cw._one_line('A "Study" Of Calibrated Language Models In Practice', limit=None))) == str(dp.title_key(plain_title)))
check("G21e control: an ordinary title and a stamp's bound are unchanged",
      cw._one_line("One", limit=None) == "One" and len(cw._one_line("x" * 400)) == 300)
# F5: a title keeps its colon, since the colon decides its keys (a name-stripped key needs a dash, never a colon);
# a stamp or a reason still never carries a provenance field name followed by its colon.
FIELD_TITLE = "Converter: Efficient Source Parsing"
def _title_keys(title):
    k = dp.title_key(title)
    return (str(k), getattr(k, "suffix_stripped", None), getattr(k, "name_stripped", None))
KEY_TITLES = [FIELD_TITLE, "converted_by: a Survey of Long Context Models", "METHOD — Calibrated Reasoning and Confidence Estimates",
              "Lost in the Middle: How Language Models Use Long Contexts | arXiv", 'A "Study" Of Calibrated Language Models In Practice',
              "Back\\slash Reading Of Calibrated Language Models", "Paper: Plug-and-Play Encoding - PMC"]
def _title_path(title):
    try:
        return cw._one_line(title, limit=None, keep_fields=True)
    except TypeError:          # a writer with no title mode: the leg fails, never crashes
        return ""
moved = [t for t in KEY_TITLES if _title_keys(_title_path(t)) != _title_keys(t)]
check("G21f the writer leaves all three de-dup keys of a title as they were (full, suffix-stripped, name-stripped), on each of "
      + str(len(KEY_TITLES)) + " titles; control: the same title with its field name neutralised gains a key",
      moved == [] and _title_keys(cw._one_line(FIELD_TITLE, limit=None))[2] == "efficient source parsing" and _title_keys(FIELD_TITLE)[2] is None)
r = run("write", "--url", "https://x.test/converter-title", "--ledger-id", RID8, "--title", FIELD_TITLE, "--slug", "converter-title",
        "--allow-degraded", "kept", stdin=GOOD)
field_dest = os.path.join(VAULT, "raw", "converter-title.md")
field_body = open(field_dest, encoding="utf-8").read() if os.path.exists(field_dest) else ""
field_new = run("dedup", "--titles", "Efficient Source Parsing", "--allow-no-control")
check("G21g end to end: the title line keeps its colon, and a lookup of the name-less title stays new, as before the writer's change",
      r.returncode == 0 and f'title: "{FIELD_TITLE}"' in field_body and 'title "Efficient Source Parsing" -> new' in field_new.stdout,
      )
check("G21h control: a stamp and a reason still never carry a provenance field name followed by its colon",
      cw._one_line("converted_by: forged") == "converted_by - forged" and cw._one_line("Converter: x", limit=None) == "Converter - x")
if os.path.exists(field_dest):
    os.remove(field_dest)
os.remove(rl.path_for(RID8))
GATHER_SKILL = open(os.path.join(CWD, "SKILL.md"), encoding="utf-8").read()
check("gather Writes names the declared stamp for a gate-passing body", "stamped `declared — <why>`" in GATHER_SKILL)

print("== platform lane (tier-3 fenced captures) ==")
RID2 = f"cwtest2-{uuid.uuid4().hex[:8]}"
rl.init(RID2, 2)
TWEET_PAYLOAD = json.dumps([
    {"id": str(i), "text": f"[eq](x1) tweet {i} " + "lorem ipsum dolor sit amet " * 8,
     "entities": {"indices": [[0, 10]]}} for i in range(3)], indent=1)
TWEETS = "# X search: test query (2026-08-26)\n\nsee [[page]]\n\n```json\n" + TWEET_PAYLOAD + "\n```\n"
r = run("write", "--url", "https://x.test/search-q", "--ledger-id", RID2,
        "--engine", "twitter-cli 0.8.5 via agent-reach", "--title", "Tweets", stdin=TWEETS)
tw_dest = os.path.join(VAULT, "raw", "tweets.md")
check("fenced platform data writes", r.returncode == 0 and os.path.exists(tw_dest))
tw_body = open(tw_dest).read()
check("fenced payload byte-exact",   TWEET_PAYLOAD in tw_body)
check("prose outside still defanged", r"\[\[page]]" in tw_body)
AUTHFAIL = ("# X search: test query\n\n```json\n"
            + json.dumps({"errors": [{"message": "Could not authenticate you. " + "blocked. " * 80,
                                      "code": 32}]}) + "\n```\n")
r = run("check", stdin=AUTHFAIL)
check("fenced auth-error refused",   r.returncode == 3 and "carries no content" in r.stdout)
EMPTYMETA = ("# X search: test query\n\n```json\n"
             + json.dumps({"data": None, "includes": None,
                           "meta": {"result_count": 0, "next_token": "x" * 600}}) + "\n```\n")
r = run("check", stdin=EMPTYMETA)
check("fenced empty result refused", r.returncode == 3 and "carries no content" in r.stdout)
EMPTYARR = "# Reddit read\n\n" + "context line. " * 20 + "\n\n```json\n" + "[]".ljust(400) + "\n```\n"
r = run("check", stdin=EMPTYARR)
check("fenced empty array refused",  r.returncode == 3 and "empty platform result" in r.stdout)
PARTIAL = ("# X search\n\n```json\n"
           + json.dumps({"data": [{"id": "1", "text": "real tweet " * 60}],
                         "errors": [{"message": "partial failure on one expansion"}]}) + "\n```\n")
r = run("check", stdin=PARTIAL)
check("partial data + errors passes", r.returncode == 0 and "PASS" in r.stdout)
SUBS = ("# YouTube subtitles\n\n```\nWEBVTT\n\n"
        + "\n".join(f"00:0{i%10}:01.000 --> 00:0{i%10}:02.000\n<i>spoken line {i}</i>\n"
                    for i in range(60)) + "\n```\n")
r = run("check", stdin=SUBS)
check("fenced subtitle markup passes", r.returncode == 0 and "PASS" in r.stdout)
LOGINWALL = ("# Reddit read\n\n```\n<!DOCTYPE html>\n<html>\n<head><title>Log in</title></head>\n<body>\n"
             + "\n".join(f'<div class="login-prompt-{i}">please sign in</div>' for i in range(40))
             + "\n</body>\n</html>\n```\n")
r = run("check", stdin=LOGINWALL)
check("fenced login wall refused",   r.returncode == 3 and "HTML page" in r.stdout)
QUOTED = ("# Article about the X API\n\n" + PAD + "\n\nAn auth failure returns:\n\n```json\n"
          + json.dumps({"errors": [{"message": "Could not authenticate you", "code": 32}]}) + "\n```\n\n" + PAD)
r = run("check", stdin=QUOTED)
check("quoted error example passes", r.returncode == 0 and "PASS" in r.stdout)
BAREARRAY = json.dumps([{"id": "1", "text": "unfenced platform output " * 40}])
r = run("check", stdin=BAREARRAY)
check("bare JSON array refused",     r.returncode == 3 and "bare JSON document" in r.stdout)

print("== browser rung: the abstract-page rule (chrome-burner), keyed on what an article has ==")
RID3 = f"cwtest3-{uuid.uuid4().hex[:8]}"
rl.init(RID3, 6)
TF = "https://journal.test/doi/full/10.9999/abc.123"
def burner_check(body, *extra):
    return run("check", "--engine", "chrome-burner", *extra, stdin=body)
def section(heading):
    return "\n\n" + heading + "\n\n" + PAD
# Two synthetic abstract-page shapes: a reader-service copy of a preprint abstract page,
# and a publisher abstract page listing related links and its references.
PREPRINT_ABS = ("Title: Localizing strictly proper scoring rules\n\nURL Source: https://preprint.test/abs/2601.00001\n\n"
                "Markdown Content:\n[View PDF](https://preprint.test/pdf/2601.00001)[HTML (experimental)](https://preprint.test/html/2601.00001v1)\n\n"
                "> Abstract:" + PAD + "\n\nComments:26 pages, 7 figures\nSubjects:Statistics Theory (math.ST)\n"
                "Cite as:[preprint:2601.00001](https://preprint.test/abs/2601.00001) [math.ST]\n\n## Submission history\n\n"
                "From: A. Author [view email](https://preprint.test/show-email/1)\n\n**[v1]** Mon, 29 Jun 2026 12:20:14 UTC (401 KB)\n")
REFERENCES = ["{0}.   Author, A. B. and Writer, C. D. Title of cited work number {0}. _Journal of Tests_, {1}, {0}-{2}.".format(i, 1960 + i, i + 9)
              for i in range(1, 41)]
REFERENCE_LIST = "".join(ref + "\n\n[Google Scholar](https://scholar.test/lookup?id=" + str(i) + ")\n\n" for i, ref in enumerate(REFERENCES, 1))
RELATED = "".join("[Related article " + str(i) + ": proper scoring rules, calibration and the evaluation of forecasts]"
                  "(https://journal.test/related/" + str(i) + ")\n\n" for i in range(1, 13))
PUBLISHER_ABS = ("# Localizing strictly proper scoring rules\n\nJournal of Tests · Volume 121 · Issue 1\n\n## Abstract\n\n" + PAD
                 + "\n\nKeywords: scoring rules; calibration\n\n### Similar content being viewed by others\n\n" + RELATED
                 + "## References\n\n" + REFERENCE_LIST + "Download PDF · Cite · Share\n")
ARTICLE = ("# Localizing strictly proper scoring rules\n\n## Abstract\n\n" + PAD + section("## 1 Introduction")
           + section("## 2 Methods") + section("## 3 Results") + "\n\n## References\n\n" + REFERENCE_LIST)
UNUSUAL = ("# A note on proper scoring\n\n## Abstract\n\n" + PAD + section("## Background") + section("## Experiments")
           + section("## Conclusion") + "\n")
SECTIONS = " ".join(f"{n} {name} {PAD.strip()}" for n, name in enumerate(("Introduction", "Background", "Methods", "Results", "Discussion"), 1))
COLLAPSED = ("Localizing strictly proper scoring rules A. Author Abstract: " + PAD.strip() + " " + SECTIONS
             + " References [1] A. Author, Title, 2020. [2] B. Writer, Title, 2021.\n")
COLLAPSED_AT_MARKER = "Abstract: " + PAD.strip() + " " + SECTIONS + " References [1] A. Author, Title, 2020.\n"
COLLAPSED_ABS = ("Localizing strictly proper scoring rules Abstract: " + PAD.strip() + " "
                 + " ".join("[Related article " + str(i) + " on scoring](https://journal.test/related/" + str(i) + ")" for i in range(1, 40))
                 + " Download PDF Cite Share\n")
SHAPES = [("Markdown heading", "## {}"), ("wholly bold line", "**{}**"), ("numbered line", "2 {}"), ("glued numbering", "4.2.{}"),
          ("roman numbering", "II. {}"), ("letter numbering", "B.3 {}"), ("all-capitals line", "{}")]
def shaped(fmt, caps=False):
    return ("## Abstract\n\n" + PAD + "".join(section(fmt.format(n.upper() if caps else n))
                                              for n in ("Background", "Experiments", "Conclusion")) + "\n")
PROSE_ONLY = ("## Abstract\n\n" + PAD + section("We describe the background of the problem first.")
              + section("We then report the experiments in turn.") + section("We close with a short conclusion.") + "\n")
PROSE_WITH_REFS = PROSE_ONLY + "\n" + "\n".join(REFERENCES[:10]) + "\n"
NO_MARKER_ARTICLE = "# A note\n\n" + PAD + section("## Background") + section("## Experiments") + section("## Conclusion") + "\n"
NO_MARKER_PAGE = "# A landing page\n\n" + PAD + "\n\nDownload PDF · Cite · Share\n"
FENCED_ARTICLE = "```\n" + ARTICLE + "\n```\n"

r = run("write", "--url", TF, "--ledger-id", RID3, "--engine", "chrome-burner", "--title", "Abs", stdin=PREPRINT_ABS)
abs_dest = os.path.join(VAULT, "raw", "abs.md")
check("F6 must fire: a preprint abstract page (reader-service shape) refused on write, nothing written",
      r.returncode == 2 and "abstract-only" in r.stderr and not os.path.exists(abs_dest))
check("refusal prints the URL for hand-fetch", TF in r.stderr and "oa_resolve.py --hand-fetch" in r.stderr)
check("refusal names its measure and the floor",
      "words of prose after the abstract" in r.stderr and f"fewer than the {cw.ARTICLE_MIN_WORDS}" in r.stderr)
r = run("write", "--url", TF, "--ledger-id", RID3, "--engine", "chrome-burner", "--title", "Abs",
        "--allow-degraded", "owner wants the abstract", stdin=PREPRINT_ABS)
check("allow-degraded does not lift the rule", r.returncode == 2 and "abstract-only" in r.stderr and not os.path.exists(abs_dest))
r = run("write", "--url", TF, "--ledger-id", RID3, "--engine", "chrome (burner)", "--title", "Abs", stdin=PREPRINT_ABS)
check("'chrome (burner)' spelling refused",  r.returncode == 2 and "abstract-only" in r.stderr)
check("abstract refusals spend no budget",   rl.summary(rl.load(rl.path_for(RID3)))["pages_captured"] == 0)
r = run("write", "--url", TF, "--ledger-id", RID3, "--engine", "chrome-burner", "--title", "Article", stdin=ARTICLE)
art_dest = os.path.join(VAULT, "raw", "article.md")
check("burner article with sections writes", r.returncode == 0 and os.path.exists(art_dest)
      and "converted_by: chrome-burner" in open(art_dest).read())
r = burner_check(PUBLISHER_ABS, "--url", TF)
check("F6 must fire: a publisher abstract page listing related links and 40 references refused (a reference list is not the article)",
      r.returncode == 3 and "abstract-only" in r.stdout and TF in r.stdout and cw.article_measures(PUBLISHER_ABS)["references"] == 40)
check("F6 control: those 40 references alone carry more words than the floor, so leaving them out is what refuses the page",
      sum(len(cw.PROSE_WORD.findall(ref)) for ref in REFERENCES) > cw.ARTICLE_MIN_WORDS)
r = run("write", "--url", TF + "-unusual", "--ledger-id", RID3, "--engine", "chrome-burner", "--title", "Unusual", stdin=UNUSUAL)
check("F6 must not fire: a paper with unusual headings (Background, Experiments, Conclusion) and no reference list writes",
      r.returncode == 0 and os.path.exists(os.path.join(VAULT, "raw", "unusual.md")))
r = burner_check(COLLAPSED)
mc = cw.article_measures(COLLAPSED)
check("F6 must not fire: a collapsed one-line paper carrying its sections passes (no line structure, so the structure arm abstains)",
      r.returncode == 0 and mc["headings"] == 0 and mc["longest_line"] > cw.COLLAPSED_LINE_CHARS and mc["words"] >= cw.ARTICLE_MIN_WORDS)
r = burner_check(COLLAPSED_AT_MARKER)
check("F6 must not fire: the collapsed paper opening on its abstract marker passes (a run-on abstract is capped)", r.returncode == 0)
r = burner_check(COLLAPSED_ABS)
check("F6 must fire: a collapsed one-line abstract page refused (the abstention lifts the structure arm only)",
      r.returncode == 3 and "words of prose" in r.stdout)
failed = [label for label, fmt in SHAPES if burner_check(shaped(fmt, label == "all-capitals line")).returncode != 0]
check("F6 heading shapes count, never names (" + ", ".join(label for label, _ in SHAPES) + ")"
      + (f": FAILED {failed}" if failed else ""), not failed)
r = burner_check(PROSE_ONLY)
check("F6 must fire: an article-length body with no heading line and no reference list refused on structure",
      r.returncode == 3 and "no section structure" in r.stdout)
r = burner_check(PROSE_WITH_REFS)
check("F6 must not fire: the same body carrying a reference list of 10 entries passes", r.returncode == 0)
check("premise: no abstract marker, the whole body is measured (an article passes, a short page is refused)",
      burner_check(NO_MARKER_ARTICLE).returncode == 0 and burner_check(NO_MARKER_PAGE).returncode == 3)
r = burner_check(FENCED_ARTICLE)
check("premise: an article wholly inside a closed fence is quoted material, refused", r.returncode == 3 and "abstract-only" in r.stdout)
check("premise: CRLF line endings measure the same (the article passes, the abstract page is refused)",
      burner_check(ARTICLE.replace("\n", "\r\n")).returncode == 0 and burner_check(PREPRINT_ABS.replace("\n", "\r\n")).returncode == 3)
r = run("check", "--engine", "markitdown of a chrome-burner download", stdin=PREPRINT_ABS)
check("engine naming the burner download refused", r.returncode == 3 and "abstract-only" in r.stdout)
r = run("check", "--engine", "chrome-burner", stdin="## Abstract\n\nshort landing page\n")
check("tiny burner body refused by the size floor first", r.returncode == 3 and "too small" in r.stdout)
r = run("check", "--engine", "defuddle", stdin=PREPRINT_ABS)
check("must not fire: headless engine, abstract body passes", r.returncode == 0 and "PASS" in r.stdout)
r = run("check", stdin=PUBLISHER_ABS)
check("must not fire: no engine given, abstract body passes", r.returncode == 0 and "PASS" in r.stdout)
check("rule unit: unknown engine is not the burner", cw.abstract_only_reason(PREPRINT_ABS, "unknown") is None
      and cw.abstract_only_reason(PREPRINT_ABS, "") is None and cw.abstract_only_reason(PREPRINT_ABS, None) is None)
check("rule unit: empty body on the burner is refused", (cw.abstract_only_reason("", "chrome-burner") or "").startswith("abstract-only"))

print("== browser rung: resolved_url beside source_url ==")
PMC = "https://pmc.ncbi.nlm.nih.gov/articles/PMC0000001/"
r = run("write", "--url", "https://journal.test/doi/10.9999/res.1", "--resolved-url", PMC, "--ledger-id", RID3,
        "--engine", "defuddle", "--title", "Resolved", stdin=GOOD)
res_dest = os.path.join(VAULT, "raw", "resolved.md")
res_body = open(res_dest).read() if os.path.exists(res_dest) else ""
check("resolved write ok",                   r.returncode == 0 and res_body)
check("resolved_url sits right after source_url",
      "source_url: https://journal.test/doi/10.9999/res.1\nresolved_url: " + PMC + "\nconverted_from:" in res_body)
check("ledger records resolved_url",         rl.load(rl.path_for(RID3))["captures"][-1].get("resolved_url") == PMC)
ONE_MD = os.path.join(VAULT, "raw", "one.md")
check("no resolved_url without the flag",    os.path.exists(ONE_MD) and "resolved_url" not in open(ONE_MD).read())
r = run("write", "--url", "https://journal.test/x", "--resolved-url", "not a url", "--ledger-id", RID3, "--title", "Bad1", stdin=GOOD)
check("malformed resolved-url refused",      r.returncode == 2 and "--resolved-url" in r.stderr
      and not os.path.exists(os.path.join(VAULT, "raw", "bad1.md")))
r = run("write", "--url", "https://journal.test/x", "--resolved-url", "https://ok.test/a\nconverted_by: forged",
        "--ledger-id", RID3, "--title", "Bad2", stdin=GOOD)
check("newline in resolved-url refused",     r.returncode == 2 and not os.path.exists(os.path.join(VAULT, "raw", "bad2.md")))
r = run("dedup", "--urls", PMC, "--control", "https://x.test/two")
check("dedup finds a capture by resolved_url", r.returncode == 0 and "ALREADY IN VAULT" in r.stdout and "resolved.md" in r.stdout)

print("== dedup ==")
r = run("dedup", "--urls", "https://x.test/one,https://x.test/new", "--control", "https://x.test/two")
r2 = run("dedup", "--urls", "https://x.test/one", "https://x.test/new", "--control", "https://x.test/two")
check("space form works",        r2.returncode == 0 and "ALREADY IN VAULT" in r2.stdout and "https://x.test/new -> new" in r2.stdout)
r2 = run("dedup", "--urls", "https://x.test/one,https://x.test/new", "https://x.test/extra", "--control", "https://x.test/two")
check("mixed form works",        r2.returncode == 0 and "https://x.test/extra -> new" in r2.stdout)
check("dedup finds present",     r.returncode == 0 and "ALREADY IN VAULT" in r.stdout)
check("dedup passes new",        "https://x.test/new -> new" in r.stdout)
r = run("dedup", "--urls", "https://x.test/new", "--control", "https://nowhere.test/none")
check("dead control fails scan", r.returncode == 2 and "cannot be trusted" in r.stderr)
r = run("dedup", "--urls", "https://x.test/new")
check("no control refused",      r.returncode == 2 and "control" in r.stderr)
r = run("dedup", "--urls", "https://x.test/new", "--allow-no-control")
check("explicit opt-out works",  r.returncode == 0)

long_fm = os.path.join(VAULT, "raw", "longfm.md")
open(long_fm, "w").write("---\ntitle: t\nnote_field: " + "x" * 5000 + "\nsource_url: https://x.test/longfm\n---\nbody\n")
r = run("dedup", "--urls", "https://x.test/longfm", "--control", "https://x.test/two")
check("key past 4096 B found (extend-on-miss)", "ALREADY IN VAULT" in r.stdout and "longfm" in r.stdout)

print("== dedup: a review site's name proves no review (G7) ==")
import shutil
G7V = tempfile.mkdtemp(prefix="cwtest-g7-")
def _g7put(rel, title, extra=""):
    p = os.path.join(G7V, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(f'---\ntitle: "{title}"\n{extra}---\n\nbody\n')
_g7put("wiki/sources/held-paper.md", "Paper: Lost in the Middle: How Language Models Use Long Contexts")
_g7put("wiki/sources/control.md", "Source: The Control Page Itself", "source_url: https://control.test/present\n")
_g7put("raw/7-reviews/held-review.md", "Calibrated Reasoning Under Long Contexts | OpenReview")
_g7put("raw/2-papers/held-copy.md", "Another Held Paper Page Title | arXiv")
def g7run(*titles):
    return subprocess.run([sys.executable, "-B", os.path.join(CWD, "capture_write.py"), "dedup", "--vault-root", G7V,
                           "--titles", *titles, "--control", "https://control.test/present"], capture_output=True, text=True, cwd=CWD)
SITE_T = "Lost in the Middle: How Language Models Use Long Contexts | OpenReview"
r = g7run(SITE_T)
check("G7g an OpenReview title meeting a held paper by a stripped key alone is shown as paper or its review, never as already in the vault",
      r.returncode == 0 and f'title "{SITE_T}" ~> paper or its review: wiki/sources/held-paper.md (matched on: suffix-stripped title;' in r.stdout
      and "never exclude it" in r.stdout and "ALREADY IN VAULT" not in r.stdout)
r = g7run("Calibrated Reasoning Under Long Contexts")
check("G7h the same from the other side: a plain title meeting a held OpenReview record by that record's stripped key is shown the same way",
      r.returncode == 0 and "~> paper or its review: raw/7-reviews/held-review.md" in r.stdout and "ALREADY IN VAULT" not in r.stdout)
r = g7run("Lost in the Middle: How Language Models Use Long Contexts | arXiv", "Another Held Paper Page Title")
check("G7i controls: a stripped-key hit with no review site stays already in the vault, from either side",
      r.returncode == 0 and r.stdout.count("ALREADY IN VAULT") == 2 and "paper or its review" not in r.stdout)
r = g7run("Calibrated Reasoning Under Long Contexts | OpenReview")
check("G7j control: a full-title hit on the review site's own record stays already in the vault",
      r.returncode == 0 and "ALREADY IN VAULT: raw/7-reviews/held-review.md (matched on: title)" in r.stdout and "paper or its review" not in r.stdout)
shutil.rmtree(G7V)

print("== dedup paper keys: arXiv id, DOI, normalised title (a page with no source_url) ==")
import hashlib, re, shutil
KV = tempfile.mkdtemp(prefix="cwtest-keys-")
TITLE_TXT = "Paper: Lost in the Middle — How Language Models Use Long Contexts"
PAGE_REL = "wiki/sources/lost-in-the-middle.md"
def put(root, rel, text):
    p = os.path.join(root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh: fh.write(text)
def lim_page(source_url=None):
    # the page the defect missed: compiled from a local PDF, so doi and source_hash, no source_url until backfilled
    return (f'---\ntitle: "{TITLE_TXT}"\ntype: source\ndepth: research\ndoi: "10.1162/tacl_a_00638"\n'
            + (f'source_url: "{source_url}"\n' if source_url else "")
            + 'sources: [raw/2-papers/lost-in-the-middle.pdf]\nsource_hash: "0123456789abcdef"\n---\n\n## Related\n')
put(KV, PAGE_REL, lim_page())
put(KV, "wiki/sources/control.md", '---\ntitle: "Source: The Control Page Itself"\nsource_url: https://control.test/present\n---\n')
put(KV, "raw/2-papers/lost-in-the-middle.md", "---\nconverted_from: local.pdf\n---\n\nLost in the Middle\n")
put(KV, "wiki/concepts/lost-in-the-middle-effect.md", '---\ntitle: "Lost in the Middle: How Language Models Use Long Contexts"\ntype: concept\n---\n')
CTL = ["--control", "https://control.test/present"]
def runk(root, *args, script=None, cwd=None):
    return subprocess.run([sys.executable, "-B", script or os.path.join(CWD, "capture_write.py"), "dedup",
                           "--vault-root", root] + list(args), capture_output=True, text=True, cwd=cwd or CWD)
def line_for(r, label):
    m = re.search(r"(?m)^" + re.escape(label) + r" -> (.*)$", r.stdout)
    return m.group(1) if m else ""
r = runk(KV, "--urls", "https://arxiv.org/abs/2307.03172", "--titles", TITLE_TXT, *CTL)
check("K1 the defect's pair: URL new on the URL keys, caught on the title alone",
      r.returncode == 0 and line_for(r, "https://arxiv.org/abs/2307.03172") == "new"
      and line_for(r, f'title "{TITLE_TXT}"') == f"ALREADY IN VAULT: {PAGE_REL} (matched on: title)")
check("K1 title key scoped to source pages and raw (same-titled concept page not listed)", "wiki/concepts" not in r.stdout)
r = runk(KV, "--urls", "https://doi.org/10.1162/TACL_A_00638", *CTL)
check("K2 DOI alone: resolver URL vs doi: frontmatter",
      line_for(r, "https://doi.org/10.1162/TACL_A_00638") == f"ALREADY IN VAULT: {PAGE_REL} (matched on: doi 10.1162/tacl_a_00638)")
put(KV, PAGE_REL, lim_page("https://arxiv.org/abs/2307.03172"))
r = runk(KV, "--urls", "https://arxiv.org/pdf/2307.03172v3", *CTL)
check("K3 arXiv id alone: pdf-form URL vs the backfilled abs URL",
      line_for(r, "https://arxiv.org/pdf/2307.03172v3") == f"ALREADY IN VAULT: {PAGE_REL} (matched on: arxiv 2307.03172)")
NEG_URLS = ["https://arxiv.org/abs/2403.04797", "https://arxiv.org/abs/2307.03173", "https://doi.org/10.1162/tacl_a_0063"]
NEG_TITLES = ["Found in the Middle: How Language Models Use Long Contexts Better via Plug-and-Play Positional Encoding",
              "Lost in the Middle: How Language Models Use Long Contexts at Scale"]
r = runk(KV, "--urls", *NEG_URLS, "https://arxiv.org/pdf/2307.03172v3", "--titles", *NEG_TITLES, "Lost in the Middle", *CTL)
check("K4 negative control: similar titles and near-miss ids stay new",
      r.returncode == 0 and all(line_for(r, u) == "new" for u in NEG_URLS)
      and all(line_for(r, f'title "{t}"') == "new" for t in NEG_TITLES))
check("K4 positive control in the same run: the real id still matches",
      line_for(r, "https://arxiv.org/pdf/2307.03172v3").startswith("ALREADY IN VAULT"))
check("K4 a two-token title is reported not keyed, never silently new", "not keyed" in line_for(r, 'title "Lost in the Middle"'))
check("K4 index counts and key self-test printed", "keys indexed:" in r.stdout and "key self-test" in r.stdout)
LONE = tempfile.mkdtemp(prefix="cwtest-lone-")
for f in ("capture_write.py", "run_ledger.py"):
    os.makedirs(os.path.join(LONE, "gather"), exist_ok=True); shutil.copy(os.path.join(CWD, f), os.path.join(LONE, "gather", f))
LONE_CW = os.path.join(LONE, "gather", "capture_write.py")
r = runk(KV, "--urls", "https://arxiv.org/abs/2307.03172", *CTL, script=LONE_CW, cwd=LONE)
check("K5 key module missing -> exit 2, never new", r.returncode == 2 and "key module missing" in r.stderr and "-> new" not in r.stdout)
put(LONE, "ingest/dedup_probe.py", "def self_test():\n    return ['planted dead extractor']\n")
r = runk(KV, "--urls", "https://arxiv.org/abs/2307.03172", *CTL, script=LONE_CW, cwd=LONE)
check("K5 planted key self-test failure -> exit 2", r.returncode == 2 and "self-test failed" in r.stderr and "-> new" not in r.stdout)
NOTITLE = tempfile.mkdtemp(prefix="cwtest-notitle-")
put(NOTITLE, "wiki/sources/c.md", "---\nsource_url: https://control.test/present\n---\n")
put(NOTITLE, "raw/x.md", "---\nconverted_from: local.pdf\n---\n")
r = runk(NOTITLE, "--titles", "A Title Long Enough To Key", *CTL)
check("K5 titles against an index holding no title -> exit 2", r.returncode == 2 and "title index empty" in r.stderr)
def manifest(top):
    rows = []
    for root, dirs, files in os.walk(top):
        dirs.sort(); rows.append((os.path.relpath(root, top), tuple(sorted(dirs + files))))
        for f in sorted(files):
            p = os.path.join(root, f)
            with open(p, "rb") as fh:
                rows.append((os.path.relpath(p, top), os.stat(p).st_mtime_ns, hashlib.sha256(fh.read()).hexdigest()))
    return rows
RO_PARENT = tempfile.mkdtemp(prefix="cwtest-ro-"); RO = os.path.join(RO_PARENT, "vault")
shutil.copytree(KV, RO)
before = manifest(RO)
for root, dirs, files in os.walk(RO):
    for f in files: os.chmod(os.path.join(root, f), 0o444)
    os.chmod(root, 0o555)
r = runk(RO, "--urls", "https://arxiv.org/pdf/2307.03172v3", *NEG_URLS, "--titles", *NEG_TITLES, *CTL)
after = manifest(RO)
check("K6 dedup on a read-only vault copy matched, and its checksum manifest is unchanged",
      line_for(r, "https://arxiv.org/pdf/2307.03172v3").startswith("ALREADY IN VAULT") and before == after and len(before) > 5)
for root, dirs, files in os.walk(RO_PARENT):
    os.chmod(root, 0o755)
for d in (KV, LONE, NOTITLE, RO_PARENT):
    shutil.rmtree(d)

print("== the capture check warns: every write records its stamp, and no result refuses a write ==")
RID5 = f"cwtest5-{uuid.uuid4().hex[:8]}"
rl.init(RID5, 80)   # room for every write here, so no leg meets the budget
STAMPS = []         # every stamp written in this section, for W13
def raw_body(slug):
    p = os.path.join(VAULT, "raw", slug + ".md")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""
def raw_stamp(slug):
    m = re.search(r'(?m)^capture_check: "(.*)"$', raw_body(slug).split("\n---\n", 1)[0])
    if m:
        STAMPS.append(m.group(1))
    return m.group(1) if m else ""
def ledger5():
    return rl.load(rl.path_for(RID5))["captures"][-1]
def run5(url, engine, slug, *extra, stdin=GOOD):
    return run("write", "--url", url, "--ledger-id", RID5, "--slug", slug,
               *(["--engine", engine] if engine else []), *extra, stdin=stdin)
COLLAPSED_BODY = "# Terms\n\n" + PAD + "\n\n**Visa terms**\n\n" + VISA + "\n"
ROUTE_ENGINE = "curl+markitdown (structural route)"
NO_LOSS, LOSS, NOT_RUN = "no loss found by the unit check (", "suspected loss — ", "not run — "
r = run5("https://x.test/web", "defuddle", "w-noresult")
check("W1 no result refuses nothing: a defuddle capture with no probe result is written, stamped not run, no probe "
      "result given, in frontmatter and ledger",
      r.returncode == 0 and raw_stamp("w-noresult") == "not run — no probe result given"
      and ledger5().get("capture_check") == "not run — no probe result given" and "capture check: not run" in r.stdout)
FAILED = probe_result("https://x.test/web", PLAIN_PAGE, ROUTE_ENGINE, status="fail", stage="fetch",
                      reason="curl exit 18 under HTTP 200: the transfer failed whatever the status line said",
                      fetch={"curl_exit": 18})
r = run5("https://x.test/web", ROUTE_ENGINE, "w-failed", "--probe-result", FAILED)
check("W2 a failed result refuses nothing: written, stamped not run with the probe's own failure (curl exit 18)",
      r.returncode == 0 and raw_stamp("w-failed").startswith(NOT_RUN + "the probe made no capture")
      and "curl exit 18" in raw_stamp("w-failed"))
BROKEN = os.path.join(tempfile.mkdtemp(prefix="cwtest-probe-"), "result.json")
PROBE_DIRS.append(os.path.dirname(BROKEN))
open(BROKEN, "w").write("{ not json")
r = run5("https://x.test/web", "defuddle", "w-broken", "--probe-result", BROKEN)
check("W3 an unreadable result refuses nothing: written, stamped not run, the parse failure named",
      r.returncode == 0 and raw_stamp("w-broken").startswith(NOT_RUN + "the probe result is unreadable")
      and "JSONDecodeError" in raw_stamp("w-broken"))
r = run5("https://x.test/web", "defuddle", "w-missing",
         "--probe-result", os.path.join(tempfile.gettempdir(), f"absent-{uuid.uuid4().hex}", "result.json"))
check("W4 a result path that does not exist refuses nothing: written, stamped not run",
      r.returncode == 0 and raw_stamp("w-missing") == "not run — no probe result at the path given")
r = run5("https://x.test/web", "defuddle", "w-changed",
         "--probe-result", probe_result("https://x.test/web", PLAIN_PAGE, "defuddle", sha="0" * 64))
check("W5 a result whose fetched page changed since the probe refuses nothing: written, stamped not run",
      r.returncode == 0 and raw_stamp("w-changed") == "not run — the fetched page has changed since the probe")
ROUTED = probe_result("https://x.test/terms", COLLAPSED_PAGE, ROUTE_ENGINE, route="ROUTE", capture=COLLAPSED_BODY)
r = run5("https://x.test/terms", ROUTE_ENGINE, "w-lost", "--probe-result", ROUTED, stdin=COLLAPSED_BODY.replace(VISA, ""))
check("W6 must warn: a body that lost a collapsed sentence is written, stamped suspected loss naming it, in frontmatter "
      "and ledger alike",
      r.returncode == 0 and raw_stamp("w-lost").startswith(LOSS) and VISA in raw_stamp("w-lost")
      and ledger5().get("capture_check") == raw_stamp("w-lost") and "capture check: suspected loss" in r.stdout)
r = run5("https://x.test/terms", ROUTE_ENGINE, "w-kept", "--probe-result", ROUTED, stdin=COLLAPSED_BODY)
check("W7 must not warn: the body that keeps it is stamped no loss found by the unit check, naming what the check does "
      "not compare (literal punctuation, empty-cell positions in tables), with no capture_quality",
      r.returncode == 0 and raw_stamp("w-kept").startswith(NO_LOSS) and "literal punctuation" in raw_stamp("w-kept")
      and "empty-cell positions in tables" in raw_stamp("w-kept") and "capture_quality" not in raw_body("w-kept")
      and "capture check: no loss found" in r.stdout)
r = run5("https://x.test/terms", "curl+defuddle", "w-mislabelled",
         "--probe-result", probe_result("https://x.test/terms", COLLAPSED_PAGE, "curl+defuddle"), stdin=COLLAPSED_BODY)
check("W8 a result calling a page with a collapsed block NOT-ROUTED is malformed: written, stamped not run (the writer's "
      "check re-routes the page)",
      r.returncode == 0 and raw_stamp("w-mislabelled").startswith(NOT_RUN) and "routes ROUTE" in raw_stamp("w-mislabelled"))
LONE_P = tempfile.mkdtemp(prefix="cwtest-lone-probe-")
for f in ("capture_write.py", "run_ledger.py"):
    shutil.copy(os.path.join(CWD, f), os.path.join(LONE_P, f))
def run_lone(where, *args, stdin=""):
    return subprocess.run([sys.executable, "-B", os.path.join(where, "capture_write.py"), "write", "--vault-root", VAULT]
                          + list(args), input=stdin, capture_output=True, text=True, cwd=where)
r = run_lone(LONE_P, "--url", "https://x.test/web", "--ledger-id", RID5, "--engine", "defuddle", "--slug", "w-lone",
             "--probe-result", probe_result("https://x.test/web", PLAIN_PAGE, "defuddle"), stdin=GOOD)
r2 = run_lone(LONE_P, "--url", "https://x.test/lone.pdf", "--ledger-id", RID5, "--engine", "markitdown", "--slug", "w-lone-pdf",
              stdin=GOOD)
check("W9 capture_probe.py missing beside the writer refuses nothing: the web page is written, stamped not run naming "
      "the missing script; a PDF with no result writes as before, stamped not run, no probe result given",
      r.returncode == 0 and raw_stamp("w-lone") == "not run — capture_probe.py is missing beside capture_write.py"
      and r2.returncode == 0 and raw_stamp("w-lone-pdf") == "not run — no probe result given")
shutil.rmtree(LONE_P)
LONE_B = tempfile.mkdtemp(prefix="cwtest-broken-check-")
for f in ("capture_write.py", "run_ledger.py"):
    shutil.copy(os.path.join(CWD, f), os.path.join(LONE_B, f))
_probe_src = open(os.path.join(CWD, "capture_probe.py"), encoding="utf-8").read() if cp is not None else ""
_guard = 'if __name__ == "__main__":\n'
open(os.path.join(LONE_B, "capture_probe.py"), "w", encoding="utf-8").write(_probe_src.replace(
    _guard, "_planted_check = check_capture\n\n\ndef check_capture(page_text, base_url, markdown):\n"
            "    if 'Visa terms' in page_text:\n        raise RuntimeError('planted check failure')\n"
            "    return _planted_check(page_text, base_url, markdown)\n\n\n" + _guard, 1))
r = run_lone(LONE_B, "--url", "https://x.test/terms", "--ledger-id", RID5, "--engine", ROUTE_ENGINE, "--slug", "w-check-raised",
             "--probe-result", ROUTED, stdin=COLLAPSED_BODY)
check("W10 must say not run: a check that fails to run (a probe beside the writer whose check raises on this page, its "
      "controls passing) is written, stamped not run with the failure, never no loss",
      _probe_src.count(_guard) == 1 and r.returncode == 0 and raw_stamp("w-check-raised").startswith(NOT_RUN)
      and "planted check failure" in raw_stamp("w-check-raised"))
shutil.rmtree(LONE_B)
U_M = "https://x.test/malformed"
LOST = 'collapsed text missing from the capture: "' + VISA + '"'
def mutated(name, change):
    result, d = probe_record(U_M, COLLAPSED_PAGE, ROUTE_ENGINE, route="ROUTE", capture=COLLAPSED_BODY)
    try:
        change(result)
    except (KeyError, TypeError):   # a record without the field (code with no probe): the leg fails, never crashes
        pass
    return save_record(result, d)
def drop(*keys):
    return lambda res: [res.pop(k, None) for k in keys]
def setf(path, value):
    def change(res):
        cur = res
        for k in path[:-1]:
            cur = cur[k]
        cur[path[-1]] = value
    return change
MUTATIONS = [
    ("its acquisition evidence removed (fetch, controls, converter, check)", drop("fetch", "controls", "converter", "check")),
    ("its fetch record removed", drop("fetch")),
    ("its controls removed", drop("controls")),
    ("its converter record removed", drop("converter")),
    ("its check record removed", drop("check")),
    ("its URL removed (never matched by an absent resolved URL)", drop("url")),
    ("its URL null", setf(("url",), None)),
    ("status pass kept over curl exit 18 under HTTP 200", setf(("fetch", "curl_exit"), 18)),
    ("a no-loss verdict kept over recorded findings", setf(("check", "failures"), [LOST])),
    ("a suspected-loss verdict with no findings", setf(("check", "verdict"), "suspected loss")),
    ("status pass kept over HTTP 404", setf(("fetch", "http_code"), 404)),
    ("a content type that is not HTML", lambda res: (setf(("fetch", "content_type"), "application/pdf")(res),
                                                      setf(("content_type",), "application/pdf")(res))),
    ("controls short of this probe's own", setf(("controls",), "1/2")),
    ("stage not done, a reason recorded", lambda res: res.update(stage="check", reason="planted")),
    ("a status that is neither pass nor fail", setf(("status",), "PASS")),
    ("the stopped admission design's schema", setf(("schema",), "capture-probe-result/1")),
    ("a probe recorded as failed at fetch that still names a fetched page",
     lambda res: res.update(status="fail", stage="fetch", reason="HTTP 404: planted")),
    ("a converter run that is not the route's", setf(("converter",), ["defuddle", "parse", "converted.html", "--markdown"])),
    ("markers that are not the page's", setf(("markers",), {"details": 9})),
    ("check counts that are not the page's", lambda res: res["check"].update(collapsed=res["check"]["collapsed"] + 1)),
    ("a base URL that is not the page's", setf(("base_url",), "https://elsewhere.test/")),
    ("a capture hash that is not capture.md's", setf(("capture_sha256",), "0" * 64)),
    ("an effective URL that disagrees with the fetch", setf(("effective_url",), "https://x.test/other")),
]
wrong = []
for i, (name, change) in enumerate(MUTATIONS):
    r = run5(U_M, ROUTE_ENGINE, f"w-malformed-{i}", "--probe-result", mutated(name, change), stdin=COLLAPSED_BODY)
    if r.returncode != 0 or not raw_stamp(f"w-malformed-{i}").startswith(NOT_RUN):
        wrong.append(name)
check(f"W11 each of {len(MUTATIONS)} malformed records refuses nothing: written, stamped not run, never no loss"
      + (f" (otherwise: {wrong})" if wrong else ""), not wrong)
r = run5(U_M, ROUTE_ENGINE, "w-malformed-control", "--probe-result", mutated("none", lambda res: None), stdin=COLLAPSED_BODY)
check("W11 control: the same record unmutated, complete and consistent, is read: no loss found",
      r.returncode == 0 and raw_stamp("w-malformed-control").startswith(NO_LOSS))
ENGINES = ("defuddle", "curl", "markitdown", None, "agent", "jina-reader", "Jina Reader (fallback)", "webfetch",
           "twitter-cli 0.8.5 via agent-reach")
got = []
for i, e in enumerate(ENGINES):
    r = run5("https://x.test/terms", e, f"w-engine-{i}", "--probe-result", ROUTED, stdin=COLLAPSED_BODY.replace(VISA, ""))
    got.append((e, r.returncode, raw_stamp(f"w-engine-{i}")))
check(f"W12 the engine plays no part: the same body and result under {len(ENGINES)} engine names (defuddle, curl, "
      "markitdown, none, an agent, Jina in three spellings, a platform CLI) are each written and stamped alike",
      all(rc == 0 and s == got[0][2] for _e, rc, s in got) and got[0][2].startswith(LOSS))
WHY_D = "a figure caption is flattened into the prose"
r = run5("https://x.test/terms", ROUTE_ENGINE, "w-declared", "--probe-result", ROUTED, "--allow-degraded", WHY_D, stdin=COLLAPSED_BODY)
check("W14 the declared-damage record is kept beside the stamp: capture_quality declared and capture_check no loss found, "
      "in frontmatter and ledger",
      r.returncode == 0 and "DEGRADED (declared)" in r.stdout and f'capture_quality: "declared — {WHY_D}"' in raw_body("w-declared")
      and raw_stamp("w-declared").startswith(NO_LOSS) and ledger5().get("degraded") == f"declared — {WHY_D}"
      and ledger5().get("capture_check", "").startswith(NO_LOSS))
r = run5("https://x.test/terms", ROUTE_ENGINE, "w-stub", "--probe-result", ROUTED, stdin=STUB)
check("W14 control: the quality gate still refuses an engine error stub whatever result is passed (nothing written)",
      r.returncode == 2 and "quality gate" in r.stderr and not raw_body("w-stub"))
PMC2 = "https://pmc.ncbi.nlm.nih.gov/articles/PMC0000002/"
OPEN_COPY = probe_result(PMC2, COLLAPSED_PAGE, ROUTE_ENGINE, route="ROUTE", capture=COLLAPSED_BODY)
r = run5("https://journal.test/doi/10.9999/res.2", ROUTE_ENGINE, "w-resolved", "--resolved-url", PMC2, "--probe-result", OPEN_COPY,
         stdin=COLLAPSED_BODY)
r2 = run5("https://journal.test/doi/10.9999/res.2", ROUTE_ENGINE, "w-unresolved", "--probe-result", OPEN_COPY, stdin=COLLAPSED_BODY)
check("W19 a result for the open copy is read for the write whose --resolved-url names it (no loss found), and is another "
      "page's result for a write that names no open copy (not run)",
      r.returncode == 0 and raw_stamp("w-resolved").startswith(NO_LOSS)
      and r2.returncode == 0 and raw_stamp("w-unresolved").startswith(NOT_RUN) and "is for" in raw_stamp("w-unresolved"))
RID7 = f"cwtest7-{uuid.uuid4().hex[:8]}"
rl.init(RID7, 2)
_bad = rl.load(rl.path_for(RID7)); _bad["probes"] = "not a list"; rl.save(rl.path_for(RID7), _bad)
r = run("write", "--url", "https://x.test/any", "--ledger-id", RID7, "--engine", "markitdown", "--slug", "w-bad-probes", stdin=GOOD)
check("W15 removed: the writer no longer reads a probes list in the run ledger; one that is not a list refuses nothing",
      r.returncode == 0 and raw_stamp("w-bad-probes") == "not run — no probe result given")
SRC_NOW = open(os.path.join(CWD, "capture_write.py"), encoding="utf-8").read()
GONE = [n for n in ("needs_probe", "recorded_probe", "probe_verdict", "WEB_FALLBACK_ENGINE", "PROBE_CONVERTER_ENGINE",
                    "probe_from", "completeness unprobed", "is refused without a passing") if n in SRC_NOW]
check("W16 removed: the writer keeps none of the stopped gate's code or texts (engine classes, the ledger binding, the "
      "refusal, completeness unprobed); control: its stamp helper is there" + (f" (still there: {GONE})" if GONE else ""),
      not GONE and "def capture_check_stamp(" in SRC_NOW)
SKILL_NOW = open(os.path.join(CWD, "SKILL.md"), encoding="utf-8").read()
check("W17 gather Writes says the capture check warns and never blocks, and no longer that a web page fails closed",
      "**The capture check warns and never blocks**" in SKILL_NOW and "fails closed" not in SKILL_NOW)
LINES = [ln for slug in ("w-noresult", "w-lost", "w-kept", "w-failed", "w-check-raised")
         for ln in raw_body(slug).split("\n---\n", 1)[0].splitlines() if ln.startswith("capture_check:")]
check("W18 the stamp is one double-quoted frontmatter line with no inner double quote or backslash",
      len(LINES) == 5 and all(re.fullmatch(r'capture_check: "[^"\\]*"', ln) for ln in LINES))
CLAIMS = re.compile(r"(?i)\b(?:verified|verify|clean|pass|passed|passes|faithful|complete|confirmed|valid|validated)\b")
OWN = [re.sub(r"(?<![A-Za-z])'[^']*'(?![A-Za-z])", "''", s) for s in STAMPS if s]   # quoted values are data
check("W13 no stamp reads as verified: every stamp written here (all three kinds) opens with suspected loss, no loss found "
      "by the unit check or not run, and none says verified, clean, complete, faithful or pass (control: the word list "
      "finds one in a planted sentence)",
      len(OWN) >= 30 and all(s.startswith((LOSS, NO_LOSS, NOT_RUN)) for s in STAMPS if s)
      and not [s for s in OWN if CLAIMS.search(s)] and {k for k in (LOSS, NO_LOSS, NOT_RUN) if any(s.startswith(k) for s in STAMPS)} == {LOSS, NO_LOSS, NOT_RUN}
      and CLAIMS.search("the capture is verified") is not None)

print("== dedup: the advisory host-and-final-slug key over raw provenance ==")
KV2 = tempfile.mkdtemp(prefix="cwtest-slug-")
def writer_raw(rel, title, url, engine="jina-reader", resolved=None):
    # the frontmatter shape capture_write.py writes (title, source_url, resolved_url, converted_from/by/on)
    put(KV2, rel, f'---\ntitle: "{title}"\nsource_url: {url}\n' + (f"resolved_url: {resolved}\n" if resolved else "")
        + f"converted_from: {url}\nconverted_by: {engine}\nconverted_on: 2026-10-02\n---\n\nBody of {title}.\n")
writer_raw("raw/articles/publisher-announcement.md", "Publisher: an announcement", "https://publisher.example/blog/some-announcement")
writer_raw("raw/docs/install-v1.md", "Install (v1)", "https://docs.example.org/v1/install", engine="defuddle")
writer_raw("raw/docs/guide-index.md", "Guide index", "https://docs.example.org/guide/index.html", engine="defuddle")
writer_raw("raw/shop/item-1.md", "Item 1", "https://shop.example.org/item?id=1", engine="defuddle")
writer_raw("raw/papers/open-copy.md", "Open copy", "https://journal.example.org/doi/10.1/abc", engine="markitdown",
           resolved="https://repository.example.edu/files/abc-preprint.pdf")
put(KV2, "wiki/sources/control.md", '---\ntitle: "Source: The Control Page Itself"\nsource_url: https://control.test/present\n---\n')
put(KV2, "wiki/sources/moved.md", '---\ntitle: "Source: a page cited at its old address"\nsource_url: https://publisher.example/news/some-announcement\n---\n')
def likely_for(r, url):
    m = re.search(r"(?m)^" + re.escape(url) + r" ~> (.*)$", r.stdout)
    return m.group(1) if m else ""
MOVED = "https://publisher.example/index/some-announcement/"
CANDS = [MOVED, "https://other.example/blog/some-announcement", "https://publisher.example/blog/another-announcement",
         "https://docs.example.org/v2/install", "https://docs.example.org/api/index.html", "https://shop.example.org/item?id=2",
         "https://WWW.Publisher.Example/News/Some-Announcement.HTML", "https://repository.example.edu/mirror/abc-preprint.pdf",
         "https://publisher.example/blog/some-announcement"]
r = runk(KV2, "--urls", *CANDS, *CTL)
check("S1 a publisher page at a moved address: the definitive verdict stays new and a second line names the likely duplicate",
      r.returncode == 0 and line_for(r, MOVED) == "new"
      and likely_for(r, MOVED).startswith("likely duplicate of raw/articles/publisher-announcement.md (same host and final slug")
      and "never exclude it" in likely_for(r, MOVED))
check("S2 control: the same slug on another host, and another slug on the same host, give no likely duplicate",
      likely_for(r, CANDS[1]) == "" and likely_for(r, CANDS[2]) == "" and line_for(r, CANDS[1]) == "new")
check("S3 versioned docs (/v1/install, /v2/install), a generic index page and a query-selected item stay advisory and selectable",
      all(line_for(r, u) == "new" and likely_for(r, u).startswith("likely duplicate of") for u in CANDS[3:6]))
check("S4 the key folds case, a leading www. and a .html ending", likely_for(r, CANDS[6]).startswith("likely duplicate of raw/articles/publisher-announcement.md"))
check("S5 the key reads resolved_url too (the writer's own provenance fields), and raw captures only, never a wiki page",
      "raw/papers/open-copy.md" in likely_for(r, CANDS[7]) and "resolved_url" in likely_for(r, CANDS[7])
      and "wiki/sources/moved.md" not in r.stdout)
check("S6 control: a definitive match is unchanged and not repeated as likely",
      line_for(r, CANDS[8]).startswith("ALREADY IN VAULT: raw/articles/publisher-announcement.md") and likely_for(r, CANDS[8]) == "")
# six distinct keys in these raws: publisher.example/some-announcement (source_url and converted_from alike),
# docs.example.org/install, docs.example.org/index, shop.example.org/item, journal.example.org/abc and,
# from resolved_url, repository.example.edu/abc-preprint.pdf
check("S7 the summary counts the host-and-slug keys", re.search(r"· 6 host-and-slug keys over raw/ \(advisory\)", r.stdout) is not None)
GATHER_SKILL_NOW = open(os.path.join(CWD, "SKILL.md"), encoding="utf-8").read()
check("S9 gather Step 1.3 keeps a likely duplicate on the menu, never excluded",
      "likely duplicate of <raw" in GATHER_SKILL_NOW and "never excluded and never" in GATHER_SKILL_NOW.replace("\n    ", " "))
shutil.rmtree(KV2)

print("== vault-root guard ==")
SCRIPT = os.path.join(CWD, "capture_write.py")
r = subprocess.run([sys.executable, SCRIPT, "dedup", "--urls", "https://nowhere.test/a",
                    "--allow-no-control"], capture_output=True, text=True, cwd=tempfile.gettempdir())
check("foreign cwd defaults to the script's vault", r.returncode == 0 and "-> new" in r.stdout)
BOGUS = tempfile.mkdtemp(prefix="cwtest-notavault-")
r = subprocess.run([sys.executable, SCRIPT, "dedup", "--urls", "x", "--allow-no-control",
                    "--vault-root", BOGUS], capture_output=True, text=True, cwd=CWD)
check("dedup refuses a non-vault root", r.returncode == 2 and "not a vault root" in r.stderr)
r = subprocess.run([sys.executable, SCRIPT, "write", "--url", "https://x.test/x", "--ledger-id", RID,
                    "--vault-root", BOGUS], input=GOOD, capture_output=True, text=True, cwd=CWD)
check("write refuses a non-vault root", r.returncode == 2 and "not a vault root" in r.stderr)

os.remove(rl.path_for(RID))
os.remove(rl.path_for(RID2))
os.remove(rl.path_for(RID3))
os.remove(rl.path_for(RID4))
os.remove(rl.path_for(RID5))
os.remove(rl.path_for(RID7))
for d in PROBE_DIRS:
    shutil.rmtree(d, ignore_errors=True)
import shutil; shutil.rmtree(VAULT); shutil.rmtree(BOGUS)
print(f"\n{P} passed, {F} failed")
sys.exit(1 if F else 0)
