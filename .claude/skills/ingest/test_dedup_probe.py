#!/usr/bin/env python3
"""test_dedup_probe.py - the ingest de-dup probe on planted fixtures.

Run: python3 test_dedup_probe.py [path/to/dedup_probe.py]   (default: beside this file)
Legs replay the page-without-source_url case (a URL capture of arXiv 2307.03172 against a page compiled from a
local PDF with no source_url), each paper key alone, a similar-title negative control with its
positive control, the name / hash / URL keys the shell block had, the site-suffix legs (F9a-F9h: a
trailing site suffix keys like the bare title by its property, while family pages, short segments
sharing a word and long segments are not cut, and gather's capture_write.py loads the same key), the
premise failures, and a last leg proving the probe wrote nothing. Fixtures live under one mkdtemp,
removed at the end.
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

for root, dirs, files in os.walk(TMP):
    os.chmod(root, 0o755)
    for f in files:
        os.chmod(os.path.join(root, f), 0o644)
shutil.rmtree(TMP)
print(f"PASS {P}/{P + F}" if not F else f"FAIL {F}/{P + F}")
sys.exit(1 if F else 0)
