#!/usr/bin/env python3
"""test_dedup_probe.py - the ingest de-dup probe on planted fixtures.

Run: python3 test_dedup_probe.py [path/to/dedup_probe.py]   (default: beside this file)
Legs replay the page-without-source_url case (a URL capture of arXiv 2307.03172 against a page compiled from a
local PDF with no source_url), each paper key alone, a similar-title negative control with its
positive control, the name / hash / URL keys the shell block had, the site-suffix legs (F9a-F9h: a
trailing site suffix keys like the bare title by its property, while family pages, short segments
sharing a word and long segments are not cut, and gather's capture_write.py loads the same key), the
review legs (G7a-G7f: a title that says it is a review never takes a stripped key that collapses it onto the
paper it reviews, while a review site's name or host proves no review and stays a candidate to inspect), the
premise failures, and a last leg proving the probe wrote nothing. Fixtures live under one mkdtemp,
removed at the end.
The lookup legs (L1-L7) test the --lookup verb, in its source-page mode, against literal citations:
MATCH only on a canonical identifier one work page asserts, every lossy key, location, companion page,
conflict or shared identifier a CANDIDATE, a key held only in a raw file no match (raw files are not
searched), coverage counted by source page after extraction, no verdict after a failed premise,
list/single parity, the query skill's membership step (default ../query/SKILL.md beside this skill, or
the second argument), one index per batch and a read-only run. The review-fold legs (R1-R5, R6f) hold
the lookup's closed reviews: one matching identifier never vouches for a conflicting one, frontmatter is
read as YAML reads it or refused, the controls fit the evidence an index holds, coverage counts pages as
unions that the index summary repeats, and a value YAML reads over several lines never makes a field of
its own. The reader legs (Y1s-Y6, Z2f, Z4) hold the PyYAML BaseLoader reader on source pages: the review
fixtures each give YAML's reading or exit 2, forms YAML readers part on are refused (only a real merge
key, never a << quoted or tagged !!str), and a missing PyYAML stops the lookup while the de-dup probe
runs without it. The source-page legs (S1-S5) hold the mode itself: nothing under raw/ is opened or
listed, every run says raw files are not searched, the raw-join flag is gone, every failing page is
named, and a page whose line ends the reader cannot see exits 2.
  python3 test_dedup_probe.py [path/to/dedup_probe.py] [path/to/query/SKILL.md]
Ends `PASS n/n` or `FAIL k/n`.
"""
import hashlib, importlib.util, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "dedup_probe.py")
TMP = tempfile.mkdtemp(prefix="dedup-probe-test-")
P = F = 0


def check(name, cond, detail=""):
    global P, F
    if cond:
        P += 1
        print(f"ok   {name}")
    else:
        F += 1
        print(f"FAIL {name}" + ("\n     " + detail.strip().replace("\n", "\n     ") if detail else ""))


TITLE = '"Paper: Lost in the Middle — How Language Models Use Long Contexts"'
ABS = "https://arxiv.org/abs/2307.03172"
PAGE_REL = "wiki/sources/lost-in-the-middle.md"


def fm(**kv):
    return "\n".join(["---"] + [f"{k}: {v}" for k, v in kv.items() if v is not None] + ["---", "", "body text", ""])


def page(source_url=None, doi='"10.1162/tacl_a_00638"', source_hash='"0123456789abcdef"'):
    # the frontmatter shape of the page the defect missed: compiled from a local PDF, so doi and
    # source_hash but (before its backfill) no source_url
    return fm(title=TITLE, type="source", depth="research", confidence="authoritative   # peer-reviewed venue",
              year="2024", doi=doi, sources="[raw/2-papers/lost-in-the-middle.pdf, raw/2-papers/lost-in-the-middle.md]",
              source_url=source_url, source_hash=source_hash, created="2026-07-21") + "## Related\n"


def base(**page_kw):
    return {PAGE_REL: page(**page_kw),
            "raw/2-papers/lost-in-the-middle.md": "---\nconverted_from: local.pdf\nconverted_by: markitdown\n---\n\n"
                                                  "Lost in the Middle: How Language Models Use Long Contexts\n"}


CAPTURE = fm(title=TITLE, source_url=ABS, converted_from=ABS, converted_by="markitdown", converted_on="2026-09-04")


