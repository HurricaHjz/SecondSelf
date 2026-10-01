#!/usr/bin/env python3
"""Unit tests for capture_write.py — run: python3 test_capture_write.py"""
import json, os, subprocess, sys, tempfile, uuid
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
body = open(dest).read()
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
check("no resolved_url without the flag",    "resolved_url" not in open(os.path.join(VAULT, "raw", "one.md")).read())
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
import shutil; shutil.rmtree(VAULT); shutil.rmtree(BOGUS)
print(f"\n{P} passed, {F} failed")
sys.exit(1 if F else 0)