def mkvault(name, files):
    v = os.path.join(TMP, name)
    os.makedirs(os.path.join(v, "raw"), exist_ok=True)
    os.makedirs(os.path.join(v, "wiki", "sources"), exist_ok=True)
    for rel, text in files.items():
        p = os.path.join(v, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb" if isinstance(text, bytes) else "w", **({} if isinstance(text, bytes) else {"encoding": "utf-8"})) as fh:
            fh.write(text)
    return v


def run(v, cand, *extra):
    return subprocess.run([sys.executable, "-B", PROBE, cand, "--vault-root", v, *extra], capture_output=True, text=True)


def cands(r):
    return {m.group(1): m.group(2) for m in re.finditer(r"(?m)^CANDIDATE (\S+) \[(.*)\]$", r.stdout)}


def out(r):
    return f"exit {r.returncode}\n{r.stdout}{r.stderr}"


# NAME_PREFIX_TESTS_BEGIN
print("== leading paper names and later-dash controls ==")
DCPO_TITLE = "Decoupling Reasoning and Confidence: Resurrecting Calibration in Reinforcement Learning from Verifiable Rewards"
prefix_page = "wiki/sources/prefixed-paper.md"
for label, prefix in (("P1", "Source: DCPO — "), ("P2", "Paper: DCPO - "),
                      ("P3", "DCPO—")):
    v = mkvault(label.lower(), {
        prefix_page: fm(title=prefix + DCPO_TITLE, source_url="https://openreview.net/forum?id=fixture",
                        source_hash="0123456789abcdef"),
        "raw/candidate.md": fm(title=DCPO_TITLE, source_url="https://arxiv.org/abs/2603.09117"),
        "raw/different.md": fm(title="Calibration Methods for Unrelated Prediction Tasks")})
    r = run(v, "raw/candidate.md")
    check(f"{label} a leading name matches the bare title on title alone",
          r.returncode == 0 and set(cands(r)) == {prefix_page}
          and cands(r)[prefix_page] in ("title", "name-stripped title"), out(r))
    r = run(v, "raw/different.md")
    check(f"{label} unrelated title stays NEW beside the matching positive control",
          r.returncode == 0 and r.stdout.startswith("NEW") and not cands(r) and "controls:" in r.stdout, out(r))

prefix_spec = importlib.util.spec_from_file_location("dedup_prefix", PROBE)
prefix_mod = importlib.util.module_from_spec(prefix_spec)
sys.dont_write_bytecode = True
prefix_spec.loader.exec_module(prefix_mod)
later = "Paper: Lost in the Middle — How Language Models Use Long Contexts"
check("P4 a later em dash leaves the full title key unchanged",
      prefix_mod.title_key(later) == "lost middle how language models use long contexts")
check("P5 a later spaced hyphen leaves the full title key unchanged",
      prefix_mod.title_key(later.replace("—", "-")) == "lost middle how language models use long contexts")
check("P6 unspaced word hyphens stay in the title",
      prefix_mod.title_key("Plug-and-Play Positional Encoding for Long Contexts") ==
      "plug play positional encoding long contexts")
named_key = prefix_mod.title_key("Source: DCPO — " + DCPO_TITLE)
bare_key = prefix_mod.title_key(DCPO_TITLE)
check("P7 the full title survives beside a separate name-stripped key",
      named_key == "dcpo " + bare_key and getattr(named_key, "name_stripped", None) == bare_key)

# T is a paper title above the existing token floor; MethodA and MethodB are distinct names.
TITLE_T = "Calibrated Reasoning and Confidence Estimates"
name_cases = [
    ("P8a full key still matches a colon title", "Source: X — " + TITLE_T, "X: " + TITLE_T, "title"),
    ("P8b a two-word remainder keeps its full key", "Source: X — two words", "X two words", "title"),
    ("P8c distinct names never meet on stripped keys", "MethodA — " + TITLE_T, "MethodB — " + TITLE_T, None),
    ("P9 genuine one-word lead-ins stay distinct", "Overconfidence — Why Large Language Models Misjudge Their Own Answers",
     "Underconfidence — Why Large Language Models Misjudge Their Own Answers", None),
    ("P10a en dash", "DCPO – " + DCPO_TITLE, DCPO_TITLE, "name-stripped title"),
    ("P10b double hyphen", "DCPO -- " + DCPO_TITLE, DCPO_TITLE, "name-stripped title"),
    ("P10c arXiv prefix before the name", "[2603.09117] DCPO — " + DCPO_TITLE, DCPO_TITLE, "name-stripped title"),
    ("P10d name-stripped never meets suffix-stripped", "X — " + TITLE_T, TITLE_T + " | Venue", None),
]
for number, (label, left, right, expected) in enumerate(name_cases):
    for direction, (page_title, candidate_title) in enumerate(((left, right), (right, left))):
        v = mkvault("dual-%d-%d" % (number, direction), {
            prefix_page: fm(title=page_title, source_hash="0123456789abcdef"),
            "raw/candidate.md": fm(title=candidate_title),
            "raw/control.pdf": b"%PDF-1.4 positive-control fixture\n"})
        r = run(v, "raw/candidate.md")
        wanted = {prefix_page: expected} if expected else {}
        check(label + " direction " + str(direction),
              r.returncode == 0 and cands(r) == wanted
              and (expected is not None or r.stdout.startswith("NEW")), out(r))
        control = run(v, "raw/control.pdf", "--title", page_title)
        check(label + " same-vault full-title control " + str(direction),
              control.returncode == 0 and cands(control).get(prefix_page) == "title", out(control))

short_key = prefix_mod.title_key("Source: X — two words")
check("P11 a stripped remainder below the token floor is not keyed",
      short_key == "x two words" and getattr(short_key, "name_stripped", None) is None)
name_controls = [row for row in prefix_mod.SELF_TEST if row[0] == "name-stripped" and row[2] is not None]
check("P12 the self-test catches a dead name stripper and passes the real one",
      bool(name_controls) and len(prefix_mod.self_test({"name-stripped": lambda title: None})) == len(name_controls)
      and prefix_mod.self_test() == [])
# NAME_PREFIX_TESTS_END

print("== the defect's own case ==")
v = mkvault("d1", {**base(), "raw/paper-lost-in-the-middle.md": CAPTURE})
r = run(v, "raw/paper-lost-in-the-middle.md")
c = cands(r)
check("D1 URL capture vs PDF-compiled page matches on the title alone", r.returncode == 0 and c.get(PAGE_REL) == "title", out(r))
check("D1 none of the block's keys (name, hash, url) carried it", not re.search(r"\b(name|hash|url)\b", c.get(PAGE_REL, "name")), out(r))

print("== each paper key alone ==")
v = mkvault("d2", {**base(source_url=f'"{ABS}"'), "raw/arxiv-org-pdf-2307-03172v3.md":
                   fm(title="arxiv-org-pdf-2307-03172v3", source_url="https://arxiv.org/pdf/2307.03172v3")})
r = run(v, "raw/arxiv-org-pdf-2307-03172v3.md")
check("D2 pdf-form URL matches the backfilled page on the arXiv id alone", cands(r).get(PAGE_REL) == "arxiv 2307.03172", out(r))
v = mkvault("d2b", {**base(doi='"10.48550/arXiv.2307.03172"'), "raw/lost.pdf": b"%PDF-1.4 not text\n"})
r = run(v, "raw/lost.pdf", "--url", "arXiv:2307.03172")
check("D2b arXiv id matches an arXiv DOI in doi: frontmatter", cands(r).get(PAGE_REL) == "arxiv 2307.03172", out(r))
v = mkvault("d3", {**base(), "raw/doi-org-10-1162-tacl-a-00638.md":
                   fm(title="doi-org-10-1162-tacl-a-00638", source_url="https://doi.org/10.1162/TACL_A_00638")})
r = run(v, "raw/doi-org-10-1162-tacl-a-00638.md")
check("D3 resolver URL matches doi: frontmatter on the DOI alone (case-folded)", cands(r).get(PAGE_REL) == "doi 10.1162/tacl_a_00638", out(r))
v = mkvault("d3b", {**base(), "raw/lost.pdf": b"%PDF-1.4 not text\n"})
r = run(v, "raw/lost.pdf", "--doi", "10.1162/TACL_a_00638")
check("D3b --doi on a PDF candidate matches on the DOI", cands(r).get(PAGE_REL) == "doi 10.1162/tacl_a_00638", out(r))
v = mkvault("d4", {**base(), "raw/hyphenated.md": fm(title='"Lost-in-the-Middle: How Language-Models Use Long Contexts"')})
r = run(v, "raw/hyphenated.md")
check("D4 title matches with hyphens, colon and label unified", cands(r).get(PAGE_REL) == "title", out(r))

print("== negative control: similar titles, near-miss ids (must stay NEW) ==")
neg = {"raw/paper-found-in-the-middle.md": fm(title='"Paper: Found in the Middle — How Language Models Use Long Contexts Better via Plug-and-Play Positional Encoding"',
                                              source_url="https://arxiv.org/abs/2403.04797"),
       "raw/near-id.md": fm(title="arxiv-org-abs-2307-03173", source_url="https://arxiv.org/abs/2307.03173"),
       "raw/near-doi.pdf": b"%PDF-1.4 not text\n",
       "raw/short-title.md": fm(title='"Lost in the Middle"'),
       "raw/extra-words.md": fm(title='"Lost in the Middle: How Language Models Use Long Contexts at Scale"'),
       "raw/paper-lost-in-the-middle.md": CAPTURE}
v5 = mkvault("d5", {**base(source_url=f'"{ABS}"'), **neg})
for cand, extra, label in [("raw/paper-found-in-the-middle.md", [], "D5a similar title, other arXiv id"),
                           ("raw/near-id.md", [], "D5b arXiv id one digit off"),
                           ("raw/near-doi.pdf", ["--doi", "10.1162/tacl_a_0063"], "D5c DOI one character short"),
                           ("raw/extra-words.md", [], "D5e same title plus two words")]:
    r = run(v5, cand, *extra)
    check(f"{label} -> NEW", r.returncode == 0 and r.stdout.startswith("NEW") and not cands(r), out(r))
r = run(v5, "raw/short-title.md")
check("D5d a two-token title is not keyed and says so", r.returncode == 0 and r.stdout.startswith("NEW") and "not keyed" in r.stdout, out(r))
r = run(v5, "raw/paper-lost-in-the-middle.md")
c = cands(r)
check("D5 positive control on the same vault: the real duplicate is a CANDIDATE",
      "arxiv 2307.03172" in c.get(PAGE_REL, "") and "title" in c.get(PAGE_REL, ""), out(r))

print("== the block's own keys (parity) ==")
v = mkvault("d6", {**base(), "raw/7-reviews/paper-x.md": fm(title="slug-a"), "raw/paper-x.md": fm(title="slug-b"),
                   "wiki/sources/post.md": fm(title='"Source: A Post Citing Its Link"') + "See https://example.test/post\n",
                   "raw/hashed.md": fm(title="slug-c")})
with open(os.path.join(v, "raw", "hashed.md"), "rb") as fh:
    h16 = hashlib.sha256(fh.read()).hexdigest()[:16]
mkvault("d6", {"wiki/sources/hashed-page.md": fm(title='"Source: The Hashed Page Here"', source_hash=f'"{h16}"')})
r = run(v, "raw/paper-x.md")
check("D6 name key: same name in a raw/ subfolder, never the candidate itself",
      cands(r).get("raw/7-reviews/paper-x.md") == "name" and "raw/paper-x.md" not in cands(r), out(r))
r = run(v, "raw/hashed.md")
check("D6 hash key: the candidate's sha256 prefix in a source page", cands(r).get("wiki/sources/hashed-page.md") == "hash", out(r))
r = run(v, "raw/paper-x.md", "--url", "https://example.test/post")
check("D6 url key: the URL anywhere in a source page", cands(r).get("wiki/sources/post.md") == "url https://example.test/post", out(r))

print("== a trailing site suffix on a title (review F9, 2026-09-13): found by its property, never a site list ==")
BARE = "Lost in the Middle: How Language Models Use Long Contexts"
HUB_TITLE = "Long Context Benchmarks for Language Models | Long Context Hub"
SUF = "suffix-stripped title"
v9 = mkvault("f9", {
    **base(),
    "raw/capture-arxiv.md": fm(title=f'"{BARE} | arXiv"'),
    "raw/capture-pmc.md": fm(title=f'"{BARE} - PMC"'),
    "raw/capture-scholar.md": fm(title=f'"{BARE} – Semantic Scholar"'),
    "raw/lost.pdf": b"%PDF-1.4 not text\n",
    "wiki/sources/widget-output-styles.md": fm(title='"Source: Widget SDK docs — Output styles"'),
    "wiki/sources/widget-sessions.md": fm(title='"Source: Widget SDK docs — Sessions"'),
    "raw/widget-guardrails.md": fm(title='"Widget SDK docs — Guardrails"'),
    "raw/widget-sessions.md": fm(title='"Widget SDK docs — Sessions"'),
    "wiki/sources/attention-heads.md": fm(title='"Paper: Attention Heads in Transformer Models"'),
    "raw/attention-sinks.md": fm(title='"Attention Heads in Transformer Models - Attention Sinks"'),
    "wiki/sources/large-language-models.md": fm(title='"Paper: Large Language Models"'),
    "raw/long-subtitle.md": fm(title='"Large Language Models - How They Use Long Contexts"'),
    "wiki/sources/rag-code-survey.md": fm(title='"Paper: Retrieval Augmented Generation for Code: A Survey"'),
    "raw/rag-code-survey-dash.md": fm(title='"Retrieval Augmented Generation for Code - A Survey"'),
    "wiki/sources/long-context-benchmarks.md": fm(title='"Paper: Long Context Benchmarks for Language Models"'),
    "raw/hub-own-host.md": fm(title=f'"{HUB_TITLE}"', source_url="https://longcontexthub.test/papers/1"),
    "raw/hub-other-host.md": fm(title=f'"{HUB_TITLE}"', source_url="https://mirror.example.test/papers/1"),
})
for cand, label in [("raw/capture-arxiv.md", "`| arXiv`"), ("raw/capture-pmc.md", "`- PMC`"),
                    ("raw/capture-scholar.md", "`– Semantic Scholar` (en dash, two words)")]:
    r = run(v9, cand)
    check(f"F9a a {label} capture keys like the bare title: it matches the PDF-compiled page", cands(r) == {PAGE_REL: SUF}, out(r))
r = run(v9, "raw/lost.pdf", "--title", BARE)
c = cands(r)
check("F9b the bare title matches each site-suffixed capture, and the page on the title in full",
      c.get(PAGE_REL) == "title" and all(c.get(p) == SUF for p in ("raw/capture-arxiv.md", "raw/capture-pmc.md", "raw/capture-scholar.md")), out(r))
r = run(v9, "raw/widget-guardrails.md")
check("F9c must not fire: pages of one family never meet on their shared stem (`Widget SDK docs — …`)",
      r.returncode == 0 and r.stdout.startswith("NEW") and not cands(r), out(r))
r = run(v9, "raw/widget-sessions.md")
check("F9c positive control in the same vault: the same-titled family page matches in full, its sibling does not",
      cands(r) == {"wiki/sources/widget-sessions.md": "title"}, out(r))
for cand, label in [("raw/attention-sinks.md", "a short segment sharing a content word (`- Attention Sinks`)"),
                    ("raw/long-subtitle.md", "a long segment (`- How They Use Long Contexts`)")]:
    r = run(v9, cand)
    check(f"F9d must not fire: a genuine title with a spaced dash inside, {label}, is not cut",
          r.returncode == 0 and r.stdout.startswith("NEW") and not cands(r), out(r))
r = run(v9, "raw/rag-code-survey-dash.md")
check("F9d no match lost: `… - A Survey` still matches `…: A Survey` on the title in full",
      cands(r) == {"wiki/sources/rag-code-survey.md": "title"}, out(r))
r = run(v9, "raw/hub-own-host.md")
check("F9e a suffix sharing content words is stripped when it names a host label of the record's own URL",
      cands(r).get("wiki/sources/long-context-benchmarks.md") == SUF, out(r))
r = run(v9, "raw/hub-other-host.md")
c = cands(r)
check("F9e must not fire: the same title from another host is not stripped (its twin capture still matches in full)",
      "wiki/sources/long-context-benchmarks.md" not in c and c.get("raw/hub-own-host.md") == "title", out(r))

spec9 = importlib.util.spec_from_file_location("dedup_probe_f9", PROBE)
m9 = importlib.util.module_from_spec(spec9)
sys.dont_write_bytecode = True
spec9.loader.exec_module(m9)


def stripped_of(title):
    k = m9.title_key(title)
    return getattr(k, "suffix_stripped", None) if k else "unkeyed"


premise = [("Lost in the Middle | arXiv", None),          # the rest is under the key floor: nothing to strip to
           ("| arXiv", "unkeyed"), ("arXiv", "unkeyed"), ("", "unkeyed"), (None, "unkeyed"),
           (f"{BARE} |", None),                           # a delimiter with no segment after it
           (f"{BARE} - The", None),                       # a segment of stop words only
           ("Plug-and-Play Positional Encoding for Long Contexts", None),   # unspaced hyphens join words
           (f"Chapter One - {BARE} - PMC", "chapter one lost middle how language models use long contexts")]
got = [(t, stripped_of(t)) for t, _ in premise]
check("F9f premise attacks: no rest to key, no segment, stop words only, unspaced hyphens, empty and None; only the final segment goes",
      [g for _, g in got] == [e for _, e in premise], repr(got))
try:
    hl = m9.host_labels(["not a url", "http://[bad", "", None, "https://www.PMC.ncbi.nlm.nih.gov/articles/x"])
except Exception as e:
    hl = f"error: {e!r}"
check("F9f host labels: junk URLs skipped without an error; www and the top-level label dropped", hl == {"pmc", "ncbi", "nlm", "nih"}, repr(hl))
try:
    planted9, real9 = m9.self_test({"stripped": lambda t: None}), m9.self_test()
except Exception as e:
    planted9, real9 = f"error: {e!r}", None
check("F9g the self-test both probes run catches a planted dead suffix stripper, and passes the real one",
      isinstance(planted9, list) and len(planted9) == 2 and real9 == [], repr(planted9))

# G7: a title that says it is a review never takes a stripped key that collapses it onto the paper it reviews.
# A review site's name or host says where a page lives, never what it is, so those stay candidates to inspect.
REVIEW_TITLES = [f"{BARE} | Review", f"{BARE} | Peer review", f"{BARE} - Reviews", f"{BARE} | Peer Reviews"]
got7 = {t: stripped_of(t) for t in REVIEW_TITLES}
check("G7a a suffix that says review keeps no stripped key, so the full key stays apart from the paper's",
      all(v is None for v in got7.values()) and all(str(m9.title_key(t)) != str(m9.title_key(BARE)) for t in REVIEW_TITLES), repr(got7))
hosted7 = m9.title_key(f"{BARE} | ICLR 2027", m9.host_labels(["https://openreview.net/forum?id=abc"]))
check("G7b a record carried by the review site keeps its stripped key: a host says nothing of the page's kind",
      getattr(hosted7, "suffix_stripped", None) == str(m9.title_key(BARE)), repr(getattr(hosted7, "suffix_stripped", None)))
check("G7c controls: a site suffix on a paper still cuts, on the same title and from the same stripper, and a venue merely holding the word still cuts",
      stripped_of(f"{BARE} | arXiv") == str(m9.title_key(BARE)) and stripped_of(f"{BARE} | Annual Reviews") == str(m9.title_key(BARE)),
      repr((stripped_of(f"{BARE} | arXiv"), stripped_of(f"{BARE} | Annual Reviews"))))
named7 = [m9.strip_name_prefix(f"{w} — {BARE}") for w in ("Review", "OpenReview")]
check("G7d a leading name that says review is not stripped, and a review site's is, as another name is",
      named7 == [None, str(m9.title_key(BARE))] and m9.strip_name_prefix(f"METHOD — {BARE}") == str(m9.title_key(BARE)), repr(named7))
v7 = tempfile.mkdtemp(prefix="g7-", dir=TMP)
os.makedirs(os.path.join(v7, "raw")); os.makedirs(os.path.join(v7, "wiki", "sources"))
with open(os.path.join(v7, "wiki", "sources", "the-paper.md"), "w", encoding="utf-8") as fh:
    fh.write(fm(title=f'"Paper: {BARE}"', source_hash='"0123456789abcdef"'))
for name, title in (("review-of-it.md", f"{BARE} | Peer review"), ("site-of-it.md", f"{BARE} | OpenReview"), ("copy-of-it.md", f"{BARE} | arXiv")):
    with open(os.path.join(v7, "raw", name), "w", encoding="utf-8") as fh:
        fh.write(fm(title=f'"{title}"'))
r7 = subprocess.run([sys.executable, "-B", PROBE, "raw/review-of-it.md", "--vault-root", v7], capture_output=True, text=True, cwd=TMP)
s7 = subprocess.run([sys.executable, "-B", PROBE, "raw/site-of-it.md", "--vault-root", v7], capture_output=True, text=True, cwd=TMP)
c7 = subprocess.run([sys.executable, "-B", PROBE, "raw/copy-of-it.md", "--vault-root", v7], capture_output=True, text=True, cwd=TMP)
check("G7e end to end: a capture that says it is a review is NEW beside the paper's page; an OpenReview capture, which may be either, is a CANDIDATE on that page, never NEW; control: an arXiv capture of the same title is a CANDIDATE too",
      r7.returncode == 0 and r7.stdout.startswith("NEW")
      and s7.returncode == 0 and "CANDIDATE wiki/sources/the-paper.md" in s7.stdout and "suffix-stripped title" in s7.stdout
      and c7.returncode == 0 and "CANDIDATE wiki/sources/the-paper.md" in c7.stdout,
      r7.stdout + r7.stderr + s7.stdout + s7.stderr + c7.stdout + c7.stderr)
site7 = [f"{BARE} | OpenReview", f"{BARE} - OpenReview.net", f"{BARE} | Open Review", f"OpenReview — {BARE}"]
none7 = [BARE, f"{BARE} | arXiv", f"{BARE} | Peer review", f"METHOD — {BARE}", f"OpenReview Findings Across Many Long Reports"]
names7 = getattr(m9, "names_review_site", lambda t: False)   # on a matcher without it the leg fails, never crashes
check("G7f names_review_site reads a review site's name as a final segment or a leading name, and nothing else; each suffixed form keeps the paper's stripped key",
      all(names7(t) for t in site7) and not any(names7(t) for t in none7)
      and all(stripped_of(t) == str(m9.title_key(BARE)) for t in site7[:3]),
      repr([t for t in site7 if not names7(t)] + [t for t in none7 if names7(t)]))

GATHER = os.path.normpath(os.path.join(os.path.dirname(PROBE), "..", "gather", "capture_write.py"))
if os.path.isfile(GATHER):
    TITLES9 = [f"{BARE} | arXiv", f"{BARE} - PMC", "Widget SDK docs — Handoffs",
               "Found in the Middle: How Language Models Use Long Contexts Better | arXiv"]
    r = subprocess.run([sys.executable, "-B", GATHER, "dedup", "--vault-root", v9, "--titles", *TITLES9,
                        "--control", "https://longcontexthub.test/papers/1"], capture_output=True, text=True, cwd=TMP)
    lines = {t: (re.search(r'(?m)^title "' + re.escape(t) + r'" -> (.*)$', r.stdout) or [None, ""])[1] for t in TITLES9}
    check("F9h gather's `capture_write.py dedup --titles` loads the same key: both suffixed titles reach the page",
          r.returncode == 0 and all(PAGE_REL in lines[t] and SUF in lines[t] for t in TITLES9[:2]), out(r))
    check("F9h must not fire in gather: a family title and another paper's suffixed title stay new",
          r.returncode == 0 and lines[TITLES9[2]] == "new" and lines[TITLES9[3]] == "new", out(r))
    vn = mkvault("gather-names", {
        prefix_page: fm(title="Source: DCPO — " + DCPO_TITLE, source_hash="0123456789abcdef",
                        source_url="https://example.test/name-control"),
        "wiki/sources/plain-paper.md": fm(title=TITLE_T),
        "wiki/sources/other-name.md": fm(title="MethodA — " + TITLE_T)})
    names = [DCPO_TITLE, "X — " + TITLE_T, "MethodB — " + DCPO_TITLE]
    r = subprocess.run([sys.executable, "-B", GATHER, "dedup", "--vault-root", vn, "--titles", *names,
                        "--control", "https://example.test/name-control"], capture_output=True, text=True, cwd=TMP)
    lines = {t: (re.search(r'(?m)^title "' + re.escape(t) + r'" -> (.*)$', r.stdout) or [None, ""])[1] for t in names}
    check("P13 gather carries the separate name key into lookup in both directions",
          r.returncode == 0 and prefix_page in lines[names[0]] and "name-stripped title" in lines[names[0]]
          and "wiki/sources/plain-paper.md" in lines[names[1]]
          and "name-stripped title" in lines[names[1]], out(r))
    check("P13 gather never matches two name-stripped titles, with matching controls beside them",
          r.returncode == 0 and "wiki/sources/other-name.md" not in lines[names[1]]
          and lines[names[2]] == "new", out(r))
else:
    check("F9h gather's capture_write.py beside this skill", False, f"needs: {GATHER} (the gather skill ships beside ingest)")

print("== premise failures (exit 2, PROBE FAILED on stdout, never NEW) ==")
bogus = tempfile.mkdtemp(prefix="notavault-", dir=TMP)
r = run(bogus, "raw/x.md")
check("D7a non-vault root", r.returncode == 2 and r.stdout.startswith("PROBE FAILED") and "not a vault root" in r.stdout, out(r))
r = run(v5, "raw/missing.md")
check("D7b missing candidate", r.returncode == 2 and "not found" in r.stdout and "NEW" not in r.stdout, out(r))
v = mkvault("d7c", {"wiki/sources/p.md": fm(title='"Source: A Page Without Hash"'), "raw/c.md": CAPTURE})
r = run(v, "raw/c.md")
check("D7c no source_hash in wiki/sources/ -> control failed", r.returncode == 2 and "control found nothing" in r.stdout, out(r))
v = os.path.join(TMP, "d7d")
os.makedirs(os.path.join(v, "raw"))
os.makedirs(os.path.join(v, "wiki"))
with open(os.path.join(v, "raw", "c.md"), "w", encoding="utf-8") as fh:
    fh.write(CAPTURE)
r = run(v, "raw/c.md")
check("D7d wiki/sources/ missing", r.returncode == 2 and "wiki/sources/ missing" in r.stdout, out(r))
v = mkvault("d7e", {"wiki/sources/p.md": fm(source_hash='"0123456789abcdef"'), "raw/c.md": fm(source_url=ABS)})
r = run(v, "raw/c.md")
check("D7e nothing titled to index -> title key searched nothing", r.returncode == 2 and "no title keyed" in r.stdout, out(r))
v = mkvault("d7f", {**base(), "raw/c.md": CAPTURE, "raw/locked/inner.md": fm(title="x")})
locked = os.path.join(v, "raw", "locked")
os.chmod(locked, 0)
try:
    r = run(v, "raw/c.md")
finally:
    os.chmod(locked, 0o755)
check("D7f an unreadable raw/ subfolder fails the probe", r.returncode == 2 and "unreadable" in r.stdout, out(r))
spec = importlib.util.spec_from_file_location("dedup_probe_under_test", PROBE)
mod = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(mod)
planted = mod.self_test({"arxiv": mod.arxiv_ids, "doi": lambda s: set(), "title": mod.normalise_title})
check("D7g the self-test catches a planted dead DOI extractor, and passes the real one", len(planted) == 2 and mod.self_test() == [], repr(planted))

print("== the probe wrote nothing ==")
ro = os.path.join(TMP, "readonly")
shutil.copytree(v5, ro)


def manifest(top):
    rows = []
    for root, dirs, files in os.walk(top):
        dirs.sort()
        rows.append(("dir", os.path.relpath(root, top), tuple(sorted(dirs + files))))
        for f in sorted(files):
            p = os.path.join(root, f)
            with open(p, "rb") as fh:
                rows.append(("file", os.path.relpath(p, top), os.stat(p).st_mtime_ns, hashlib.sha256(fh.read()).hexdigest()))
    return rows


before = manifest(ro)
for root, dirs, files in os.walk(ro):
    for f in files:
        os.chmod(os.path.join(root, f), 0o444)
    os.chmod(root, 0o555)
runs = [run(ro, "raw/paper-lost-in-the-middle.md"), run(ro, "raw/paper-found-in-the-middle.md"), run(ro, "raw/missing.md")]
after = manifest(ro)
check("D8 runs on the read-only copy behaved (CANDIDATE, NEW, PROBE FAILED)",
      bool(cands(runs[0])) and runs[1].stdout.startswith("NEW") and runs[2].returncode == 2, "".join(out(x) for x in runs))
check("D8 checksum manifest identical before and after", before == after and len(before) > 5, f"{len(before)} rows before, {len(after)} after")
WRITES = re.compile(r"""open\([^,()]+,\s*['"][rbt]*[wax+][rwaxbt+]*['"]|mode\s*=\s*['"][rbt]*[wax+]"""
                    r"""|os\.(?:replace|rename|remove|unlink|makedirs|mkdir|rmdir|chmod|utime|truncate)\("""
                    r"""|shutil\.|\.write(?:_text|_bytes)?\(|\.(?:touch|unlink)\(""")
with open(PROBE, encoding="utf-8") as fh:
    probe_hits = WRITES.findall(fh.read())
control = 'open(p, "w")\nos.replace(a, b)\nshutil.rmtree(d)\nfh.write(x)\n'
check("D8 write-pattern grep: 0 hits in the probe source, control snippet hits 4",
      probe_hits == [] and len(WRITES.findall(control)) == 4, f"probe hits {probe_hits}; control hits {WRITES.findall(control)}")

# ================================================================================================
# The lookup verb (--lookup): "is this work in the vault?". The legs follow the design review's
# admission conditions: MATCH establishes work identity (L1); candidates keep uncertainty and
# multiplicity (L2); coverage describes the effective index (L3); a failed premise gives no verdict
# (L4); a list keeps the single-work contract (L5); the query skill keeps the limits of the result
# (L6); the mode is bounded and read-only (L7). Every leg here fails on a probe without the verb.
# The six historical works are public papers whose pages a membership grep once reported as not held.
# Run: python3 test_dedup_probe.py [dedup_probe.py] [query/SKILL.md]
# The verb ships in its source-page mode: it reads wiki/sources/ only and says that raw files are not
# searched, so each leg that needed the raw join is left out or asks for that answer (S1-S5).
# ================================================================================================
import contextlib, io, json, shlex

QUERY_SKILL = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.normpath(
    os.path.join(os.path.dirname(PROBE), "..", "query", "SKILL.md"))
LOOKUP_OUTPUTS = []
BANNED = re.compile(r"\babsent\b|\bmissing\b|not in the vault|not held", re.I)


def lk_load():
    try:
        spec_l = importlib.util.spec_from_file_location("dedup_probe_lookup", PROBE)
        mod_l = importlib.util.module_from_spec(spec_l)
        sys.dont_write_bytecode = True
        spec_l.loader.exec_module(mod_l)
        mod_l.lookup_main  # the verb under test; AttributeError on a probe without it
        return mod_l
    except Exception as e:
        print(f"     (module without the lookup verb: {e!r})")
        return None


def lrun(v, *args):
    r = subprocess.run([sys.executable, "-B", PROBE, "--lookup", "--vault-root", v, *args], capture_output=True, text=True)
    LOOKUP_OUTPUTS.append(r.stdout + r.stderr)
    return r


def blocks(stdout):
    """[(header, [verdict lines])] for each citation block of a lookup run."""
    out = []
    for line in stdout.splitlines():
        if line.startswith("citation "):
            out.append((line, []))
        elif out and not line.startswith(("index: ", "controls: ")):
            out[-1][1].append(line)
    return out


def verdicts(lines):
    """{target: (kind, detail)}, with NO MATCH and UNKEYED under their own names."""
    d = {}
    for ln in lines:
        m = re.match(r"(MATCH|CANDIDATE) (.+?) \((.*)\)$", ln)
        if m:
            d[m.group(2)] = (m.group(1), m.group(3))
        elif ln.startswith(("NO MATCH", "UNKEYED")):
            d[ln.split(" (")[0]] = (ln.split(" (")[0], ln)
    return d


def args_of(c):
    a = []
    for k in ("title", "arxiv", "doi", "url"):
        for val in ([c[k]] if isinstance(c.get(k), str) else c.get(k) or []):
            a += [f"--{k}", val]
    for k in ("author", "year"):
        if c.get(k) is not None:
            a += [f"--{k}", str(c[k])]
    return a


def look(v, c, *extra):
    """One work's lookup: (run, {target: (kind, detail)} or None when the run gave no single block)."""
    r = lrun(v, *args_of(c), *extra)
    b = blocks(r.stdout)
    return r, (verdicts(b[0][1]) if r.returncode == 0 and len(b) == 1 else None)


def kinds(vd):
    return {t: k for t, (k, _d) in (vd or {}).items()}


def doc(*lines, body="body text\n"):
    return "---\n" + "\n".join(lines) + "\n---\n\n" + body


S = "wiki/sources/"
LK = {
    # the six historical works, in the page shapes they had
    S + "bani-harouni-2025-rewarding-doubt-calibrated-confidence.md": doc(   # all fields present
        'title: "Paper: Rewarding Doubt — RL for Calibrated Confidence Expression of LLMs"', "type: source",
        "authors:", "  - David Bani-Harouni", "  - Chantal Pellegrini", "year: 2025", "doi: arXiv:2503.02623",
        "sources:", "  - raw/2-papers/rewarding-doubt-arxiv-html.md", "source_url: https://arxiv.org/html/2503.02623v6",
        "aliases:", "  - stangel-2025-rewarding-doubt"),
    S + "llms-mostly-know-what-they-know.md": doc(                          # a title and no identifier
        'title: "Paper: Language Models (Mostly) Know What They Know"', "type: source",
        "authors: [Saurav Kadavath, Tom Conerly, Amanda Askell]", "year: 2022",
        'sources: ["raw/2-papers/LLMs_know_what_they_know.pdf", "raw/2-papers/LLMs_know_what_they_know.md"]'),
    S + "tian-2023-just-ask-for-calibration.md": doc(                       # an arXiv id in doi:
        'title: "Paper: Just Ask for Calibration — Eliciting Calibrated Confidence from RLHF-Tuned Language Models"',
        "authors: [Katherine Tian, Eric Mitchell]", "year: 2023", 'doi: "arXiv:2305.14975"',
        'sources: [raw/2-papers/just-ask-for-calibration.md, "https://arxiv.org/abs/2305.14975"]',
        'source_url: "https://arxiv.org/abs/2305.14975"'),
    S + "lin-2022-teaching-models-to-express-uncertainty-in-words.md": doc(
        'title: "Paper: Teaching Models to Express Their Uncertainty in Words"',
        "authors: [Stephanie Lin, Jacob Hilton, Owain Evans]", "year: 2022", 'doi: "arXiv:2205.14334"',
        'source_url: "https://arxiv.org/abs/2205.14334"'),
    S + "on-calibration-of-modern-neural-networks.md": doc(                 # an arXiv URL in doi:
        'title: "Paper: On Calibration of Modern Neural Networks"', "authors:", "  - Chuan Guo", "  - Geoff Pleiss",
        "year: 2017", "doi: https://arxiv.org/abs/1706.04599", "source_url: https://arxiv.org/abs/1706.04599"),
    S + "verification-of-forecasts-expressed-in-terms-of-probability.md": doc(   # source_url only
        'title: "Source: Verification of Forecasts Expressed in Terms of Probability"', "authors: [Glenn W. Brier]",
        "year: 1950",
        'source_url: "https://journals.ametsoc.org/view/journals/mwre/78/1/1520-0493_1950_078_0001_vofeit_2_0_co_2.xml"'),
    "raw/2-papers/LLMs_know_what_they_know.md": doc("converted_from: local.pdf", "converted_by: markitdown"),
    "raw/2-papers/rewarding-doubt-arxiv-html.md": doc("source_url: https://arxiv.org/html/2503.02623v6"),
    # the other promised shapes
    S + "smith-2019-widget-calibration-study.md": doc('title: "Source: Widget Calibration Study Notes"'),   # slug only
    S + "deep-sets-sparse-graphs.md": doc('title: "Paper: Deep Sets Over Sparse Graphs"',                   # raw-linked
                                          "sources: [raw/2-papers/deep-sets-sparse-graphs.md]"),
    "raw/2-papers/deep-sets-sparse-graphs.md": doc("source_url: https://arxiv.org/abs/2101.00001", "converted_by: markitdown"),
    # the conflicting-DOI title collision
    S + "learning-from-human-feedback.md": doc('title: "Paper: Learning from Human Feedback"', 'doi: "10.5555/lfhf.2020.1"',
                                               "authors: [Ann Example]", "year: 2020"),
    # two pages compiled from one repository snapshot: one source_url, one raw bundle
    S + "project-submission-v2.md": doc('title: "Paper: Calibrating for Consequences — Cost-Targeted Confidence Training"',
                                        'source_url: "https://code.example.test/org/repo/tree/abc123/kit"',
                                        "sources: [raw/9-originals/project-snapshot-kit.md]"),
    S + "project-final-plan.md": doc('title: "Source: project repository — the reconciled implementation plan"',
                                     "source_url: https://code.example.test/org/repo/tree/abc123/kit",
                                     "sources:", "  - raw/9-originals/project-snapshot-kit.md"),
    "raw/9-originals/project-snapshot-kit.md": doc("source_url: https://code.example.test/org/repo/tree/abc123/kit",
                                                   "arxiv: 2202.00002", 'title: "Project review kit bundle"'),
    # a companion page asserting its paper's identifier, beside the paper
    S + "binary-rewards-paper.md": doc('title: "Paper: Beyond Binary Rewards — Reasoning About Uncertainty"',
                                       "doi: arXiv:2601.00011"),
    S + "binary-rewards-code.md": doc('title: "Repo: official code (Beyond Binary Rewards)"', 'doi: "arXiv:2601.00011"',
                                      "source_url: https://code.example.test/org/binary-rewards"),
    # two work pages asserting one identifier
    S + "dup-a.md": doc('title: "Paper: Duplicate Page Alpha Copy"', 'doi: "10.5555/dup.1"'),
    S + "dup-b.md": doc('title: "Paper: Duplicate Page Beta Copy"', 'doi: "10.5555/dup.1"'),
    # lossy identifier extraction
    S + "example-paren.md": doc('title: "Paper: Parenthesised Identifier Example Paper"', 'doi: "10.5555/example(a)"'),
    S + "series-paper-a.md": doc('title: "Paper: Series Paper Alpha Study"',
                                 "source_url: https://publisher.example.test/doi/10.5555/series/paper-a"),
    # DOI forms, an arXiv id only in a location field, an old-style arXiv id
    S + "lost-in-the-middle.md": doc('title: "Paper: Lost in the Middle — How Language Models Use Long Contexts"',
                                     'doi: "10.1162/tacl_a_00638"', 'source_url: "https://arxiv.org/abs/2307.03172"'),
    S + "old-style-arxiv.md": doc('title: "Paper: An Old Style Identifier Paper"', "arxiv: hep-th/9901001"),
    # aliases, a shared author-year, a title under the key floor
    S + "aliased-page.md": doc('title: "Source: Aliased Page Main Title"',
                               'aliases: ["Alternative Name of the Aliased Work"]'),
    S + "lee-2021-alpha.md": doc('title: "Paper: Alpha Results on Sparse Widgets"', "authors: [Ann Lee]", "year: 2021"),
    S + "lee-2021-beta.md": doc('title: "Paper: Beta Results on Dense Widgets"', "authors:", '  - "Lee, Ann"', "year: 2021"),
    S + "a-world-unobserved.md": doc('title: "Source: A World Unobserved"',
                                     'source_url: "https://blog.example.test/p/a-world-unobserved"'),
}
LKV = mkvault("lk", LK)
P_RD, P_KAD, P_TIAN, P_LIN, P_GUO, P_BRIER = (S + n + ".md" for n in (
    "bani-harouni-2025-rewarding-doubt-calibrated-confidence", "llms-mostly-know-what-they-know",
    "tian-2023-just-ask-for-calibration", "lin-2022-teaching-models-to-express-uncertainty-in-words",
    "on-calibration-of-modern-neural-networks", "verification-of-forecasts-expressed-in-terms-of-probability"))
LK_MOD = lk_load()

# Literal citations: (id, citation, the verdict each target must get). The six historical works carry the
# keys a citation of each gives; the rest are the promised shapes, the conflicts and the unkeyed.
CITES = [
    ("rewarding-doubt", {"title": "Rewarding Doubt: A Reinforcement Learning Approach to Calibrated Confidence "
                                  "Expression of Large Language Models", "author": "Bani-Harouni", "year": 2025,
                         "arxiv": "2503.02623"}, {P_RD: "MATCH"}),
    ("kadavath-2022", {"title": "Language Models (Mostly) Know What They Know", "author": "Kadavath", "year": 2022,
                       "arxiv": "2207.05221"}, {P_KAD: "CANDIDATE"}),
    ("tian-2023", {"title": "Just Ask for Calibration: Strategies for Eliciting Calibrated Confidence Scores from "
                            "Language Models Fine-Tuned with Human Feedback", "author": "Tian", "year": 2023,
                   "arxiv": "2305.14975"}, {P_TIAN: "MATCH"}),
    ("lin-2022", {"title": "Teaching Models to Express Their Uncertainty in Words", "author": "Lin", "year": 2022,
                  "arxiv": "2205.14334"}, {P_LIN: "MATCH"}),
    ("guo-2017", {"title": "On Calibration of Modern Neural Networks", "author": "Guo", "year": 2017,
                  "arxiv": "1706.04599"}, {P_GUO: "MATCH"}),
    ("brier-1950", {"title": "Verification of Forecasts Expressed in Terms of Probability", "author": "Brier",
                    "year": 1950, "doi": "10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2"}, {P_BRIER: "CANDIDATE"}),
    ("brier-url", {"url": "https://journals.ametsoc.org/view/journals/mwre/78/1/1520-0493_1950_078_0001_vofeit_2_0_co_2.xml"},
     {P_BRIER: "CANDIDATE"}),
    ("slug-only", {"author": "J. Smith", "year": 2019}, {S + "smith-2019-widget-calibration-study.md": "CANDIDATE"}),
    ("raw-linked", {"arxiv": "2101.00001"}, {"NO MATCH": "NO MATCH"}),
    ("collision", {"title": "Learning with Human Feedback", "doi": "10.5555/lwhf.2021.7"},
     {S + "learning-from-human-feedback.md": "CANDIDATE"}),
    ("plan-by-url", {"title": "project repository — the reconciled implementation plan",
                     "url": "https://code.example.test/org/repo/tree/abc123/kit"},
     {S + "project-final-plan.md": "CANDIDATE", S + "project-submission-v2.md": "CANDIDATE"}),
    ("bundle-id", {"arxiv": "2202.00002"}, {"NO MATCH": "NO MATCH"}),
    ("companion", {"arxiv": "arXiv:2601.00011"}, {S + "binary-rewards-paper.md": "MATCH", S + "binary-rewards-code.md": "CANDIDATE"}),
    ("two-pages", {"doi": "10.5555/dup.1"}, {S + "dup-a.md": "CANDIDATE", S + "dup-b.md": "CANDIDATE"}),
    ("held-by-title-doi-only", {"doi": "10.5555/kadavath.2022.preprint"}, {"NO MATCH": "NO MATCH"}),
    ("held-by-title-doi-and-title", {"doi": "10.5555/kadavath.2022.preprint",
                                     "title": "Language Models (Mostly) Know What They Know"}, {P_KAD: "CANDIDATE"}),
    ("planted-not-held", {"title": "Gradient Descent Through Lunar Regolith Sieves", "author": "Nobody", "year": 1999,
                          "doi": "10.5555/planted.lookup.1"}, {"NO MATCH": "NO MATCH"}),
    ("unkeyed-short-title", {"title": "A World Unobserved"}, {"UNKEYED": "UNKEYED"}),
    ("unkeyed-author-only", {"author": "Kadavath"}, {"UNKEYED": "UNKEYED"}),
]
SINGLE = {}
for cid, cit, want in CITES:
    SINGLE[cid] = look(LKV, cit)

print("== lookup L1: MATCH establishes work identity ==")
for cid in ("rewarding-doubt", "tian-2023", "lin-2022", "guo-2017"):
    r, vd = SINGLE[cid]
    want = dict(next(w for i, _c, w in CITES if i == cid))
    check(f"L1a {cid}: an arXiv id the page asserts in doi: gives MATCH at its page", kinds(vd) == want, out(r))
for label, c in [("DOI upper-case", {"doi": "10.1162/TACL_A_00638"}), ("doi.org resolver URL", {"url": "https://doi.org/10.1162/TACL_A_00638"}),
                 ("doi: prefix", {"doi": "doi:10.1162/tacl_a_00638"})]:
    r, vd = look(LKV, c)
    check(f"L1b canonical DOI form ({label}) gives MATCH", kinds(vd) == {S + "lost-in-the-middle.md": "MATCH"}, out(r))
for label, c in [("versioned id", {"arxiv": "2205.14334v2"}), ("arXiv: prefix", {"arxiv": "arXiv:2205.14334"}),
                 ("abs URL", {"url": "https://arxiv.org/abs/2205.14334v1"}), ("pdf URL", {"url": "https://arxiv.org/pdf/2205.14334v2"}),
                 ("arXiv DOI", {"doi": "10.48550/arXiv.2205.14334"})]:
    r, vd = look(LKV, c)
    check(f"L1b supported arXiv representation ({label}) gives MATCH", kinds(vd).get(P_LIN) == "MATCH", out(r))
r, vd = look(LKV, {"arxiv": "hep-th/9901001v2"})
check("L1b an old-style arXiv id in an arxiv: field gives MATCH", kinds(vd) == {S + "old-style-arxiv.md": "MATCH"}, out(r))
r, vd = look(LKV, {"arxiv": "2205.14334", "url": "https://elsewhere.example.test/lin-copy"})
check("L1b differing URLs alone are no conflict: the identifier still gives MATCH", kinds(vd) == {P_LIN: "MATCH"}, out(r))
r, vd = SINGLE["plan-by-url"]
check("L1c must not fire: a shared source URL makes no MATCH; both pages it names are candidates, each saying why",
      kinds(vd) == {S + "project-final-plan.md": "CANDIDATE", S + "project-submission-v2.md": "CANDIDATE"}
      and "a shared location, never an identity" in vd[S + "project-submission-v2.md"][1], out(r))
RAW_PHRASE = "raw files are not searched"
r, vd = SINGLE["bundle-id"]
check("L1d must not fire: an identifier held only in a raw bundle two pages name reaches neither page (raw files are not "
      "searched): NO MATCH, and the line says so", kinds(vd) == {"NO MATCH": "NO MATCH"} and RAW_PHRASE in vd["NO MATCH"][1], out(r))
r, vd = SINGLE["raw-linked"]
check("L1d must not fire: an identifier held only in one page's own raw file gives no verdict through it: NO MATCH, "
      "saying raw files are not searched", kinds(vd) == {"NO MATCH": "NO MATCH"} and RAW_PHRASE in vd["NO MATCH"][1], out(r))
r, vd = look(LKV, {"doi": "10.5555/example(a"})
r2, vd2 = look(LKV, {"doi": "10.5555/example(a)"})
check("L1e must not fire: DOI `…(a` against a page's `…(a)` (equal only after the lossy extractor) is a CANDIDATE; the exact DOI is a MATCH",
      kinds(vd) == {S + "example-paren.md": "CANDIDATE"} and kinds(vd2) == {S + "example-paren.md": "MATCH"}, out(r) + out(r2))
r, vd = look(LKV, {"url": "https://publisher.example.test/doi/10.5555/series/paper-b"})
check("L1e must not fire: publisher URL paths cut to one DOI (`/series/paper-a` against `/series/paper-b`) give no MATCH",
      kinds(vd) == {S + "series-paper-a.md": "CANDIDATE"} and "lossy extraction" in vd[S + "series-paper-a.md"][1], out(r))
r, vd = look(LKV, {"url": "https://notarxiv.org/abs/2205.14334"})
check("L1e must not fire: an arXiv-shaped path on another host (notarxiv.org) gives no MATCH",
      kinds(vd) == {P_LIN: "CANDIDATE"}, out(r))
r, vd = SINGLE["collision"]
check("L1f must not fire: the from/with title collision with a conflicting DOI stays a CANDIDATE and prints both DOIs",
      kinds(vd) == {S + "learning-from-human-feedback.md": "CANDIDATE"}
      and "10.5555/lwhf.2021.7" in vd[S + "learning-from-human-feedback.md"][1] and "10.5555/lfhf.2020.1" in vd[S + "learning-from-human-feedback.md"][1], out(r))
r, vd = look(LKV, {"doi": "10.1162/tacl_a_00638", "arxiv": "2307.03999"})
check("L1f must not fire: an equal DOI beside a conflicting arXiv id is a CANDIDATE with the conflict printed",
      kinds(vd) == {S + "lost-in-the-middle.md": "CANDIDATE"} and "conflict:" in vd[S + "lost-in-the-middle.md"][1], out(r))
r, vd = look(LKV, {"doi": "10.5555/LFHF.2020.1"})
check("L1f positive control: the collision page's own DOI (case-varied) gives MATCH", kinds(vd) == {S + "learning-from-human-feedback.md": "MATCH"}, out(r))
r, vd = SINGLE["companion"]
check("L1g a Repo: page asserting its paper's identifier is a CANDIDATE; the Paper: page is the MATCH",
      kinds(vd) == {S + "binary-rewards-paper.md": "MATCH", S + "binary-rewards-code.md": "CANDIDATE"}
      and "companion" in vd[S + "binary-rewards-code.md"][1], out(r))
LKC = mkvault("lk-companion", {S + "binary-rewards-code.md": LK[S + "binary-rewards-code.md"],
                               S + "aliased-page.md": LK[S + "aliased-page.md"]})
r, vd = look(LKC, {"arxiv": "2601.00011"})
check("L1g must not fire: the Repo: page alone is never the paper's MATCH", kinds(vd) == {S + "binary-rewards-code.md": "CANDIDATE"}, out(r))
r, vd = SINGLE["two-pages"]
check("L1h must not fire: one identifier asserted by two work pages singles out neither",
      kinds(vd) == {S + "dup-a.md": "CANDIDATE", S + "dup-b.md": "CANDIDATE"} and "2 pages" in vd[S + "dup-a.md"][1], out(r))
r, vd = look(LKV, {"arxiv": "2307.03172"})
check("L1i must not fire: an arXiv id read only from source_url is a location, so a CANDIDATE",
      kinds(vd) == {S + "lost-in-the-middle.md": "CANDIDATE"} and "a location" in vd[S + "lost-in-the-middle.md"][1], out(r))

print("== lookup L2: candidates keep uncertainty and multiplicity ==")
r, vd = SINGLE["kadavath-2022"]
check("L2a the exact title of a page with no identifier is a CANDIDATE (title, author-year), never a MATCH",
      kinds(vd) == {P_KAD: "CANDIDATE"} and "title: a lossy key" in vd[P_KAD][1] and "author-year kadavath 2022" in vd[P_KAD][1], out(r))
r, vd = SINGLE["brier-url"]
check("L2b Brier's URL alone is a CANDIDATE: an equal URL is a location, never an identity", kinds(vd) == {P_BRIER: "CANDIDATE"}, out(r))
r, vd = look(LKV, {"url": "https://journals.ametsoc.org/view/journals/mwre/78/1/other.xml"})
check("L2b must not fire: a URL on the same host with another path reaches nothing", kinds(vd) == {"NO MATCH": "NO MATCH"}, out(r))
r, vd = SINGLE["brier-1950"]
check("L2b Brier's citation (title, author-year, a DOI no page carries) is a CANDIDATE", kinds(vd) == {P_BRIER: "CANDIDATE"}, out(r))
r, vd = look(LKV, {"title": "Alternative Name of the Aliased Work"})
r2, vd2 = look(LKV, {"title": "stangel-2025-rewarding-doubt"})
check("L2c an inline alias and a block-list alias each give a CANDIDATE",
      kinds(vd) == {S + "aliased-page.md": "CANDIDATE"} and "alias" in vd[S + "aliased-page.md"][1] and kinds(vd2) == {P_RD: "CANDIDATE"}, out(r) + out(r2))
r, vd = SINGLE["slug-only"]
check("L2d a slug author-year (no authors or year in frontmatter) gives a CANDIDATE labelled slug",
      kinds(vd) == {S + "smith-2019-widget-calibration-study.md": "CANDIDATE"} and "(slug" in vd[S + "smith-2019-widget-calibration-study.md"][1], out(r))
r, vd = look(LKV, {"author": "A. Lee", "year": 2021})
check("L2e two pages sharing a first author and a year (inline and block-list authors) both give CANDIDATE",
      kinds(vd) == {S + "lee-2021-alpha.md": "CANDIDATE", S + "lee-2021-beta.md": "CANDIDATE"}, out(r))
r, vd = look(LKV, {"title": "Learning with Human Feedback"})
check("L2f the title collision alone is a CANDIDATE, never a MATCH", kinds(vd) == {S + "learning-from-human-feedback.md": "CANDIDATE"}, out(r))

print("== lookup L3: coverage describes the effective index ==")
CV = mkvault("lk-cov", {
    S + "p1.md": doc('title: "Paper: Coverage Page One Study"', 'doi: "10.5555/a.1"', "authors:", "  - Ann Able", "year: 2020"),
    S + "p2.md": doc('title: "Paper: Coverage Page Two Study"', "doi: arXiv:2101.00002", "authors: [Bo Baker]"),
    S + "p3.md": doc('title: "Repo: Coverage Page Three Code"', 'doi: "https://github.com/example/three"'),
    S + "p4.md": doc('title: "Source: Tiny Page"', "doi: none — no DOI issued"),
    S + "p5.md": doc('title: "Paper: Coverage Page Five Study"', "source_url: https://doi.org/10.5555/b.2"),
    S + "p6.md": doc('title: "Paper: Coverage Page Six Study"', "aliases:", "  - Alias Title For Page Six"),
    S + "smith-2019-thing.md": doc('title: "Source: Coverage Page Seven Notes"'),
    S + "p8.md": doc('title: "Paper: Coverage Page Eight Study"', "sources: [raw/x/p8.md]"),
    "raw/x/p8.md": doc('doi: "10.5555/raw.8"', 'title: "Raw Title of Page Eight"'),
})
r, vd = look(CV, {"doi": "10.5555/zzz.9", "title": "Some Other Title Entirely", "author": "Nobody", "year": 1999,
                  "url": "https://nowhere.example.test/x"})
cov = (vd or {}).get("NO MATCH", ("", ""))[1]
want_cov = ["of 8 source pages", "doi on 2 (1 asserted in the page's own identity field)",
            "2 pages carry a doi/arxiv field that gives no identifier",
            "title or alias on 7 (title 7, alias 1; 1 titles under 3 tokens, 0 untitled)",
            "author-year on 2 (1 from the file name or an alias only; 1 pages' authors or year unusable)",
            "url on 2", RAW_PHRASE]
check("L3a NO MATCH carries coverage counted by source page after extraction, with the reasons pages give none, and says "
      "raw files are not searched", all(w in cov for w in want_cov), out(r) + f"\n     wanted each of {want_cov}")
check("L3b must not fire: field presence (doi: on 4 pages) is never reported as usable coverage", "doi on 4" not in cov and "doi on 2" in cov, out(r))
r, vd = look(CV, {"author": "Ann Able", "year": 2020})
r2, vd2 = look(CV, {"title": "Alias Title For Page Six"})
check("L3c block-list authors and a block-list alias are read (each gives its CANDIDATE)",
      kinds(vd) == {S + "p1.md": "CANDIDATE"} and kinds(vd2) == {S + "p6.md": "CANDIDATE"}, out(r) + out(r2))
r = lrun(CV, "--author", "Ann Able", "--year", "2020", "--title", "AB", "--doi", "not-an-identifier", "--url", "notaurl")
b = blocks(r.stdout)
disc = [ln for ln in (b[0][1] if b else []) if ln.startswith("discarded: ")]
check("L3d every supplied key that gives none is named on a discarded: line with its reason",
      r.returncode == 0 and disc and all(s in disc[0] for s in ('--title "AB"', '--doi "not-an-identifier"', '--url "notaurl"')), out(r))
r, vd = SINGLE["unkeyed-short-title"]
check("L3e no usable key gives UNKEYED with the reason, never NO MATCH (`A World Unobserved` is under the title floor)",
      kinds(vd) == {"UNKEYED": "UNKEYED"} and "under 3 tokens" in vd["UNKEYED"][1], out(r))
r, vd = SINGLE["unkeyed-author-only"]
check("L3e an author without a year is UNKEYED, with the reason", kinds(vd) == {"UNKEYED": "UNKEYED"} and "without --year" in vd["UNKEYED"][1], out(r))
r, vd = look(CV, {"title": "Raw Title of Page Eight"})
r2, vd2 = look(CV, {"doi": "10.5555/raw.8"})
check("L3f keys held only in the raw file a page names count nowhere and reach nothing: NO MATCH by its title and by its "
      "doi, each saying raw files are not searched, as the index line does",
      kinds(vd) == {"NO MATCH": "NO MATCH"} and kinds(vd2) == {"NO MATCH": "NO MATCH"} and RAW_PHRASE in vd["NO MATCH"][1]
      and any(ln.startswith("index: ") and RAW_PHRASE in ln for ln in r.stdout.splitlines()), out(r) + out(r2))
r, vd = SINGLE["held-by-title-doi-only"]
r2, vd2 = SINGLE["held-by-title-doi-and-title"]
check("L3g a page held by title only, asked by its DOI alone: NO MATCH with coverage; with its title added: CANDIDATE",
      kinds(vd) == {"NO MATCH": "NO MATCH"} and "coverage: of " in vd["NO MATCH"][1] and kinds(vd2) == {P_KAD: "CANDIDATE"}, out(r) + out(r2))
r, vd = SINGLE["planted-not-held"]
check("L3h a planted work no page holds: NO MATCH, and no word claiming it is not held", kinds(vd) == {"NO MATCH": "NO MATCH"}
      and not BANNED.search(r.stdout), out(r))

print("== lookup L4: a failed premise gives no verdict ==")
VERDICT_LINE = re.compile(r"(?m)^(?:citation |MATCH |CANDIDATE |NO MATCH|UNKEYED|discarded: )")


def failed(r, phrase):
    return r.returncode == 2 and r.stdout.startswith("PROBE FAILED: ") and phrase in r.stdout and not VERDICT_LINE.search(r.stdout)


TONLY = mkvault("lk-title-only", {S + "t1.md": doc('title: "Paper: Title Only Healthy Page"'),
                                  S + "t2.md": doc('title: "Paper: Another Title Only Page"')})
r, vd = look(TONLY, {"title": "Title Only Healthy Page"})
check("L4a a healthy title-only index works; its identifier control is n/a, never failed",
      kinds(vd) == {S + "t1.md": "CANDIDATE"} and "identity n/a" in r.stdout, out(r))
IONLY = mkvault("lk-id-only", {S + "i1.md": doc('title: "Doc"', 'doi: "10.5555/i.1"'), S + "i2.md": doc('title: "Doc Two"', 'doi: "10.5555/i.2"')})
r, vd = look(IONLY, {"doi": "10.5555/i.2"})
check("L4b a healthy identifier-only index works; its title control is n/a, never failed",
      kinds(vd) == {S + "i2.md": "MATCH"} and "title n/a" in r.stdout, out(r))
bogus_l = tempfile.mkdtemp(prefix="notavault-lookup-", dir=TMP)
r = lrun(bogus_l, "--title", "Any Title Here At All")
check("L4c not a vault root: PROBE FAILED, no verdict", failed(r, "not a vault root"), out(r))
NOSRC = os.path.join(TMP, "lk-nosources")
os.makedirs(os.path.join(NOSRC, "raw"))
os.makedirs(os.path.join(NOSRC, "wiki"))
r = lrun(NOSRC, "--title", "Any Title Here At All")
check("L4c wiki/sources/ not a directory: PROBE FAILED, no verdict", failed(r, "wiki/sources/ is not a directory"), out(r))
EMPTY = mkvault("lk-empty", {"wiki/sources/.gitkeep": ""})
r = lrun(EMPTY, "--title", "Any Title Here At All")
check("L4d an empty index (no source page): PROBE FAILED, no verdict", failed(r, "holds no Markdown page"), out(r))
NOKEY = mkvault("lk-nokey", {S + "n1.md": doc('title: "Doc"'), S + "n2.md": doc('title: "Doc Two"')})
r = lrun(NOKEY, "--title", "Any Title Here At All")
check("L4d pages but no usable key of any kind: PROBE FAILED, no verdict", failed(r, "no usable key of any kind"), out(r))
BROKEN = mkvault("lk-broken", {S + "good.md": doc('title: "Paper: A Healthy Page Beside It"', 'doi: "10.5555/good.1"'),
                               S + "broken.md": '---\ntitle: "Paper: A Page Whose Block Never Closes"\ndoi: "10.5555/broken.1"\n\nbody\n'})
r = lrun(BROKEN, "--title", "A Healthy Page Beside It")
check("L4e an unclosed frontmatter block beside a healthy page: PROBE FAILED naming it, and the healthy page gets no verdict",
      failed(r, "wiki/sources/broken.md: the frontmatter block never closes"), out(r))
for name, text, phrase in [
        ("nofm", "# A page with no frontmatter\n\nbody\n", "no frontmatter block"),
        ("badutf8", b'---\ntitle: "Paper: Bad \xff Bytes Here"\n---\nbody\n', "not UTF-8"),
        ("badlist", doc('title: "Paper: Unclosed Authors List"', "authors: [Ann Able, Bo Baker"),
         "does not parse as YAML: while parsing a flow sequence"),
        ("dupfield", doc('title: "Paper: Title Given Twice Here"', 'title: "Paper: Second Title Given"'), "given twice"),
        ("badquote", doc('title: "Paper: A Quote That Never Closes', 'doi: "10.5555/q.1"'), "does not parse as YAML"),
        ("listofmaps", doc('title: "Paper: Authors As Mappings"', "authors:", "  - name: Ann Able"), "a list holding a mapping")]:
    v = mkvault(f"lk-bad-{name}", {S + "good.md": doc('title: "Paper: A Healthy Page Beside It"'), S + f"{name}.md": text})
    r = lrun(v, "--title", "A Healthy Page Beside It")
    check(f"L4e malformed page ({name}): PROBE FAILED ({phrase}), no verdict", failed(r, phrase), out(r))
LOCKV = mkvault("lk-locked", {S + "good.md": doc('title: "Paper: A Healthy Page Beside It"'),
                              S + "locked.md": doc('title: "Paper: An Unreadable Page Here"')})
os.chmod(os.path.join(LOCKV, S, "locked.md"), 0)
try:
    r = lrun(LOCKV, "--title", "A Healthy Page Beside It")
finally:
    os.chmod(os.path.join(LOCKV, S, "locked.md"), 0o644)
check("L4e an unreadable page: PROBE FAILED, no verdict", failed(r, "cannot be read"), out(r))
RAWBAD = mkvault("lk-rawbad", {S + "good.md": doc('title: "Paper: A Healthy Page Beside It"'),
                               "raw/x/unclosed.md": '---\nsource_url: https://example.test/x\n\nbody\n',
                               "raw/x/tabbed.md": "---\n\tdoi: 10.5555/raw\n---\n",
                               "raw/x/not-yaml.md": '---\nnotes: "never closed\ndoi: 10.5555/raw\n---\n',
                               "raw/x/twice.md": "---\nscope: pdf\nscope: twice\n---\n",
                               "raw/x/thematic-break.md": "---\n\n# A heading after a rule\n\nbody\n",
                               "raw/locked/inner.md": doc('title: "An Unreadable Raw File"')})
os.chmod(os.path.join(RAWBAD, "raw", "locked"), 0)
try:
    r = lrun(RAWBAD, "--title", "A Healthy Page Beside It")
    rd = run(RAWBAD, "raw/x/thematic-break.md")
finally:
    os.chmod(os.path.join(RAWBAD, "raw", "locked"), 0o755)
check("L4f raw files the join refused (a block that never closes, a tab, an unclosed quote, a key given twice) and an "
      "unreadable raw/ subfolder do not touch the lookup: the healthy page gets its CANDIDATE, exit 0, and the index line "
      "says raw files are not searched; control: the de-dup probe, which walks raw/, fails on the unreadable subfolder",
      r.returncode == 0 and f"CANDIDATE {S}good.md (" in r.stdout and "raw/" not in r.stdout
      and any(ln.startswith("index: ") and RAW_PHRASE in ln for ln in r.stdout.splitlines())
      and rd.returncode == 2 and "unreadable" in rd.stdout, out(r) + out(rd))
r2 = lrun(RAWBAD, "--title", "A Healthy Page Beside It", "--no-raw")
check("L4f the raw-join flag is gone: --no-raw is refused as a usage error, exit 2, with no verdict", failed(r2, "lookup usage"), out(r2))


def inproc(mod, argv):
    buf = io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(buf):
            mod.lookup_main(argv)
    except SystemExit as e:
        code = e.code
    return code, buf.getvalue()


try:
    sab = lk_load()
    sab.lookup_work = lambda idx, cit: (["NO MATCH (sabotaged)"], {}, [])
    code, text = inproc(sab, ["--vault-root", LKV, "--title", "Teaching Models to Express Their Uncertainty in Words"])
    ok = code == 2 and "same-run control failed" in text and not VERDICT_LINE.search(text)
except Exception as e:
    ok, text = False, f"error: {e!r}"
check("L4g a planted dead matcher fails the same-run controls: exit 2, no verdict", ok, text)
try:
    sab = lk_load()
    sab.canonical_ids = lambda value: set()
    code, text = inproc(sab, ["--vault-root", LKV, "--doi", "10.1162/tacl_a_00638"])
    planted_l = lk_load().lookup_self_test({"canonical": lambda value: set()})
    n_canon = sum(1 for n, _i, e in LK_MOD.LOOKUP_SELF_TEST if n == "canonical" and e)
    ok = (code == 2 and "self-test" in text and not VERDICT_LINE.search(text) and len(planted_l) == n_canon >= 10
          and LK_MOD.lookup_self_test() == [])
except Exception as e:
    ok, text = False, f"error: {e!r}"
check("L4h a planted dead canonical-identifier extractor fails the lookup self-test (each positive case catches it; the real one passes)", ok, text)
LISTS = os.path.join(TMP, "lists")
os.makedirs(LISTS)


def listfile(name, text):
    p = os.path.join(LISTS, name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


good_line = json.dumps({"id": "lin", "arxiv": "2205.14334"})
for name, text, phrase in [("late-bad-json", good_line + "\n" + good_line + "\n{\"title\": \"Unclosed\"\n", "list line 3: not one JSON object"),
                           ("unknown-key", good_line + "\n" + json.dumps({"titel": "Typo Key Title Here"}) + "\n", "unknown key 'titel'"),
                           ("empty", "# only a comment\n\n", "no citation in it"),
                           ("wrong-type", json.dumps({"title": 42}) + "\n", "title takes a string"),
                           ("dup-key", '{"doi": "10.5555/a.1", "doi": "10.5555/b.2"}\n', "given twice"),
                           ("not-object", "[\"a list\"]\n", "not one JSON object")]:
    r = lrun(LKV, "--list", listfile(name + ".jsonl", text))
    check(f"L4i malformed list ({name}): PROBE FAILED ({phrase}), and no earlier entry's verdict is printed", failed(r, phrase), out(r))
r = lrun(LKV, "--list", os.path.join(LISTS, "no-such-list.jsonl"))
check("L4i an unreadable list: PROBE FAILED, no verdict", failed(r, "cannot be read"), out(r))
r = lrun(LKV)
r2 = lrun(LKV, "--title", "Some Title Words Here", "--list", listfile("one.jsonl", good_line + "\n"))
check("L4j no citation, or keys beside --list: PROBE FAILED, no verdict", failed(r, "no citation given") and failed(r2, "not both"), out(r) + out(r2))

print("== lookup L5: a list keeps the single-work contract ==")
LIST_ALL = listfile("all.jsonl", "# every literal citation of the suite\n" + "".join(
    json.dumps({"id": cid, **{k: v for k, v in c.items()}}) + "\n" for cid, c, _w in CITES))
r = lrun(LKV, "--list", LIST_ALL)
bl = blocks(r.stdout)
check("L5a a list of every literal citation gives one block per entry, none dropped", r.returncode == 0 and len(bl) == len(CITES), out(r))
mism = []
for (cid, _c, want), (_h, lines) in zip(CITES, bl):
    single_lines = blocks(SINGLE[cid][0].stdout)
    if not single_lines or single_lines[0][1] != lines:
        mism.append(cid)
check("L5b each entry's verdict lines in the list equal its single-work run, line for line", r.returncode == 0 and not mism and len(bl) == len(CITES), f"differ: {mism}\n" + out(r))
wrong = [cid for cid, _c, want in CITES if kinds(SINGLE[cid][1]) != want]
check("L5c every literal citation gets its stated verdict at its stated pages", not wrong, f"wrong: {wrong}")
check("L5d the list header names each entry's list line and id", all(f"(list line {i + 2}, {cid})" in bl[i][0] for i, (cid, _c, _w) in enumerate(CITES)) if len(bl) == len(CITES) else False, out(r))

print("== lookup L6: the query skill keeps the limits of the result ==")
REQUIRED = {"MATCH": ["cite the page"],
            "CANDIDATE": ["Read the page", "opening the page is not confirmation", "conflict", "stays unresolved", "each read"],
            "NO MATCH": ["no match under these keys", "coverage line", "raw files are not searched", "never"],
            "UNKEYED": ["unresolved", "never report it as a no-match"],
            "PROBE FAILED": ["unresolved", "never fall back to greps", "never read it as a no-match"]}
ESCALATION = ["never by itself justifies a missing-work claim or a gather", "Step 4b", "verify the miss",
              "re-run with every key", "instrument rule's own reasons", "the head verifies a short list",
              "breadth one context cannot hold", "reason recorded", "two search controls", "separate first step",
              "reported apart from its results", "Only a verified miss"]
RETIRED_DEVICES = ["planted present work", "planted absent work"]


def query_step(text):
    m = re.search(r"(?ms)^### Step 1b — A membership question goes to the lookup verb\n(.*?)(?=^### )", text or "")
    return m.group(1) if m else None


def step_problems(step, verdict_names):
    if step is None:
        return ["no `Step 1b — A membership question goes to the lookup verb` in the query skill"]
    probs = []
    bullets = re.split(r"(?m)^- (?=\*\*)", step)
    flat = lambda s: " ".join(s.split())
    for v in verdict_names:
        mine = [b for b in bullets if re.match(r"\*\*(?:Exit 2, `)?" + re.escape(v), b)]
        if len(mine) != 1:
            probs.append(f"{v}: {len(mine)} bullets")
            continue
        probs += [f"{v}: lacks {p!r}" for p in REQUIRED[v] if p not in flat(mine[0])]
    named = set(re.findall(r"(?m)^- \*\*(?:Exit 2, `)?([A-Z][A-Z ]+[A-Z])", step))
    if named != set(verdict_names):
        probs.append(f"verdict bullets {sorted(named)} differ from the verb's {sorted(verdict_names)}")
    probs += [f"escalation lacks {p!r}" for p in ESCALATION if p not in flat(step)]
    probs += [f"a planted work is back in the step: {p!r}" for p in RETIRED_DEVICES if p in flat(step)]
    return probs


try:
    with open(QUERY_SKILL, encoding="utf-8") as fh:
        QTEXT = fh.read()
except OSError as e:
    QTEXT = ""
    print(f"     (query skill unreadable: {e})")
STEP = query_step(QTEXT)
NAMES = list(getattr(LK_MOD, "VERDICTS", ())) + ["PROBE FAILED"] if LK_MOD else ["?"]
probs = step_problems(STEP, NAMES)
check("L6a the query step answers every verdict the verb prints, and exit 2, with its caller response", not probs and len(NAMES) == 5, "\n".join(probs))
check("L6b the step sits once in the skill, between Step 1 and Step 2",
      QTEXT.count("### Step 1b — A membership question goes to the lookup verb") == 1
      and QTEXT.find("### Step 1 —") < QTEXT.find("### Step 1b —") < QTEXT.find("### Step 2 —"), f"{QTEXT.count('### Step 1b')} copies")
mutants = {"UNKEYED bullet dropped": re.sub(r"(?ms)^- \*\*UNKEYED.*?(?=^- \*\*)", "", STEP or ""),
           "NO MATCH reported as missing": (STEP or "").replace('report "no match under these keys"', 'report the work as missing'),
           "every miss sent to a lane": (STEP or "").replace("the head verifies a short list", "every miss goes to a verifier lane; a short list"),
           "opening counts as confirmation": (STEP or "").replace("opening the page is not confirmation", "opening the page confirms it"),
           "NO MATCH without the raw caveat": (STEP or "").replace("also says raw files are not searched", "also says what was read"),
           "a planted work back in formal work": (STEP or "").replace("Only a", "A planted present work too. Only a")}
caught = {k: bool(step_problems(m, NAMES)) for k, m in mutants.items()}
check("L6c control: the step checker catches each planted defect (a dropped verdict, a missing-work answer, a mandatory lane, "
      "opening as confirmation, a NO MATCH without the raw caveat)",
      STEP is not None and all(caught.values()), repr(caught))
spans = re.findall(r"`([^`]*--lookup[^`]*)`", STEP or "")
fill = {"<title>": "Teaching Models to Express Their Uncertainty in Words", "<first author>": "Stephanie Lin", "<year>": "2022",
        "<arxiv-id>": "2205.14334", "<doi>": "10.5555/lin.example.doi", "<url>": "https://arxiv.org/abs/2205.14334"}
ran = []
for span in spans:
    toks = shlex.split(span)
    if toks[:2] != ["python3", ".claude/skills/ingest/dedup_probe.py"]:
        ran.append((span, "not the ingest skill's probe"))
        continue
    lf = listfile("documented.jsonl", "".join(json.dumps({"id": c[0], **c[1]}) + "\n" for c in CITES[:3]))
    argv = [fill.get(t, lf if t == "<file>" else t) for t in toks[2:]]
    left = [t for t in argv if t.startswith("<")]
    r = subprocess.run([sys.executable, "-B", PROBE, *argv, "--vault-root", LKV], capture_output=True, text=True)
    LOOKUP_OUTPUTS.append(r.stdout)
    bl = blocks(r.stdout)
    ran.append((span, "ok" if r.returncode == 0 and not left and (len(bl) == 3 if "--list" in toks else
                                                                 kinds(verdicts(bl[0][1]) if bl else {}) == {P_LIN: "MATCH"}) else out(r)))
check("L6d the step's documented commands run as written: one work gives its MATCH, the list gives one block per entry",
      len(spans) == 2 and all(res == "ok" for _s, res in ran), repr(ran))
doc_keys = re.findall(r"`(\w+)`", (re.search(r"keys ((?:`\w+`,?\s*)+)", " ".join((STEP or "").split())) or [None, ""])[1])
check("L6e the list keys the step documents are the verb's list keys", LK_MOD is not None and doc_keys == list(LK_MOD.LIST_KEYS), repr(doc_keys))


def raw_mode_ok(step):
    """Whether a membership step fits the source-page verb: it names no raw-join flag, and before its verdict bullets
    it says that raw files are not searched."""
    return step is not None and "--no-raw" not in step and "raw files are not searched" in " ".join(step.split("\n- **")[0].split())


planted_flag = (STEP or "").replace("Report the failure and fix it", "Report the failure and fix it (`--no-raw` searches without the raw join)")
planted_quiet = (STEP or "").replace("raw files are not searched, so a", "a")
check("L6f the step offers no raw-join flag and says before its verdicts that raw files are not searched; controls: a planted "
      "--no-raw and a dropped caveat are each caught", raw_mode_ok(STEP) and not raw_mode_ok(planted_flag)
      and not raw_mode_ok(planted_quiet) and planted_flag != STEP and planted_quiet != STEP, (STEP or "")[:600])

# ================================================================================================
# The fold of the build's closed review (R1-R4). Each leg below fails on the build that review held
# and passes on the fold: one matching identifier never vouches for a conflicting one of its family
# (R1); a frontmatter value is read as YAML reads it, or refused with exit 2 (R2); the same-run
# controls cover the evidence an index holds, each with the verdict it is owed, and still catch a
# planted defect (R3); coverage and the index summary count source pages as unions, file-name keys
# included, and agree (R4).
# ================================================================================================
print("== review fold R1: one matching identifier never vouches for a conflicting one ==")
R1V = mkvault("lk-r1", {
    S + "r1-alpha.md": doc('title: "Paper: Conflict Fixture Alpha Study"', 'doi: "10.5555/r1.a"'),
    S + "r1-two-dois.md": doc('title: "Paper: Two Identifier Fixture Study"', 'doi: ["10.5555/r1.c", "10.5555/r1.d"]'),
    S + "r1-arxiv.md": doc('title: "Paper: Arxiv Conflict Fixture Study"', 'arxiv: "2601.00021"')})
P_A, P_TWO, P_AX = (S + n for n in ("r1-alpha.md", "r1-two-dois.md", "r1-arxiv.md"))
r, vd = look(R1V, {"doi": ["10.5555/r1.a", "10.5555/r1.b"]})
check("R1a must not fire: --doi A --doi B against a page asserting only A is a CANDIDATE naming B against A, never a MATCH",
      kinds(vd) == {P_A: "CANDIDATE"} and "conflict: the citation's doi 10.5555/r1.b against the page's 10.5555/r1.a" in vd[P_A][1], out(r))
LIST_R1 = listfile("r1.jsonl", json.dumps({"id": "two-dois", "doi": ["10.5555/r1.a", "10.5555/r1.b"]}) + "\n"
                   + json.dumps({"id": "reversed", "doi": ["10.5555/r1.b", "10.5555/r1.a"]}) + "\n")
r2 = lrun(R1V, "--list", LIST_R1)
bl = blocks(r2.stdout)
single_r1 = blocks(r.stdout)[0][1] if blocks(r.stdout) else None
check("R1b must not fire: the JSON-list form, in either order, gives the same CANDIDATE naming the conflict, line for line",
      r2.returncode == 0 and len(bl) == 2 and all(lines == single_r1 and kinds(verdicts(lines)) == {P_A: "CANDIDATE"}
                                                  and "10.5555/r1.b against the page's 10.5555/r1.a" in verdicts(lines)[P_A][1]
                                                  for _h, lines in bl), out(r2))
r, vd = look(R1V, {"arxiv": ["2601.00021", "2601.00022"]})
check("R1c must not fire: per arXiv id too (2601.00021 equal, 2601.00022 not): a CANDIDATE naming 2601.00022 against 2601.00021",
      kinds(vd) == {P_AX: "CANDIDATE"} and "the citation's arxiv 2601.00022 against the page's 2601.00021" in vd[P_AX][1], out(r))
r, vd = look(R1V, {"doi": ["10.5555/r1.c", "10.5555/r1.d"]})
r2, vd2 = look(R1V, {"doi": ["10.5555/r1.d"]})
r3, vd3 = look(R1V, {"doi": ["10.5555/r1.c", "10.5555/r1.e"]})
check("R1d a page asserting two DOIs: both, or one alone, give MATCH; one of them beside a third is a CANDIDATE naming the third",
      kinds(vd) == {P_TWO: "MATCH"} and kinds(vd2) == {P_TWO: "MATCH"} and kinds(vd3) == {P_TWO: "CANDIDATE"}
      and "the citation's doi 10.5555/r1.e against the page's 10.5555/r1.c, 10.5555/r1.d" in vd3[P_TWO][1], out(r) + out(r2) + out(r3))
for label, c, pg in [("case, resolver and doi: forms of one DOI", {"doi": ["10.5555/R1.A", "https://doi.org/10.5555/r1.a", "doi:10.5555/r1.a"]}, P_A),
                     ("version, prefix, URL and DOI forms of one arXiv id",
                      {"arxiv": ["2601.00021", "2601.00021v3", "arXiv:2601.00021v1"], "doi": ["10.48550/arXiv.2601.00021"],
                       "url": ["https://arxiv.org/abs/2601.00021v2"]}, P_AX)]:
    r, vd = look(R1V, c)
    rl = lrun(R1V, "--list", listfile("r1-equiv.jsonl", json.dumps(c) + "\n"))
    bl = blocks(rl.stdout)
    check(f"R1e the {label} are one identifier: MATCH alone and as a list",
          kinds(vd) == {pg: "MATCH"} and rl.returncode == 0 and len(bl) == 1 and kinds(verdicts(bl[0][1])) == {pg: "MATCH"}, out(r) + out(rl))

print("== review fold R2: a frontmatter value is read as YAML reads it, or refused ==")
R2_HEX = doc('title: "Paper: Hex Escape Fixture Study"', r'doi: "10.5555/r2a\x62"')
R2V = mkvault("lk-r2", {S + "r2-hex.md": R2_HEX})
r, vd = look(R2V, {"doi": "10.5555/r2ax62"})
r2, vd2 = look(R2V, {"doi": "10.5555/r2ab"})
check('R2a must not fire: `doi: "10.5555/r2a\\x62"` is 10.5555/r2ab, as YAML reads it: the letters ax62 never match, ab gives MATCH',
      kinds(vd) == {"NO MATCH": "NO MATCH"} and kinds(vd2) == {S + "r2-hex.md": "MATCH"}, out(r) + out(r2))
R2Q = mkvault("lk-r2q", {S + "r2-hex.md": R2_HEX, S + "r2-bad-escape.md": doc('title: "Paper: Bad Escape Fixture Study"', r'doi: "10.5555/r2a\q"')})
r = lrun(R2Q, "--doi", "10.5555/r2aq")
r2 = lrun(R2Q, "--title", "Hex Escape Fixture Study")
check("R2b must not fire: an escape YAML does not define (\\q) exits 2 naming the page and the escape, and no citation gets a verdict",
      failed(r, "r2-bad-escape.md: the frontmatter does not parse as YAML") and failed(r2, "found unknown escape character 'q'"),
      out(r) + out(r2))
# Each frontmatter below with the value YAML reads (a YAML 1.2 reader gives the same), or the refusal it gets.
YAML_VALUES = [
    (r'doi: "10.5555/a\x62"', "doi", ["10.5555/ab"]),
    ('title: "' + r'\0\a\b\t\n\v\f\r\e\ \"\/\\\N\_\L\P' + '\\\t"', "title",
     "\x00\x07\x08\t\n\x0b\x0c\r\x1b \"/\\\x85\xa0\U00002028\U00002029\t"),
    ('title: "\\x41\\u00e9\\U0001F600"', "title", "A\U000000e9\U0001F600"),
    (r"title: 'single \x62 ''quoted'''", "title", "single \\x62 'quoted'"),
    (r"doi: 10.5555/plain\x62#x # a comment", "doi", ["10.5555/plain\\x62#x"]),
    ('title: "A Title Here" # a comment', "title", "A Title Here"),
    ("title: # an empty value and a comment", "title", ""),
    ("title:", "title", ""),
    ('authors: ["", "Ann Able"]', "authors", ["", "Ann Able"]),
    ("authors:\n  -\n  - Ann Able", "authors", ["", "Ann Able"]),
    ("authors:\n  - # a note\n  - Ann Able", "authors", ["", "Ann Able"]),
    ("authors: # the list\n  - Ann Able", "authors", ["Ann Able"]),
    ("authors: [Ann Able, 'Bo, Baker', \"C\\x2e Coe\",]", "authors", ["Ann Able", "Bo, Baker", "C. Coe"]),
    ('title: "A\tTitle Here" # a comment\twith a tab', "title", "A\tTitle Here"),
]
YAML_REFUSED = [
    (r'doi: "10.5555/a\q"', "found unknown escape character 'q'"),
    (r'doi: "10.5555/a\x6"', "expected escape sequence of 2 hexadecimal numbers"),
    (r'doi: "10.5555/a\xZZ"', "expected escape sequence of 2 hexadecimal numbers"),
    (r'doi: "10.5555/a\u12"', "expected escape sequence of 4 hexadecimal numbers"),
    (r'doi: "10.5555/a\U0010FFF"', "expected escape sequence of 8 hexadecimal numbers"),
    (r'doi: "10.5555/a\U00110000"', "chr() arg not in range"),
    (r'title: "A Title \uD800 Here"', "U+D800, a UTF-16 surrogate half"),
    ('doi: "10.5555/a\\', "does not parse as YAML"),
    ("title: Paper: A Title", "mapping values are not allowed here"),
    ("doi: - 10.5555/a", "sequence entries are not allowed here"),
    ("authors: [Ann Able, # first]", "does not parse as YAML: while parsing a flow node"),
    ("authors: [Ann Able,, Bo Baker]", "expected the node content, but found ','"),
    ("authors: [Ann: Able]", "authors: a list holding a mapping"),
    ('authors: ["Ann"#c]', "expected ',' or ']'"),
    ("authors:\n\t- Ann Able", "found character '\\t' that cannot start any token"),
    ('title: "A \x01 Title"', "U+0001"),
    ('title: "A \x85 Title"', "U+0085"),
    ("title: A\U00002028doi: 10.5555/ls", "U+2028"),
    ("doi:\t10.5555/a", "cannot start any token"),
    ("title: A\tTitle Here", "cannot start any token"),
    ('title: "A Title Here"\t# a comment', "cannot start any token"),
    ("authors: [Ann Able,\tBo Baker]", "cannot start any token"),
    ("authors:\n  -\tAnn Able", "cannot start any token"),
    ("sources: [https://example.test/p?q=1]", "expected ',' or ']', but got '?'"),
    ("authors: [:Ann Able]", "expected the node content, but found ':'"),
    ("title: []", "a list where one value belongs"),
    ('title: "A Title"\ntitle: "Another Title"', "the key 'title' is given twice"),
    ('doi: "10.5555/a"\nDOI: "10.5555/b"', "the key 'DOI' is given twice (also as 'doi')"),
    ('meta:\n  a: one\n  a: two\ndoi: "10.5555/b"', "given twice in a nested mapping"),
    ('base: &b {doi: 10.5555/m}\n<<: *b\ntitle: "A Title"', "a merge key << at the top level"),
    ("x" * 1025 + ': ignored\ndoi: "10.5555/a"', "mapping values are not allowed here (block line 1, column 1026)"),
    ("- a list item\n- another", "not a mapping (YAML reads a list there)"),
    ("A line of prose and nothing else", "not a mapping (YAML reads a single value there)"),
]
# Forms the hand-written reader refused that YAML reads, each with the value it reads: a quoted or plain value
# continued over lines, an escaped line break, a block scalar, a comment inside a [ list over lines
YAML_NOW_READ = [
    ('title: "A long title\n  continued here"', "title", "A long title continued here"),
    ('doi: "10.5555/\\\n  abc"', "doi", ["10.5555/abc"]),
    ("title: >-\n  A folded title", "title", "A folded title"),
    ("title: |\n  A literal title", "title", "A literal title"),
    ("authors: [Ann Able, # first\n  Bo Baker]", "authors", ["Ann Able", "Bo Baker"]),
    ("authors:\n  - Ann Able\n    - Bo Baker", "authors", ["Ann Able - Bo Baker"]),
    ("title: A plain title\n  continued here", "title", "A plain title continued here"),
]


def read_or_refusal(mod, block):
    try:
        return ("value", mod.parse_front_fields(block, "fixture.md"))
    except Exception as e:
        return ("refused" if mod and type(e).__name__ == "LookupPremise" else "error", str(e) or repr(e))


wrong_v = [(b, got) for b, key, want in YAML_VALUES for got in [read_or_refusal(LK_MOD, b)]
           if got[0] != "value" or got[1].get(key) != want] if LK_MOD else ["no lookup module"]
check(f"R2c {len(YAML_VALUES)} frontmatter values read as YAML reads them: every escape decoded, quotes and comments, empty items kept",
      not wrong_v, "\n".join(repr(w) for w in wrong_v))
wrong_r = [(b, got) for b, phrase in YAML_REFUSED for got in [read_or_refusal(LK_MOD, b)]
           if got[0] != "refused" or phrase not in got[1]] if LK_MOD else ["no lookup module"]
check(f"R2d {len(YAML_REFUSED)} blocks YAML does not parse, or that the reader refuses beyond the parse (a surrogate half, "
      "a key given twice, a merge key, a NEL, LS or PS, a top level that is no mapping, a field holding no value or list of "
      "values), are refused with their reason", not wrong_r, "\n".join(repr(w) for w in wrong_r))
wrong_n = [(b, got) for b, key, want in YAML_NOW_READ for got in [read_or_refusal(LK_MOD, b)]
           if got[0] != "value" or got[1].get(key) != want] if LK_MOD else ["no lookup module"]
check(f"Y5a {len(YAML_NOW_READ)} forms the hand-written reader refused (a value over lines, an escaped line break, block "
      "scalars, a comment in a [ list over lines) read as YAML reads them", not wrong_n, "\n".join(repr(w) for w in wrong_n))
for name, text, title in [("multi-line title", doc('title: "Paper: A Title Spread', '  Over Two Lines"'), "A Title Spread Over Two Lines"),
                          ("block scalar", doc("title: >-", "  Paper: A Folded Title Here"), "A Folded Title Here")]:
    v = mkvault(f"lk-r2-{name.replace(' ', '-')}", {S + "good.md": doc('title: "Paper: A Healthy Page Beside It"'), S + "odd.md": text})
    r, vd = look(v, {"title": "A Healthy Page Beside It"})
    r2, vd2 = look(v, {"title": title})
    check(f"R2e a page with a {name} is read as YAML reads it (its title {title!r} gives its CANDIDATE), and the healthy "
          "page beside it gets its verdict (it was exit 2)",
          kinds(vd) == {S + "good.md": "CANDIDATE"} and kinds(vd2) == {S + "odd.md": "CANDIDATE"}, out(r) + out(r2))
try:
    m_r2 = lk_load()
    n_value = sum(1 for n, _i, _e in m_r2.LOOKUP_SELF_TEST if n == "value")
    n_refused = sum(1 for n, _i, e in m_r2.LOOKUP_SELF_TEST if n == "refused" and e is True)
    undecoded = m_r2.lookup_self_test({"value": lambda s: s.strip().strip("\"'")})
    accepting = m_r2.lookup_self_test({"refused": lambda s: False})
    ok = (n_value >= 4 and n_refused >= 3 and len(undecoded) == n_value and len(accepting) == n_refused
          and m_r2.lookup_self_test() == [])
    detail = f"value cases {n_value}, refusal cases {n_refused}; undecoded caught {len(undecoded)}, accepting caught {len(accepting)}"
except Exception as e:
    ok, detail = False, f"error: {e!r}"
check("R2f the lookup self-test catches a planted reader that leaves escapes undecoded, and one that accepts what YAML refuses", ok, detail)

print("== review fold R3: the controls cover the evidence an index holds, each with the verdict it is owed ==")
R3URL = mkvault("lk-r3-url", {S + "r3-url.md": doc('title: "Doc"', "doi: https://doi.org/10.5555/r3.a")})
R3SH = mkvault("lk-r3-shared", {S + "r3-s1.md": doc('title: "Doc"', 'doi: "10.5555/r3.s"'),
                                S + "r3-s2.md": doc('title: "Doc Two"', 'doi: "10.5555/r3.s"')})
R3SL = mkvault("lk-r3-slug", {S + "smith-2019-widget-notes.md": doc('title: "Doc"')})
r, vd = look(R3URL, {"doi": "10.5555/r3.a"})
r2, vd2 = look(R3URL, {"url": "https://doi.org/10.5555/r3.a"})
check("R3a a canonical-URL index (doi: https://doi.org/...) answers: --doi and the URL each give MATCH, and its url control is owed MATCH and gets it",
      kinds(vd) == {S + "r3-url.md": "MATCH"} and kinds(vd2) == {S + "r3-url.md": "MATCH"}
      and "url MATCH at wiki/sources/r3-url.md" in r.stdout and "identity MATCH at wiki/sources/r3-url.md" in r.stdout, out(r) + out(r2))
r, vd = look(R3SH, {"doi": "10.5555/r3.s"})
check("R3b a shared-identifier index answers: two CANDIDATEs, neither singled out, and its shared-identifier control names both",
      kinds(vd) == {S + "r3-s1.md": "CANDIDATE", S + "r3-s2.md": "CANDIDATE"} and "so none is singled out" in vd[S + "r3-s1.md"][1]
      and "shared identifier CANDIDATE at wiki/sources/r3-s1.md, wiki/sources/r3-s2.md" in r.stdout, out(r))
r, vd = look(R3SL, {"author": "J. Smith", "year": 2019})
check("R3c a slug-only index answers: its page is a CANDIDATE by the file name's author-year, and its slug control ran",
      kinds(vd) == {S + "smith-2019-widget-notes.md": "CANDIDATE"}
      and "slug author-year CANDIDATE at wiki/sources/smith-2019-widget-notes.md" in r.stdout, out(r))
DEFECTS = {
    "a dead matcher": lambda real, idx, cit: (["NO MATCH (planted)"], {}, []),
    "a matcher reaching every page": lambda real, idx, cit: ([f"CANDIDATE {p} (planted)" for p in idx.pages], {}, []),
    "MATCH demoted to CANDIDATE": lambda real, idx, cit: (["CANDIDATE " + ln[6:] if ln.startswith("MATCH ") else ln
                                                           for ln in real(idx, cit)[0]], {}, []),
    "a CANDIDATE promoted to MATCH": lambda real, idx, cit: ([("MATCH " + ln[10:]) if k == 0 and ln.startswith("CANDIDATE ") else ln
                                                              for k, ln in enumerate(real(idx, cit)[0])], {}, []),
    "an equal URL promoted to MATCH": lambda real, idx, cit: ([("MATCH " + ln[10:]) if ln.startswith("CANDIDATE ") and "url = " in ln else ln
                                                               for ln in real(idx, cit)[0]], {}, [])}


def with_defect(defect, vault, argv):
    """An in-process lookup whose matcher carries a planted defect: (exit code, output)."""
    sab = lk_load()
    real = sab.lookup_work
    sab.lookup_work = lambda idx, cit: DEFECTS[defect](real, idx, cit)
    return inproc(sab, ["--vault-root", vault, *argv])


R3BLOG = mkvault("lk-r3-blog", {S + "blog.md": doc('title: "Source: A Blog Post About Widgets"', "source_url: https://blog.example.test/p/widgets")})
for name, vault, argv, defects in [
        ("canonical-URL", R3URL, ["--doi", "10.5555/r3.a"], ["a dead matcher", "a matcher reaching every page", "MATCH demoted to CANDIDATE"]),
        ("shared-identifier", R3SH, ["--doi", "10.5555/r3.s"], ["a dead matcher", "a matcher reaching every page", "a CANDIDATE promoted to MATCH"]),
        ("slug-only", R3SL, ["--author", "J. Smith", "--year", "2019"], ["a dead matcher", "a matcher reaching every page", "a CANDIDATE promoted to MATCH"]),
        ("plain-URL", R3BLOG, ["--url", "https://blog.example.test/p/widgets"], ["a dead matcher", "an equal URL promoted to MATCH"])]:
    healthy = lrun(vault, *argv)
    caught, texts = {}, []
    for d in defects:
        try:
            code, text = with_defect(d, vault, argv)
        except Exception as e:
            code, text = None, f"error: {e!r}"
        caught[d] = code == 2 and "same-run control failed" in text and not VERDICT_LINE.search(text)
        texts.append(f"[{d}] exit {code}: {text.strip()[:300]}")
    check(f"R3d the {name} index runs (exit 0), and its controls fail it, with no verdict, under each planted defect ({', '.join(defects)})",
          healthy.returncode == 0 and all(caught.values()), out(healthy) + "\n".join(texts))

print("== review fold R4: coverage and the index summary count source pages as unions, and agree ==")
R4V = mkvault("lk-r4", {S + "smith-2020.md": doc('title: "Smith Notes"', "sources: [raw/x/smith-2020-raw.md]"),
                        "raw/x/smith-2020-raw.md": doc('title: "A Raw Title For The Smith Study"', "authors: [J. Smith]",
                                                       "year: 2020", 'doi: "10.5555/r4.smith"')})
P_SM = S + "smith-2020.md"
COV_PATTERNS = {"arxiv": r"\barxiv on (\d+) \(\d+ asserted in the page's own identity field\)",
                "doi": r"\bdoi on (\d+) \(\d+ asserted in the page's own identity field\)",
                "title or alias": r"\btitle or alias on (\d+) \(title \d+, alias \d+;",
                "author-year": r"\bauthor-year on (\d+) \(\d+ from the file name or an alias only; \d+ pages' authors or year unusable\)",
                "url": r"\burl on (\d+)"}
SUM_PATTERNS = {"arxiv": r"\barxiv (\d+) \(identity \d+\)",
                "doi": r"\bdoi (\d+) \(identity \d+\)",
                "title or alias": r"· title or alias (\d+) \(title \d+, alias \d+\)",
                "author-year": r"· author-year (\d+) \(slug only \d+\)",
                "url": r"· url (\d+)"}


def counts(text, patterns):
    """{kind: source pages reached} read from one line."""
    got = {}
    for kind, pat in patterns.items():
        m = re.search(pat, text or "")
        if m:
            got[kind] = int(m.group(1))
    return got


r, vd = look(R4V, {"author": "Smith", "year": 2020})
r2, vd2 = look(R4V, {"doi": "10.5555/r4.smith"})
r3, vd3 = look(R4V, {"title": "A Raw Title For The Smith Study"})
check("R4a control: the one-page fixture's page is reached by its file name's author-year (a CANDIDATE labelled slug); the "
      "doi and the title held only in its raw file reach nothing (raw files are not searched)",
      kinds(vd) == {P_SM: "CANDIDATE"} and "(slug)" in vd[P_SM][1] and kinds(vd2) == {"NO MATCH": "NO MATCH"}
      and kinds(vd3) == {"NO MATCH": "NO MATCH"}, out(r) + out(r2) + out(r3))
r, vd = look(R4V, {"doi": "10.5555/r4.none", "title": "Some Other Title Entirely Here", "author": "Nobody", "year": 1999})
cov_line = (vd or {}).get("NO MATCH", ("", ""))[1]
index_line = next((ln for ln in r.stdout.splitlines() if ln.startswith("index: ")), "")
cc, sc = counts(cov_line, COV_PATTERNS), counts(index_line, SUM_PATTERNS)
check("R4b must not fire: that page counts once, by the one family its own page gives (doi 0, title or alias 0, author-year 1)",
      cc.get("doi") == 0 and cc.get("title or alias") == 0 and cc.get("author-year") == 1, out(r) + f"\n     read {cc}")
check("R4c the index summary carries the same totals (doi 0, title or alias 0, author-year 1)",
      sc.get("doi") == 0 and sc.get("title or alias") == 0 and sc.get("author-year") == 1
      and all(sc.get(k) == v for k, v in cc.items()), out(r) + f"\n     coverage {cc}\n     summary {sc}")
r = lrun(CV, "--doi", "10.5555/zzz.9", "--arxiv", "2109.99999", "--title", "Some Other Title Entirely", "--author", "Nobody",
         "--year", "1999", "--url", "https://nowhere.example.test/x")
b = blocks(r.stdout)
cc = counts(next((ln for ln in (b[0][1] if b else []) if ln.startswith("NO MATCH")), ""), COV_PATTERNS)
sc = counts(next((ln for ln in r.stdout.splitlines() if ln.startswith("index: ")), ""), SUM_PATTERNS)
check("R4d on the coverage fixture the coverage line and the index summary agree for all five kinds (doi 2: the page whose "
      "doi sits only in its raw file is not counted)", len(cc) == 5 and cc == sc and cc.get("doi") == 2,
      f"coverage {cc} summary {sc}\n" + out(r))

# ================================================================================================
# The fold of the build's re-review (R5, R6f), as the BaseLoader reader holds it. A value YAML reads over
# several lines never makes a field of its own, since the whole block is parsed and the fields are YAML's
# (R5); and Fixture B's block on a source page is read as YAML reads it (R6f). The raw-file legs of R6
# held the raw join, which this build leaves out. Where the hand-written reader refused a form YAML
# reads, the leg asks for YAML's reading, so it fails on the build that refused it. The tables are
# literals, so a YAML parser can be run beside them.
# ================================================================================================
print("== re-review fold R5: a value YAML reads over several lines never makes a field of its own ==")
R5_PAGE = S + "quoted-note.md"
R5_HEALTHY = doc('title: "Paper: A Healthy Page Beside It"', 'doi: "10.5555/r5.healthy"')


def r5_vault(name, text):
    """A vault of a healthy page and the page under test, R5_PAGE."""
    return mkvault(f"lk-r5-{name}", {S + "healthy.md": R5_HEALTHY, R5_PAGE: text})


FIXTURE_A_LINES = ('notes: "starts', "doi: 10.5555/a", 'extra: ends"', 'title: "Paper: A Healthy Control Page"')
FIXTURE_A = doc(*FIXTURE_A_LINES)
R5A = r5_vault("fixture-a", FIXTURE_A)
r, vd = look(R5A, {"doi": "10.5555/a"})
r2 = lrun(R5A, "--list", listfile("r5-fixture-a.jsonl", json.dumps({"id": "fixture-a", "doi": "10.5555/a"}) + "\n"
                                  + json.dumps({"id": "healthy", "doi": "10.5555/r5.healthy"}) + "\n"))
bl = blocks(r2.stdout)
check("R5a must not fire: Fixture A (a doi: line inside a quoted notes: value YAML reads over three lines) is read as YAML "
      "reads it, notes `starts doi: 10.5555/a extra: ends` and no DOI: NO MATCH, alone and in a list beside the healthy "
      "page's MATCH (it was a MATCH, then exit 2)",
      read_or_refusal(LK_MOD, "\n".join(FIXTURE_A_LINES)) == ("value", {"title": "Paper: A Healthy Control Page"})
      and kinds(vd) == {"NO MATCH": "NO MATCH"} and r2.returncode == 0 and len(bl) == 2
      and kinds(verdicts(bl[0][1])) == {"NO MATCH": "NO MATCH"} and kinds(verdicts(bl[1][1])) == {S + "healthy.md": "MATCH"},
      out(r) + out(r2))
for name, how, text, cite, want in [
        ("single-quoted", "a doi: line inside a single-quoted value YAML reads over three lines, so no DOI",
         doc("notes: 'starts", "doi: 10.5555/a", "extra: ends'", 'title: "Paper: A Healthy Control Page"'),
         "10.5555/a", "NO MATCH"),
        ("mapping-over-lines", "a doi: line inside a { mapping YAML reads over three lines, so no top-level DOI",
         doc("meta: {a: one,", "doi: 10.5555/a,", "extra: ends}", 'title: "Paper: A Healthy Control Page"'),
         "10.5555/a,", "NO MATCH"),
        ("return-in-comment", "a doi: line after a carriage return in a comment, which every YAML version reads as a "
         "line break, so a field", doc('title: "Paper: A Healthy Control Page"', "# a note\rdoi: 10.5555/r5.cr"),
         "10.5555/r5.cr", "MATCH")]:
    r, vd = look(r5_vault(name, text), {"doi": cite})
    check(f"R5b Fixture A's variant ({how}) gives YAML's reading: {want} (it was exit 2)",
          kinds(vd) == ({R5_PAGE: "MATCH"} if want == "MATCH" else {"NO MATCH": "NO MATCH"}), out(r))
for name, how, text, cite, phrase in [
        ("list-over-lines", "a doi: line inside a [ list over three lines, which YAML does not parse",
         doc("tags: [alpha,", "doi: 10.5555/a", "extra: omega]", 'title: "Paper: A Healthy Control Page"'),
         "10.5555/a", "the frontmatter does not parse as YAML: while parsing a flow sequence"),
        ("nel-in-comment", "a doi: line after a NEL in a comment, a line YAML 1.1 reads and YAML 1.2 does not",
         doc('title: "Paper: A Healthy Control Page"', "# a note\x85doi: 10.5555/r5.nel"),
         "10.5555/r5.nel", "the character U+0085")]:
    r = lrun(r5_vault(name, text), "--doi", cite)
    check(f"R5b must not fire: Fixture A's variant ({how}) exits 2 naming it ({phrase}), with no verdict",
          failed(r, R5_PAGE + ": " + phrase), out(r))
for name, lines in [("open-double-quote", ['notes: "never closed']), ("open-single-quote", ["notes: 'never closed"]),
                    ("open-list", ["tags: [alpha, beta"]), ("open-quote-in-item", ["keywords:", '  - "never closed'])]:
    r = lrun(r5_vault(name, doc(*lines, 'title: "Paper: A Healthy Control Page"', 'doi: "10.5555/r5.open"')),
             "--doi", "10.5555/r5.open")
    check(f"R5c must not fire: an unclosed quote or [ list in a field the lookup does not use ({lines[-1].strip()}) leaves the "
          "block unparsed: exit 2 naming the page and PyYAML's reason, with no verdict (the page's own doi was a MATCH)",
          failed(r, R5_PAGE + ": the frontmatter does not parse as YAML"), out(r))
for name, lines in [("block-scalar", ["notes: |", "  doi: 10.5555/r5.inside"]), ("nested-mapping", ["meta:", "  sub: one"]),
                    ("plain-continued", ["notes: starts", "  more words"]), ("flow-mapping", ["meta: {a: one}"])]:
    v = r5_vault(name, doc(*lines, 'title: "Paper: A Healthy Control Page"', 'doi: "10.5555/r5.form"'))
    r, vd = look(v, {"doi": "10.5555/r5.form"})
    r2, vd2 = look(v, {"doi": "10.5555/r5.inside"})
    check(f"R5d a field the lookup does not use, in a form YAML reads ({name.replace('-', ' ')}), is set aside: the page's own "
          "doi gives MATCH, and a doi: line inside it is no field (it was exit 2)",
          kinds(vd) == {R5_PAGE: "MATCH"} and kinds(vd2) == {"NO MATCH": "NO MATCH"}, out(r) + out(r2))
for name, lines, phrase in [("given-twice", ["notes: one", "notes: two"], "the key 'notes' is given twice"),
                            ("plain-mapping", ["notes: a: b"], "mapping values are not allowed here")]:
    r = lrun(r5_vault(name, doc(*lines, 'title: "Paper: A Healthy Control Page"', 'doi: "10.5555/r5.form"')),
             "--doi", "10.5555/r5.form")
    check(f"R5d a field the lookup does not use, in a form YAML does not allow ({name.replace('-', ' ')}), exits 2 naming it "
          f"({phrase}), with no verdict", failed(r, R5_PAGE + ": ") and phrase in r.stdout, out(r))
GUARD_R5 = doc("type: source", "notes: plain words and a C# note", 'summary: "a quoted value: with a colon and a # sign"',
               "extra: 'single ''quoted'' value'", 'tags: [alpha, "beta, gamma", delta]', "keywords:", "  - one",
               '  - "two: quoted"', "empty:", "# a comment line", 'title: "Paper: Every Form Beside The Fields"',
               "doi: 10.5555/r5.guard")
r, vd = look(r5_vault("guard", GUARD_R5), {"doi": "10.5555/r5.guard"})
r2, vd2 = look(r5_vault("one-line", doc('notes: "starts doi: 10.5555/a extra: ends"', 'title: "Paper: A Healthy Control Page"')),
               {"doi": "10.5555/a"})
check("R5e guard: a genuine doi: field beside fields of every form this reader reads (plain, quoted, [ list, block list, "
      "empty, comment) still gives MATCH; Fixture A's value written on one line, as YAML reads it, holds no DOI (NO MATCH)",
      kinds(vd) == {R5_PAGE: "MATCH"} and kinds(vd2) == {"NO MATCH": "NO MATCH"}, out(r) + out(r2))
# Whole blocks, each with the lookup fields YAML reads in it (every other field read and set aside); blocks whose
# values carry white space YAML does not strip; and blocks refused, with the reason, wherever the form sits
YAML_DOCS = [
    ('notes: "starts doi: 10.5555/a extra: ends"\ntitle: "Paper: A Healthy Control Page"',
     {"title": "Paper: A Healthy Control Page"}),
    ("type: source\nnotes: plain words and a C# note\nsummary: \"a quoted value: with a colon and a # sign\"\n"
     "extra: 'single ''quoted'' value'\ntags: [alpha, \"beta, gamma\", delta]\nkeywords:\n  - one\n  - \"two: quoted\"\n"
     "empty:\n# a comment line\ntitle: \"Paper: Every Form Beside The Fields\"\ndoi: 10.5555/docs.1\nauthors:\n- Ann Able\n- Bo Baker",
     {"title": "Paper: Every Form Beside The Fields", "doi": ["10.5555/docs.1"], "authors": ["Ann Able", "Bo Baker"]}),
    ('title: "Paper: A CRLF Page"\r\ndoi: 10.5555/docs.crlf\r\n# a comment\r\n',
     {"title": "Paper: A CRLF Page", "doi": ["10.5555/docs.crlf"]}),
    ("# only a comment\n\n# and another", {}),
    ('keywords:\n  - "an item holding doi: 10.5555/docs.no"\ntitle: A Plain Title Here', {"title": "A Plain Title Here"}),
]
YAML_DOCS_WHITE = [
    ("title: \xa0A Title After A No-Break Space\ndoi: 10.5555/docs.nbsp\xa0",
     {"title": "\xa0A Title After A No-Break Space", "doi": ["10.5555/docs.nbsp\xa0"]}),
    ("authors: [Ann Able\U00002009, \U00003000Bo Baker]\naliases:\n  - \xa0An Alias Of Four",
     {"authors": ["Ann Able\U00002009", "\U00003000Bo Baker"], "aliases": ["\xa0An Alias Of Four"]}),
]
RAW_FIELDS = {"title": "Raw Known Work Title", "doi": ["10.5555/raw"]}
# Whole blocks the hand-written reader refused that YAML reads, each with the lookup fields YAML reads in it: Fixture A
# and its variants, forms in fields the lookup does not use, a carriage return, an anchor, and the key forms of
# Fixture B and Fixture C (a mapping behind a quoted, indented or spaced key, a flow mapping, a complex key, or node
# properties above it, with a comment beside them or below)
YAML_DOCS_NOW_READ = [
    ('notes: "starts\ndoi: 10.5555/a\nextra: ends"\ntitle: "Paper: A Healthy Control Page"', {"title": "Paper: A Healthy Control Page"}),
    ("notes: 'starts\ndoi: 10.5555/a\nextra: ends'", {}),
    ("meta: {a: one,\ndoi: 10.5555/a,\nextra: ends}", {}),
    ('notes: |\n  doi: 10.5555/a\ndoi: "10.5555/b"', {"doi": ["10.5555/b"]}),
    ('meta:\n  sub: one\ndoi: "10.5555/b"', {"doi": ["10.5555/b"]}),
    ('notes: starts\n  more words\ndoi: "10.5555/b"', {"doi": ["10.5555/b"]}),
    ('meta: {a: one}\ndoi: "10.5555/b"', {"doi": ["10.5555/b"]}),
    ('notes: &anchor one\ndoi: "10.5555/b"', {"doi": ["10.5555/b"]}),
    ('title: "A Title"\n# a note\rdoi: 10.5555/cr', {"title": "A Title", "doi": ["10.5555/cr"]}),
    ('notes: one\rdoi: 10.5555/cr\ntitle: "A Title"', {"doi": ["10.5555/cr"], "title": "A Title"}),
    ('"title": "Raw Known Work Title"\ndoi: 10.5555/raw', RAW_FIELDS),
    ("'title': 'Raw Known Work Title'\ndoi: 10.5555/raw", RAW_FIELDS),
    ('  title: "Raw Known Work Title"\n  doi: 10.5555/raw', RAW_FIELDS),
    ('{title: "Raw Known Work Title", doi: 10.5555/raw}', RAW_FIELDS),
    ('title : "Raw Known Work Title"\ndoi : 10.5555/raw', RAW_FIELDS),
    ('? title\n: "Raw Known Work Title"\ndoi: 10.5555/raw', RAW_FIELDS),
    ('&meta\ntitle: "Raw Known Work Title"\ndoi: 10.5555/raw', RAW_FIELDS),
    ('&root # comment\ntitle: "Raw Known Work Title"\ndoi: 10.5555/raw', RAW_FIELDS),
    ('&root\n# comment\ntitle: "Raw Known Work Title"\ndoi: 10.5555/raw', RAW_FIELDS),
    ('!!map # comment\ntitle: "Raw Known Work Title"\ndoi: 10.5555/raw', RAW_FIELDS),
    ('&root\n!!map\ntitle: "Raw Known Work Title"\ndoi: 10.5555/raw', RAW_FIELDS),
    ('!!map\n&root\ntitle: "Raw Known Work Title"\ndoi: 10.5555/raw', RAW_FIELDS),
]
# Whole blocks refused, with the reason, wherever the form sits: what YAML does not parse, and what YAML readers part on
YAML_DOCS_REFUSED = [
    ("tags: [alpha,\ndoi: 10.5555/a\nextra: omega]", "while parsing a flow sequence"),
    ("tags: [alpha,\n  beta,\ndoi: 10.5555/a\nextra: omega]", "while parsing a flow sequence"),
    ('notes: "never closed\ndoi: "10.5555/u"', "does not parse as YAML"),
    ('keywords:\n  - "never closed\ndoi: "10.5555/u"', "does not parse as YAML"),
    ('notes: one\nnotes: two\ndoi: "10.5555/b"', "the key 'notes' is given twice"),
    ('notes: a: b\ndoi: "10.5555/b"', "mapping values are not allowed here"),
    ('title: "A Title"\n# a note\x85doi: 10.5555/nel', "the character U+0085 (block line 2)"),
    ('title: "A Title"\n# a note\U00002029doi: 10.5555/ps', "the character U+2029 (block line 2)"),
    ('title: "A Title"\n\t\ndoi: "10.5555/b"', "cannot start any token"),
    ('title: "A Title"\n\t# a note\ndoi: "10.5555/b"', "cannot start any token"),
    ('title: "A Title"\n...\ndoi: 10.5555/a', "expected '<document start>'"),
    ('title: "A Title"\n\xa0\ndoi: 10.5555/a', "could not find expected ':'"),
]
wrong_d = [(b, got) for b, want in YAML_DOCS for got in [read_or_refusal(LK_MOD, b)]
           if got != ("value", want)] if LK_MOD else ["no lookup module"]
check(f"R5f guard: {len(YAML_DOCS)} whole blocks read as YAML reads them, every lookup field and no other (Fixture A's "
      "value on one line has no doi; an item holding `doi:` is no field)", not wrong_d, "\n".join(repr(w) for w in wrong_d))
wrong_w = [(b, got) for b, want in YAML_DOCS_WHITE for got in [read_or_refusal(LK_MOD, b)]
           if got != ("value", want)] if LK_MOD else ["no lookup module"]
check(f"R5g {len(YAML_DOCS_WHITE)} blocks whose values carry white space YAML does not strip (a no-break, thin or "
      "ideographic space) read with it kept, as YAML reads them", not wrong_w, "\n".join(repr(w) for w in wrong_w))
wrong_r5 = [(b, got) for b, phrase in YAML_DOCS_REFUSED for got in [read_or_refusal(LK_MOD, b)]
            if got[0] != "refused" or phrase not in got[1]] if LK_MOD else ["no lookup module"]
check(f"R5h {len(YAML_DOCS_REFUSED)} whole blocks refused with their reason wherever the form sits: lists and quotes YAML "
      "does not close, a key given twice, a plain value holding ': ', a NEL or PS in a comment, tabs before a comment or "
      "in a blank line, a document end, a no-break space alone", not wrong_r5, "\n".join(repr(w) for w in wrong_r5))
wrong_n5 = [(b, got) for b, want in YAML_DOCS_NOW_READ for got in [read_or_refusal(LK_MOD, b)]
            if got != ("value", want)] if LK_MOD else ["no lookup module"]
check(f"Y5b {len(YAML_DOCS_NOW_READ)} whole blocks the hand-written reader refused, read as YAML reads them: Fixture A and "
      "its variants (no DOI), forms in fields the lookup does not use, a carriage return, an anchor, and the key forms of "
      "Fixtures B and C ({title, doi})", not wrong_n5, "\n".join(repr(w) for w in wrong_n5))

print("== re-review fold R6: Fixture B's block on a source page is read as YAML reads it ==")
FIXTURE_B = '---\n"title": "Raw Known Work Title"\ndoi: 10.5555/raw\n---\n\nbody\n'
v = mkvault("lk-r6-source", {S + "healthy.md": R5_HEALTHY, S + "quoted-key.md": FIXTURE_B})
r, vd = look(v, {"doi": "10.5555/raw"})
check("R6f must not fire: Fixture B's block on a source page is read as YAML reads it, a title and a doi, so its doi gives "
      "MATCH there (it was exit 2)", kinds(vd) == {S + "quoted-key.md": "MATCH"}, out(r))

# ================================================================================================
# The reader's replacement (Y1-Y7): the lookup parses each whole frontmatter block with PyYAML's
# BaseLoader, and refuses with exit 2 what does not parse and what YAML readers part on. Each review
# fixture gives YAML's reading or exits 2, never a silent absence. A guard passes on the hand-written
# reader too, as do two refusals it words alike (a line separator, a control character); every other
# leg here fails on it, by verdict or, where both exit 2, by the reason's wording.
# ================================================================================================
print("== reader Y1: Fixture C, node properties and a comment above the mapping, is read on a source page ==")
FIXTURE_C_PAGE = '---\n&root # comment\ntitle: "Paper: A Healthy Control Page"\ndoi: 10.5555/y1.c\n---\n'
v = mkvault("lk-y1-source", {S + "healthy.md": R5_HEALTHY, R5_PAGE: FIXTURE_C_PAGE})
r, vd = look(v, {"doi": "10.5555/y1.c"})
check("Y1s Fixture C's block (an anchor and a comment on the line above the mapping) on a source page is read as YAML reads "
      "it: its doi gives MATCH", kinds(vd) == {R5_PAGE: "MATCH"}, out(r))

print("== reader Y2: a key over YAML's 1,024-character limit exits 2; the 1,024 control is read ==")
Y2_PAGE = S + "long-key.md"
for name, n, want in [("1,025", 1025, "exit 2"), ("1,024", 1024, "MATCH")]:
    v = mkvault(f"lk-y2-{n}", {S + "healthy.md": R5_HEALTHY,
                               Y2_PAGE: doc("x" * n + ": ignored", 'title: "Paper: A Healthy Control Page"', "doi: 10.5555/y2.long")})
    r, vd = look(v, {"doi": "10.5555/y2.long"})
    rl = lrun(v, "--list", listfile(f"y2-{n}.jsonl", json.dumps({"id": "healthy", "doi": "10.5555/r5.healthy"}) + "\n"
                                    + json.dumps({"id": "long-key", "doi": "10.5555/y2.long"}) + "\n"))
    if want == "exit 2":
        phrase = Y2_PAGE + ": the frontmatter does not parse as YAML: mapping values are not allowed here (block line 1, column 1026)"
        check("Y2a must not fire: a source block holding a 1,025-character implicit key exits 2 naming PyYAML's reason, alone "
              "and in a list after a healthy entry, with no verdict (it was a MATCH)", failed(r, phrase) and failed(rl, phrase),
              out(r) + out(rl))
    else:
        bl = blocks(rl.stdout)
        check("Y2b guard: the same block with a 1,024-character key is read, so its doi gives MATCH, alone and in the list",
              kinds(vd) == {Y2_PAGE: "MATCH"} and rl.returncode == 0 and len(bl) == 2 and kinds(verdicts(bl[1][1])) == {Y2_PAGE: "MATCH"},
              out(r) + out(rl))

print("== reader Y3: without PyYAML the lookup exits 2 naming it; the de-dup probe runs without it ==")
HIDE_YAML = ("import os, runpy, sys; sys.modules['yaml'] = None; sys.argv = sys.argv[1:]; "
             "sys.path[0] = os.path.dirname(os.path.abspath(sys.argv[0])); runpy.run_path(sys.argv[0], run_name='__main__')")


def without_yaml(script, *args, hide=True, cwd=None):
    """script run as __main__ in a python3 where `import yaml` fails (hide), or the same wrapper with PyYAML left (control)."""
    code = HIDE_YAML if hide else HIDE_YAML.replace("sys.modules['yaml'] = None; ", "")
    return subprocess.run([sys.executable, "-B", "-c", code, script, *args], capture_output=True, text=True, cwd=cwd)


r = without_yaml(PROBE, "--lookup", "--vault-root", LKV, "--arxiv", "2205.14334")
rl = without_yaml(PROBE, "--lookup", "--vault-root", LKV, "--list", LIST_ALL)
rc = without_yaml(PROBE, "--lookup", "--vault-root", LKV, "--arxiv", "2205.14334", hide=False)
check("Y3a must not fire: with PyYAML unimportable the lookup exits 2 naming it (PyYAML cannot be imported), alone and for a "
      "list, with no verdict and no other reader tried; control: the same wrapper with PyYAML gives Lin's MATCH",
      failed(r, "PyYAML cannot be imported") and failed(rl, "PyYAML cannot be imported")
      and rc.returncode == 0 and f"MATCH {P_LIN} (" in rc.stdout, out(r) + out(rl) + out(rc))
rd = without_yaml(PROBE, "raw/paper-lost-in-the-middle.md", "--vault-root", v5)
rd0 = run(v5, "raw/paper-lost-in-the-middle.md")
check("Y3b guard: the de-dup probe needs no PyYAML: run where `import yaml` fails it prints exactly what it prints with it "
      "(CANDIDATE, exit 0)", rd.returncode == 0 and rd.stdout == rd0.stdout and bool(cands(rd)), out(rd) + out(rd0))
if os.path.isfile(GATHER):
    rg = without_yaml(GATHER, "dedup", "--vault-root", v9, "--titles", *TITLES9, "--control", "https://longcontexthub.test/papers/1", cwd=TMP)
    rg0 = subprocess.run([sys.executable, "-B", GATHER, "dedup", "--vault-root", v9, "--titles", *TITLES9,
                          "--control", "https://longcontexthub.test/papers/1"], capture_output=True, text=True, cwd=TMP)
    check("Y3c guard: gather's `capture_write.py dedup`, which loads this probe, needs no PyYAML either: identical output "
          "where `import yaml` fails", rg.returncode == 0 and rg.stdout == rg0.stdout and PAGE_REL in rg.stdout, out(rg) + out(rg0))
else:
    check("Y3c gather's capture_write.py beside this skill", False, f"needs: {GATHER} (the gather skill ships beside ingest)")

print("== reader Y4: escapes as YAML decodes them, or exit 2 ==")
for name, value, phrase in [("a surrogate half", r'"10.5555/y4\uD800"', "doi: U+D800, a UTF-16 surrogate half"),
                            ("a code point past U+10FFFF", r'"10.5555/y4\U00110000"', "chr() arg not in range"),
                            ("a hex escape one digit short", r'"10.5555/y4\x6"', "expected escape sequence of 2 hexadecimal numbers")]:
    v = r5_vault("y4-" + name.split()[-1], doc('title: "Paper: A Healthy Control Page"', "doi: " + value))
    r = lrun(v, "--doi", "10.5555/r5.healthy")
    rl = lrun(v, "--list", listfile("y4.jsonl", json.dumps({"id": "healthy", "doi": "10.5555/r5.healthy"}) + "\n"))
    check(f"Y4a {name} in a doi exits 2 naming the page ({phrase}), alone and in a list, with no verdict",
          failed(r, R5_PAGE + ": ") and phrase in r.stdout and failed(rl, phrase), out(r) + out(rl))
v = r5_vault("y4-decoded", doc('title: "Paper: A Healthy Control Page"', r'doi: "10.5555/y4\/\x41b"'))
r, vd = look(v, {"doi": "10.5555/y4/Ab"})
r2, vd2 = look(v, {"doi": "10.5555/y4\\/\\x41\\u0062"})
check("Y4b guard: YAML 1.2's escapes decode (\\/ to /, \\x41 to A, \\u0062 to b): the decoded DOI gives MATCH, its escaped "
      "letters reach nothing", kinds(vd) == {R5_PAGE: "MATCH"} and kinds(vd2) == {"NO MATCH": "NO MATCH"}, out(r) + out(r2))

print("== reader Y5: forms only YAML reads are read so ==")
v = mkvault("lk-y5-nocolon", {S + "good.md": doc('title: "Paper: A Healthy Page Beside It"'),
                              S + "nocolon.md": doc("type: source", 'title "Paper: Title Line Without Colon"', 'doi: "10.5555/nocolon.1"')})
r, vd = look(v, {"doi": "10.5555/nocolon.1"})
r2, vd2 = look(v, {"title": "Title Line Without Colon"})
check("Y5c a title line without its colon is read as YAML reads it, the key `title \"Paper` and no title field: the page's doi "
      "gives MATCH, the would-be title reaches nothing (it was exit 2)",
      kinds(vd) == {S + "nocolon.md": "MATCH"} and kinds(vd2) == {"NO MATCH": "NO MATCH"}, out(r) + out(r2))

print("== reader Y6: what YAML readers part on, and a top level that is no mapping, exit 2 ==")
for name, lines, phrase in [
        ("two spellings of doi", ['doi: "10.5555/y6.a"', 'DOI: "10.5555/y6.b"'], "the key 'DOI' is given twice (also as 'doi')"),
        ("a merge key", ["base: &b {doi: 10.5555/y6.m}", "<<: *b"], "a merge key << at the top level"),
        ("a line separator", ["notes: one\U00002028doi: 10.5555/y6.ls"], "the character U+2028"),
        ("a key twice in a nested mapping", ["meta:", "  a: one", "  a: two"], "given twice in a nested mapping")]:
    r = lrun(r5_vault("y6-" + name.split()[-1], doc('title: "Paper: A Healthy Control Page"', *lines)), "--doi", "10.5555/r5.healthy")
    check(f"Y6a {name} exits 2 naming the page ({phrase}), with no verdict", failed(r, R5_PAGE + ": ") and phrase in r.stdout, out(r))
for name, text, phrase in [("a list", "---\n- title: \"Paper: A Listed Page\"\n---\n\nbody\n", "not a mapping (YAML reads a list holding a mapping there)"),
                           ("a single value", "---\nA line of prose and nothing else\n---\n\nbody\n", "not a mapping (YAML reads a single value there)"),
                           ("an empty block", "---\n---\n\nbody\n", None)]:
    v = mkvault("lk-y6-top-" + name.split()[-1], {S + "healthy.md": R5_HEALTHY, R5_PAGE: text})
    r, vd = look(v, {"doi": "10.5555/r5.healthy"})
    if phrase:
        check(f"Y6b a source block YAML reads as {name} exits 2 naming the page ({phrase}), with no verdict",
              failed(r, R5_PAGE + ": the frontmatter is " + phrase), out(r))
    else:
        check("Y6b guard: an empty source block reads as no field (YAML reads nothing): the healthy page's MATCH stands",
              kinds(vd) == {S + "healthy.md": "MATCH"}, out(r))

# ================================================================================================
# The fold of the replacement's review, as source-page mode keeps it (Z2f's source half, Z4). Only a
# real merge key (one YAML 1.1 resolves as a merge) is refused; a << quoted or tagged !!str is an
# ordinary key. The raw-recognition legs (Z1-Z3) held the raw join, which this build leaves out.
# ================================================================================================
z_src = read_or_refusal(LK_MOD, "# a comment: only\n")
check("Z2f a source block of comments alone (one holding ': ') carries no field, as YAML reads it", z_src == ("value", {}), repr(z_src))

print("== fold Z4: only a real merge key is refused; a << quoted or tagged !!str is an ordinary key ==")
Z4_LINES = ('title: "Paper: A Healthy Control Page"', "doi: 10.5555/raw")
Z4_LITERAL = [("dq", "double-quoted", '"<<": harmless'), ("sq", "single-quoted", "'<<': harmless"),
              ("str", "tagged !!str", "!!str <<: harmless")]
Z4_MERGE = [("plain", "a plain << naming a mapping", ["<<: {note: harmless}", *Z4_LINES], "10.5555/raw",
             "a merge key << at the top level"),
            ("anchored", "an anchored plain <<", ["base: &b {note: harmless}", "&k <<: *b", *Z4_LINES], "10.5555/raw",
             "a merge key << at the top level"),
            ("tagged", "a key tagged !!merge whose mapping holds the page's only doi",
             ["base: &b {doi: 10.5555/z4.hidden}", "!!merge x: *b", Z4_LINES[0]], "10.5555/z4.hidden",
             "a merge key 'x' tagged !!merge at the top level")]


def z4_list(tag, doi):
    return listfile(f"z4-{tag}.jsonl", json.dumps({"id": "healthy", "doi": "10.5555/r5.healthy"}) + "\n"
                    + json.dumps({"id": "page", "doi": doi}) + "\n")


for tag, name, key in Z4_LITERAL:
    v = r5_vault("z4-" + tag, doc(key, *Z4_LINES))
    r, vd = look(v, {"doi": "10.5555/raw"})
    rl = lrun(v, "--list", z4_list(tag, "10.5555/raw"))
    bl = blocks(rl.stdout)
    check(f"Z4a must not fire: a literal key << ({name}) beside a healthy title and doi is an ordinary key to YAML 1.1 and 1.2 "
          "alike, so the genuine doi gives MATCH, alone and as a list's second entry (it was exit 2, called a merge key)",
          kinds(vd) == {R5_PAGE: "MATCH"} and rl.returncode == 0 and len(bl) == 2
          and kinds(verdicts(bl[1][1])) == {R5_PAGE: "MATCH"}, out(r) + out(rl))
for tag, name, lines, query, phrase in Z4_MERGE:
    v = r5_vault("z4-" + tag, doc(*lines))
    r = lrun(v, "--doi", query)
    rl = lrun(v, "--list", z4_list(tag, query))
    check(f"Z4b{' must not fire' if tag == 'tagged' else ' guard'}: {name} is a real merge key (PyYAML's SafeLoader merges "
          f"there, a YAML 1.2 reader reads a key): exit 2 naming the page ({phrase}), alone and in a list, with no verdict"
          + (" (it was NO MATCH: BaseLoader reads a key x, SafeLoader a top-level doi)" if tag == "tagged" else ""),
          failed(r, R5_PAGE + ": " + phrase) and failed(rl, phrase), out(r) + out(rl))
try:
    import yaml as YAML_ORACLE
except Exception:
    YAML_ORACLE = None
z4_rows = []
for b in [k + "\n" + "\n".join(Z4_LINES) for _t, _n, k in Z4_LITERAL] + ["\n".join(lines) for _t, _n, lines, _q, _p in Z4_MERGE]:
    try:
        part = YAML_ORACLE.load(b, Loader=YAML_ORACLE.BaseLoader) != YAML_ORACLE.load(b, Loader=YAML_ORACLE.SafeLoader)
    except Exception as e:
        part = f"oracle error {e!r}"
    z4_rows.append((b, part, read_or_refusal(LK_MOD, b)[0] == "refused"))
check("Z4c the merge refusal follows the readers' own disagreement: of the 3 literal and 3 real merge forms, the reader refuses "
      "exactly the blocks PyYAML's SafeLoader and BaseLoader read differently (3), and reads the 3 they read alike",
      all(part is refused for _b, part, refused in z4_rows) and sum(p is True for _b, p, _r in z4_rows) == 3
      and sum(p is False for _b, p, _r in z4_rows) == 3, "\n".join(repr(x) for x in z4_rows))


print("== source-page mode S1-S5: raw files are not searched, and the output says so ==")
import builtins


def traced(argv, entry):
    """(exit code, output, paths opened or listed) for one in-process run of the probe module's `entry`."""
    m = lk_load()
    seen = []
    real_open, real_scandir, real_listdir = builtins.open, os.scandir, os.listdir

    def t_open(file, *a, **k):
        seen.append(os.fspath(file) if not isinstance(file, int) else f"fd {file}")
        return real_open(file, *a, **k)

    def t_scandir(path="."):
        seen.append(os.fspath(path))
        return real_scandir(path)

    def t_listdir(path="."):
        seen.append(os.fspath(path))
        return real_listdir(path)
    buf, code = io.StringIO(), 0
    builtins.open, os.scandir, os.listdir = t_open, t_scandir, t_listdir
    try:
        with contextlib.redirect_stdout(buf):
            getattr(m, entry)(argv)
    except SystemExit as e:
        code = e.code
    finally:
        builtins.open, os.scandir, os.listdir = real_open, real_scandir, real_listdir
    return code, buf.getvalue(), seen


RAW_ROOT = os.path.join(RAWBAD, "raw")
under_raw = lambda paths: [p for p in paths if isinstance(p, str) and (os.path.abspath(p) == RAW_ROOT
                                                                       or os.path.abspath(p).startswith(RAW_ROOT + os.sep))]
try:
    code, text, seen = traced(["--vault-root", RAWBAD, "--title", "A Healthy Page Beside It"], "lookup_main")
    dcode, dtext, dseen = traced(["raw/x/thematic-break.md", "--vault-root", RAWBAD], "main")
    src_seen = [p for p in seen if isinstance(p, str) and os.path.abspath(p).startswith(os.path.join(RAWBAD, "wiki", "sources"))]
    raw_x = [os.path.join(RAWBAD, "raw", "x", f) for f in sorted(os.listdir(os.path.join(RAWBAD, "raw", "x")))]
    ok = (code in (0, None) and f"CANDIDATE {S}good.md (" in text and not under_raw(seen) and src_seen and len(raw_x) == 5
          and all(any(os.path.abspath(p) == f for p in under_raw(dseen)) for f in raw_x))
    detail = (f"lookup: exit {code}, {len(src_seen)} wiki/sources/ paths, raw paths {under_raw(seen)}; de-dup control: "
              f"{len(under_raw(dseen))} raw paths\n{text[-300:]}")
except Exception as e:
    ok, detail = False, f"error: {e!r}"
check("S1 the lookup opens and lists nothing under raw/, only wiki/sources/; control: the de-dup probe's run on the same "
      "vault, traced the same way, opens or lists raw/ and every file in raw/x/", ok, detail)
ok_runs = [o for o in LOOKUP_OUTPUTS if any(ln.startswith("index: ") for ln in o.splitlines())]
lacking = [o for o in ok_runs if not any(ln.startswith("index: ") and RAW_PHRASE in ln for ln in o.splitlines())]
nm_lines = [ln for o in LOOKUP_OUTPUTS for ln in o.splitlines() if ln.startswith("NO MATCH (")]
nm_lacking = [ln for ln in nm_lines if RAW_PHRASE not in ln]
held_wording = "index: 1 source pages read and parsed · raw join off (--no-raw) · pages a key of each kind reaches: arxiv 0"
check(f"S2 every lookup run of this suite that printed an index line ({len(ok_runs)}) says there that raw files are not "
      f"searched, and so does every NO MATCH line ({len(nm_lines)}); control: an index line in the raw-join build's wording "
      "lacks it", ok_runs and nm_lines and not lacking and not nm_lacking and RAW_PHRASE not in held_wording,
      "".join(lacking[:1]) + "\n".join(nm_lacking[:2]))
raw_opts = [o for a in (LK_MOD.lookup_parser()._actions if LK_MOD else []) for o in a.option_strings if "raw" in o]
r = lrun(LKV, "--list", LIST_ALL, "--no-raw")
check("S3 the lookup offers no raw option, and --no-raw beside a list is refused as a usage error with no verdict",
      LK_MOD is not None and raw_opts == [] and failed(r, "lookup usage"), f"raw options {raw_opts}\n" + out(r))
S4V = mkvault("lk-s4", {S + "good.md": doc('title: "Paper: A Healthy Page Beside It"'),
                        **{S + f"bad-{k}.md": doc('title: "Paper: A Quote That Never Closes', f'doi: "10.5555/s4.{k}"') for k in range(6)}})
r = lrun(S4V, "--title", "A Healthy Page Beside It")
named = [k for k in range(6) if f"{S}bad-{k}.md: the frontmatter does not parse as YAML" in r.stdout]
check("S4 six source pages that do not parse are each named, with their count (6 of 7), and no verdict is printed (the held "
      "build named the first five)", failed(r, "6 of 7 source pages cannot be read or parsed") and named == list(range(6)),
      f"named {named}\n" + out(r))
S5V = mkvault("lk-s5", {S + "good.md": doc('title: "Paper: A Healthy Page Beside It"'),
                        S + "cr-only.md": '---\rtitle: "Paper: A Page With CR Line Ends"\rdoi: "10.5555/s5.cr"\r---\r\rbody\r'})
r = lrun(S5V, "--doi", "10.5555/s5.cr")
S5C = mkvault("lk-s5-crlf", {S + "good.md": doc('title: "Paper: A Healthy Page Beside It"'),
                             S + "crlf.md": '---\r\ntitle: "Paper: A Page With CR LF Line Ends"\r\ndoi: "10.5555/s5.crlf"\r\n---\r\n\r\nbody\r\n'})
r2, vd2 = look(S5C, {"doi": "10.5555/s5.crlf"})
check("S5 a source page with CR-only line ends exits 2 naming it (no frontmatter block), never read as a page with no key; "
      "control: the same page with CR LF line ends gives its MATCH",
      failed(r, S + "cr-only.md: no frontmatter block") and kinds(vd2) == {S + "crlf.md": "MATCH"}, out(r) + out(r2))


print("== lookup L7: bounded and read-only ==")
try:
    cnt = lk_load()
    calls = {"index": 0}
    real_build = cnt.build_lookup_index

    def counted(*a, **k):
        calls["index"] += 1
        return real_build(*a, **k)
    cnt.build_lookup_index = counted
    code, text = inproc(cnt, ["--vault-root", LKV, "--list", LIST_ALL])
    ok = code in (0, None) and calls["index"] == 1 and len(blocks(text)) == len(CITES)
except Exception as e:
    ok, text = False, f"error: {e!r}"
check(f"L7a one index construction serves the whole batch ({len(CITES)} citations and the controls)", ok, f"index builds {calls.get('index') if 'calls' in dir() else '?'}\n{text[-400:]}")
ro_l = os.path.join(TMP, "readonly-lookup")
shutil.copytree(LKV, ro_l)
before_l = manifest(ro_l)
for root, dirs, files in os.walk(ro_l):
    for f in files:
        os.chmod(os.path.join(root, f), 0o444)
    os.chmod(root, 0o555)
runs_l = [lrun(ro_l, "--arxiv", "2205.14334"), lrun(ro_l, "--list", LIST_ALL), lrun(ro_l, "--list", os.path.join(LISTS, "late-bad-json.jsonl"))]
after_l = manifest(ro_l)
check("L7b lookups on a read-only copy behaved (a MATCH, a full list, a PROBE FAILED) and its checksum manifest is unchanged",
      "MATCH " in runs_l[0].stdout and len(blocks(runs_l[1].stdout)) == len(CITES) and runs_l[2].returncode == 2
      and before_l == after_l and len(before_l) > 20, f"{len(before_l)} rows before, {len(after_l)} after")
hits_b = [o for o in LOOKUP_OUTPUTS if BANNED.search(o)]
n_nomatch = sum("\nNO MATCH (" in o for o in LOOKUP_OUTPUTS)
n_failed = sum(o.startswith("PROBE FAILED: ") for o in LOOKUP_OUTPUTS)
check(f"L7c no lookup output in this suite ({len(LOOKUP_OUTPUTS)} runs, {n_nomatch} with NO MATCH, {n_failed} PROBE FAILED) says "
      "absent, missing, not in the vault or not held; control hits 1",
      n_nomatch >= 3 and n_failed >= 10 and not hits_b and len(BANNED.findall("the work is absent")) == 1, "".join(hits_b[:2]))

for root, dirs, files in os.walk(TMP):
    os.chmod(root, 0o755)
    for f in files:
        os.chmod(os.path.join(root, f), 0o644)
shutil.rmtree(TMP)
print(f"PASS {P}/{P + F}" if not F else f"FAIL {F}/{P + F}")
sys.exit(1 if F else 0)
