#!/usr/bin/env python3
"""test_preprint_versions.py - the fixture suite for preprint-versions.py, with no network.

  python3 -B test_preprint_versions.py [--script P] [--dedup-probe P] [--skill P] [--edit-spec P]

  --script       the script under test (default: preprint-versions.py beside this file)
  --dedup-probe  the ingest skill's dedup_probe.py (default: ../ingest/dedup_probe.py from this file)
  --skill        deep-lint's SKILL.md for T0 (default: SKILL.md beside this file)
  --edit-spec    an edit spec in the install set's format: T0 then checks that its old occurs once in
                 --skill and that the edited text names the script once, inside Step 5; without it, T0
                 checks --skill as installed

The suite works in one mktemp -d tree, removed at the end. The fixture vaults and saved replies are
copied in; the script under test is copied to <tmp>/skills/deep-lint/ and dedup_probe.py is linked,
never copied, at <tmp>/skills/ingest/, so the script loads it as it does when installed. No call
leaves the machine: every subprocess run carries --reply or a file: --api-url (run() refuses any
other), and the call-path and crash legs run the script in-process with sockets refused (the first
with its opener replaced). Each leg asserts the exit code and the exact lines printed (so a line
that must not print fails it), names the prefixes that must not appear, and checks every output for
"all clear", "OK" and "clean". The last leg is the read-only proof: a checksum manifest of the whole
tree and of the linked module before and after, with a control that changes one byte. Ends PASS n/n
or FAIL k/n (exit 0 or 1); a broken premise of the suite prints PROBE FAILED and exits 2.
"""
import argparse, contextlib, hashlib, importlib.util, io, json, os, re, shutil, socket, stat, subprocess, sys
import tempfile, urllib.error, urllib.request

sys.dont_write_bytecode = True   # the in-process leg must leave no cache file in the tree under test
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures", "preprint-versions")
NAME = "preprint-versions.py"
FORBIDDEN = re.compile(r"all clear|\bclean\b|\bOK\b", re.I)
MUTANT_ANCHOR = 'r"v(\\d+)(?!\\d)"'      # the captured-version parse in version_in
MUTANT_SWAP = 'r"v(\\d)(?!\\d)"'         # reads one digit only, so v12 no longer parses
BAD_MODULE = '''ARXIV_KEYS = ("source_url",)
def arxiv_ids(value, bare=False):
    return set()
def frontmatter(text):
    return {}
def self_test(fns=None):
    return ["planted failure: arxiv_ids gave set() for an arXiv URL"]
'''
P1 = "wiki/sources/fixture-2024-planted-preprint.md"
BEHIND_1 = f"BEHIND {P1} · 2401.00001 captured v1 (source_url) · latest v2 updated 2026-10-01"
LAST_T2 = "behind: 0 · likely behind: 0 · current: 1 · ids answered 1 of 1 · pages 1"


class Ctx:
    pass


def sub(ctx, text):
    for t in (ctx.real, ctx.tmp):
        text = text.replace(t, "<tmp>")
    return text


def hdr(vault, n, p, m, b, reply=None):
    return (f"preprint-versions: <tmp>/fixtures/vaults/{vault} · source pages {n} · with an arXiv id {p} · "
            f"distinct ids {m} · batches {b}" + (f" · saved reply <tmp>/fixtures/replies/{reply}" if reply else ""))


def show(ctx, args, code, lines):
    print("    $ " + " ".join(sub(ctx, str(x)) for x in args))
    for line in lines:
        print("    | " + line)
    print(f"    exit {code}")


def run(ctx, args, script=None):
    """(exit code, output lines with the tree shown as <tmp>) of one subprocess run of the script."""
    if "--reply" not in args and not any(str(x).startswith("file:") for x in args):
        return None, ["(refused by the suite: a run with neither --reply nor a file: --api-url could reach the network)"]
    script = script or ctx.script
    p = subprocess.run([sys.executable, "-B", script] + args, capture_output=True, text=True, timeout=120, cwd=ctx.tmp)
    lines = [sub(ctx, x) for x in p.stdout.splitlines()] + ["(stderr) " + sub(ctx, x) for x in p.stderr.splitlines()]
    show(ctx, [sub(ctx, script)] + args, p.returncode, lines)
    return p.returncode, lines


def verdict(code, lines, rc, want, absent=()):
    """Errors, if any: the exit code, the lines line by line (a str matches exactly, a pattern in full),
    the prefixes no line may start with, and the wording no output may hold."""
    errs = []
    if code != rc:
        errs.append(f"exit {code}, expected {rc}")
    for i in range(max(len(want), len(lines))):
        w = want[i] if i < len(want) else None
        got = lines[i] if i < len(lines) else None
        if w is None or got is None or not (w.fullmatch(got) if isinstance(w, re.Pattern) else w == got):
            errs.append(f"line {i + 1}: got {got!r}, expected {getattr(w, 'pattern', w)!r}")
            break
    for prefix in absent:
        hit = next((x for x in lines if x.startswith(prefix)), None)
        if hit:
            errs.append(f"a line starts {prefix!r}: {hit!r}")
    hit = next((x for x in lines if FORBIDDEN.search(x)), None)
    if hit:
        errs.append(f"forbidden wording in {hit!r}")
    return errs


def vault(ctx, name):
    return os.path.join(ctx.tmp, "fixtures", "vaults", name)


def reply(ctx, name):
    return os.path.join(ctx.tmp, "fixtures", "replies", name)


def check(ctx, v, r, rc, want, absent=(), script=None, extra=()):
    code, lines = run(ctx, ["--vault", vault(ctx, v)] + (["--reply", reply(ctx, r)] if r else []) + list(extra), script)
    return verdict(code, lines, rc, want, absent)


# ---------------------------------------------------------------- the legs

def t0(ctx):
    """The step edit: the spec's old occurs once in SKILL.md as a whole line, and the edited text names
    the script once, inside Step 5 (the freshness step); without a spec, SKILL.md as installed."""
    try:
        text = open(ctx.skill, encoding="utf-8").read()
    except OSError as e:
        return [f"{ctx.skill} cannot be read ({e.strerror or e})"]
    errs = []
    if ctx.edit_spec:
        spec = json.load(open(ctx.edit_spec, encoding="utf-8"))
        n = text.count(spec["old"])
        print(f"    the spec's old occurs {n} time(s) in {ctx.skill}")
        if n != 1:
            return [f"the spec's old occurs {n} times, expected 1"]
        if f"\n{spec['old']}\n" not in text or "\n" in spec["old"] or "\n" in spec["new"]:
            errs.append("old and new must each be one whole line")
        text = text.replace(spec["old"], spec["new"], 1)
    n = text.count(NAME)
    s5, s6 = text.find("\n### 5 "), text.find("\n### 6 ")
    at = text.find(NAME)
    print(f"    the {'edited' if ctx.edit_spec else 'installed'} text names {NAME} {n} time(s)"
          + (f", at line {text.count(chr(10), 0, at) + 1}" if at >= 0 else ""))
    if n != 1:
        errs.append(f"{NAME} named {n} times, expected 1")
    elif not (0 <= s5 < at < s6):
        errs.append(f"{NAME} is named outside Step 5")
    return errs


def t1(ctx):
    return check(ctx, "t1-behind", "latest-2401.00001v2.xml", 1,
                 [hdr("t1-behind", 1, 1, 1, 0, "latest-2401.00001v2.xml"), BEHIND_1,
                  "behind: 1 · likely behind: 0 · current: 0 · ids answered 1 of 1 · pages 1"],
                 absent=("LIKELY BEHIND", "INCOMPLETE"))


def t2(ctx):
    return check(ctx, "t2-current", "latest-2401.00001v2.xml", 0,
                 [hdr("t2-current", 1, 1, 1, 0, "latest-2401.00001v2.xml"), LAST_T2],
                 absent=("BEHIND", "LIKELY BEHIND", "INCOMPLETE"))


def t3(ctx):
    url = "file://" + os.path.join(ctx.tmp, "no-such-dir", "query")
    return check(ctx, "t2-current", None, 2,
                 [hdr("t2-current", 1, 1, 1, 1),
                  re.compile(r"INCOMPLETE: the arXiv API could not be reached \(URLError: .+\); 1 of 1 ids unanswered"
                             r" · behind so far 0 · likely behind so far 0")],
                 absent=("behind:", "BEHIND"), extra=["--api-url", url])


def t4(ctx):
    return check(ctx, "partial", "partial.xml", 2,
                 [hdr("partial", 2, 2, 2, 0, "partial.xml"), BEHIND_1,
                  "UNANSWERED 2401.00002 · wiki/sources/fixture-2024-second-preprint.md",
                  "INCOMPLETE: 1 of 2 ids unanswered · behind so far 1 · likely behind so far 0"],
                 absent=("behind:",))


def t5(ctx):
    raw = "raw/2-papers/fixture-2026-unversioned-"
    return check(ctx, "unversioned", "unversioned.xml", 1,
                 [hdr("unversioned", 5, 5, 5, 0, "unversioned.xml"),
                  "LIKELY BEHIND wiki/sources/fixture-2026-unversioned-converted.md · 2401.00003 unversioned, captured by "
                  f"2026-08-20 (converted_on of {raw}converted-arxiv-2401-00003-first.md) · latest v2 updated 2026-10-25",
                  "LIKELY BEHIND wiki/sources/fixture-2026-unversioned-created.md · 2401.00004 unversioned, captured by "
                  "2026-08-25 (created) · latest v2 updated 2026-11-07",
                  "LIKELY BEHIND wiki/sources/fixture-2026-unversioned-same-day.md · 2401.00011 unversioned, captured by "
                  f"2026-10-05 (converted_on of {raw}same-day-arxiv-2401-00011.md) · latest v2 updated 2026-10-05",
                  "behind: 0 · likely behind: 3 · current: 2 · ids answered 5 of 5 · pages 5"],
                 absent=("LIKELY BEHIND wiki/sources/fixture-2026-unversioned-later-capture.md",
                         "LIKELY BEHIND wiki/sources/fixture-2026-unversioned-single-version.md", "BEHIND", "INCOMPLETE"))


def t6(ctx):
    page = "wiki/sources/fixture-2026-abstract-two-versions.md"
    raw = "raw/2-papers/fixture-2026-abstract-two-versions-arxiv-2401-00005-abstract-pag.md"
    return (check(ctx, "raw-two-versions", "two-versions-latest-v2.xml", 0,
                  [hdr("raw-two-versions", 1, 1, 1, 0, "two-versions-latest-v2.xml"), LAST_T2],
                  absent=("BEHIND", "LIKELY BEHIND", "INCOMPLETE"))
            + check(ctx, "raw-two-versions", "two-versions-latest-v3.xml", 1,
                    [hdr("raw-two-versions", 1, 1, 1, 0, "two-versions-latest-v3.xml"),
                     f"BEHIND {page} · 2401.00005 captured v2 (raw {raw}) · latest v3 updated 2026-10-25",
                     "behind: 1 · likely behind: 0 · current: 0 · ids answered 1 of 1 · pages 1"],
                    absent=("LIKELY BEHIND", "INCOMPLETE")))


def t7(ctx):
    tail = "; 1 of 1 ids unanswered · behind so far 0 · likely behind so far 0"
    return (check(ctx, "t2-current", "malformed-truncated.xml", 2,
                  [hdr("t2-current", 1, 1, 1, 0, "malformed-truncated.xml"),
                   re.compile(r"INCOMPLETE: a reply could not be read as XML \(.+\)" + re.escape(tail))],
                  absent=("behind:", "BEHIND"))
            + check(ctx, "t2-current", "malformed-html.xml", 2,
                    [hdr("t2-current", 1, 1, 1, 0, "malformed-html.xml"),
                     "INCOMPLETE: a reply is not an Atom feed (its root is <html>)" + tail],
                    absent=("behind:", "BEHIND"))
            + check(ctx, "t2-current", "no-such-reply.xml", 2,
                    [hdr("t2-current", 1, 1, 1, 0, "no-such-reply.xml"),
                     "INCOMPLETE: the saved reply cannot be read (No such file or directory)" + tail],
                    absent=("behind:", "BEHIND")))


def t8(ctx):
    return (check(ctx, "no-arxiv", "latest-2401.00001v2.xml", 2,
                  [hdr("no-arxiv", 1, 0, 0, 0, "latest-2401.00001v2.xml"),
                   "INCOMPLETE: no source page with an arXiv id found among the 1 read · behind so far 0 · likely behind so far 0"],
                  absent=("behind:",))
            + check(ctx, "empty", "latest-2401.00001v2.xml", 2,
                    [hdr("empty", 0, 0, 0, 0, "latest-2401.00001v2.xml"),
                     "INCOMPLETE: no source page found under wiki/sources/ · behind so far 0 · likely behind so far 0"],
                    absent=("behind:",)))


def t9(ctx):
    return check(ctx, "flagged", "flagged.xml", 1,
                 [hdr("flagged", 2, 2, 2, 0, "flagged.xml"),
                  "BEHIND wiki/sources/fixture-2026-already-flagged.md · 2401.00008 captured v1 (source_url) · latest v2 "
                  "updated 2026-10-12 · already flagged 2026-11-19",
                  "BEHIND wiki/sources/fixture-2026-flagged-older-version.md · 2401.00009 captured v1 (source_url) · latest v3 "
                  "updated 2026-11-02",
                  "behind: 2 · likely behind: 0 · current: 0 · ids answered 2 of 2 · pages 2"],
                 absent=("INCOMPLETE",))


def t10(ctx):
    return check(ctx, "unreadable", "unreadable.xml", 2,
                 [hdr("unreadable", 2, 1, 1, 0, "unreadable.xml"),
                  "BEHIND wiki/sources/fixture-2026-readable-behind.md · 2401.00012 captured v1 (source_url) · latest v2 "
                  "updated 2026-09-15",
                  "UNREADABLE wiki/sources/fixture-2026-unclosed-frontmatter.md · its frontmatter block does not close "
                  "within the first 64 KiB",
                  "INCOMPLETE: 1 source page unreadable · behind so far 1 · likely behind so far 0"],
                 absent=("behind:",))


def t11(ctx):
    return check(ctx, "t1-behind", "latest-2401.00001v2.xml", 2,
                 ["PROBE FAILED: the de-dup key module is missing (<tmp>/tree-nomod/skills/ingest/dedup_probe.py); "
                  "the arXiv ids cannot be read without it"],
                 absent=("behind:", "BEHIND"), script=ctx.script_nomod)


def t12(ctx):
    return (check(ctx, "t1-behind", "latest-2401.00001v2.xml", 2,
                  ["PROBE FAILED: the de-dup key self-test failed: planted failure: arxiv_ids gave set() for an arXiv URL"],
                  absent=("behind:", "BEHIND"), script=ctx.script_badmod)
            + check(ctx, "t1-behind", "latest-2401.00001v2.xml", 2,
                    [re.compile(r"PROBE FAILED: the de-dup key module does not load \(<tmp>/tree-brokenmod/skills/ingest/"
                                r"dedup_probe\.py: SyntaxError: .+\)")],
                    absent=("behind:", "BEHIND"), script=ctx.script_brokenmod))


def t13(ctx):
    if not ctx.mutant:
        return [f"the mutation anchor {MUTANT_ANCHOR} does not occur exactly once in the script under test"]
    return check(ctx, "t1-behind", "latest-2401.00001v2.xml", 2,
                 ["INCOMPLETE: the built-in check failed (version_in('arXiv:2401.00001v12', '2401.00001') gave None, "
                  "expected 12) · behind so far 0 · likely behind so far 0"],
                 absent=("preprint-versions:", "behind:", "BEHIND"), script=ctx.mutant)


@contextlib.contextmanager
def no_network():
    def refuse(*_a, **_k):
        raise RuntimeError("network refused by the suite")
    saved = (socket.socket.connect, socket.create_connection, urllib.request.urlopen, urllib.request.OpenerDirector.open)
    socket.socket.connect = socket.create_connection = urllib.request.urlopen = urllib.request.OpenerDirector.open = refuse
    try:
        yield
    finally:
        (socket.socket.connect, socket.create_connection, urllib.request.urlopen, urllib.request.OpenerDirector.open) = saved


class FakeOpener:
    """Stands in for the script's opener: records each request and answers from the saved replies."""
    def __init__(self, ctx, fail_on=()):
        self.ctx, self.fail_on, self.requests = ctx, fail_on, []

    def open(self, req, timeout=None):
        self.requests.append((req.full_url, req.get_header("User-agent"), req.get_method(), timeout))
        n = len(self.requests)
        if n in self.fail_on:
            if self.fail_on[n] == "503":
                raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, None)
            raise urllib.error.URLError(self.fail_on[n])
        ids = re.search(r"id_list=([^&]*)", req.full_url).group(1)
        name = {"2401.00001": "batch-2401.00001.xml", "2401.00002": "batch-2401.00002.xml",
                "2401.00001,2401.00002": "batch-pair.xml"}[ids]
        return contextlib.nullcontext(io.BytesIO(open(reply(self.ctx, name), "rb").read()))


class FakeTime:
    def __init__(self):
        self.sleeps = []

    def sleep(self, s):
        self.sleeps.append(s)


def t14(ctx):
    """The call path, in-process: one GET per batch with the id list, the batch size and a User-Agent,
    3 s between batches, no retry, no redirect followed; an HTTP error or a failed later batch ends it."""
    try:
        spec = importlib.util.spec_from_file_location("preprint_versions_under_test", ctx.script)
        mod = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(mod)
    except BaseException as e:   # a script that exits or prints on import is no importable check
        return [f"the script under test does not import cleanly ({type(e).__name__}: {e})"]
    api = "https://export.arxiv.org/api/query"
    pv = vault(ctx, "partial")
    last = "behind: 1 · likely behind: 0 · current: 1 · ids answered 2 of 2 · pages 2"
    cases = [  # (label, extra args, failures by request number, requests expected, sleeps expected, rc, lines)
        ("two batches of one id", ["--batch", "1"], {}, [f"{api}?id_list=2401.00001&max_results=1",
         f"{api}?id_list=2401.00002&max_results=1"], [3], 1, [hdr("partial", 2, 2, 2, 2), BEHIND_1, last]),
        ("one batch of two ids", [], {}, [f"{api}?id_list=2401.00001,2401.00002&max_results=2"], [], 1,
         [hdr("partial", 2, 2, 2, 1), BEHIND_1, last]),
        ("HTTP 503 on batch 1, no retry", ["--batch", "1"], {1: "503"}, [f"{api}?id_list=2401.00001&max_results=1"], [], 2,
         [hdr("partial", 2, 2, 2, 2), "INCOMPLETE: the arXiv API answered HTTP 503 on batch 1 of 2; 2 of 2 ids "
          "unanswered · behind so far 0 · likely behind so far 0"]),
        ("unreachable on batch 2", ["--batch", "1"], {2: "planted outage"}, [f"{api}?id_list=2401.00001&max_results=1",
         f"{api}?id_list=2401.00002&max_results=1"], [3], 2,
         [hdr("partial", 2, 2, 2, 2), BEHIND_1, "INCOMPLETE: the arXiv API could not be reached (URLError: planted outage)"
          " on batch 2 of 2; 1 of 2 ids unanswered · behind so far 1 · likely behind so far 0"]),
    ]
    errs = []
    for label, extra, fail_on, urls, sleeps, rc, want in cases:
        opener, clock, buf = FakeOpener(ctx, fail_on), FakeTime(), io.StringIO()
        mod.OPENER, mod.time = opener, clock
        with no_network(), contextlib.redirect_stdout(buf):
            try:
                code = mod.main(["--vault", pv] + extra)
            except BaseException as e:   # SystemExit included: the leg must report, never stop the suite
                code = f"raised {type(e).__name__}: {e}"
        lines = [sub(ctx, x) for x in buf.getvalue().splitlines()]
        print(f"    in-process, {label}:")
        show(ctx, ["preprint-versions.py", "--vault", pv] + extra, code, lines)
        for u, ua, method, timeout in opener.requests:
            print(f"    request: GET={method == 'GET'} {u} · User-Agent {ua!r} · timeout {timeout}")
        print(f"    sleeps: {clock.sleeps}")
        e = verdict(code, lines, rc, want)
        if [r[0] for r in opener.requests] != urls:
            e.append(f"requests {[r[0] for r in opener.requests]}, expected {urls}")
        if any(m != "GET" or not ua or "preprint-versions" not in ua or t != 30 for _u, ua, m, t in opener.requests):
            e.append("a request was not a GET with a User-Agent naming the check and the 30 s timeout")
        if clock.sleeps != sleeps:
            e.append(f"sleeps {clock.sleeps}, expected {sleeps}")
        errs += [f"{label}: {x}" for x in e]
    # a redirect is never followed: the handler answers a 3xx with None, and the script's own opener carries it
    redirect = getattr(mod, "_NoRedirect", None)
    asked = urllib.request.Request("https://export.arxiv.org/api/query?id_list=2401.00001&max_results=1")
    if not (redirect and redirect().redirect_request(asked, None, 301, "Moved", {}, "https://elsewhere.example/") is None):
        errs.append("a redirect would be followed (no handler returning None for a 3xx)")
    else:
        fresh = importlib.util.module_from_spec(spec)   # mod.OPENER was replaced above: read a fresh copy's
        spec.loader.exec_module(fresh)
        if not any(isinstance(h, fresh._NoRedirect) for h in getattr(fresh.OPENER, "handlers", [])):
            errs.append("the script's opener does not carry the no-redirect handler")
    return errs


WRITES = [r"open\([^)]*,\s*['\"][^'\"]*[wax+]", r"\.write\(", r"\.write_(?:text|bytes)\(",
          r"\bos\.(?:remove|unlink|rename|replace|rmdir|removedirs|makedirs|mkdir|chmod|symlink|link|truncate)\(",
          r"\bshutil\.", r"\btempfile\.", r"\bsubprocess\b", r"\bos\.(?:system|popen)\("]
WRITER = 'open(p, "w").write("x")\nos.replace(a, b)\nshutil.copy(a, b)\nsubprocess.run(["touch", p])\n'


def t15(ctx):
    """A source grep for writes in the script, whose positive control is a synthetic writer."""
    hits = lambda text: [(p, m.group()) for p in WRITES for m in re.finditer(p, text)]
    control = hits(WRITER)
    print(f"    control: {len(control)} write patterns hit the synthetic writer (expected at least 4)")
    if len(control) < 4:
        return [f"the grep's control hit {len(control)} times, expected at least 4"]
    try:
        found = hits(open(ctx.script, encoding="utf-8").read())
    except OSError as e:
        return [f"the script cannot be read ({e.strerror or e})"]
    print(f"    the script: {len(found)} hits {found}")
    return [f"write patterns in the script: {found}"] if found else []


def manifest(top):
    """{relative path: (kind, mode, sha256 or link text)} for every directory, file and link under top."""
    out = {}
    for d, dirs, files in os.walk(top):
        dirs.sort()
        rel = os.path.relpath(d, top)
        out[rel + "/"] = ("dir", oct(os.lstat(d).st_mode))
        for f in sorted(files):
            p = os.path.join(d, f)
            st = os.lstat(p)
            if stat.S_ISLNK(st.st_mode):
                out[os.path.join(rel, f)] = ("link", oct(st.st_mode), os.readlink(p))
            else:
                out[os.path.join(rel, f)] = ("file", oct(st.st_mode), hashlib.sha256(open(p, "rb").read()).hexdigest())
    return out


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def diff(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def t16(ctx):
    """The read-only proof, last: one more run checked against its expectations, then the manifest of the
    whole tree and the linked module's bytes against those taken before the first leg; the control
    changes one byte beside a page the script read, with the same permissions, and must be caught."""
    errs = check(ctx, "t1-behind", "latest-2401.00001v2.xml", 1,
                 [hdr("t1-behind", 1, 1, 1, 0, "latest-2401.00001v2.xml"), BEHIND_1,
                  "behind: 1 · likely behind: 0 · current: 0 · ids answered 1 of 1 · pages 1"])
    after, module_after = manifest(ctx.tmp), sha(ctx.dedup)
    changed = diff(ctx.before, after)
    print(f"    manifest: {len(ctx.before)} entries before, {len(after)} after, {len(changed)} differ {changed}")
    print(f"    linked module sha256 before {ctx.module_before[:16]}… after {module_after[:16]}…")
    if changed:
        errs.append(f"the tree changed: {changed}")
    if module_after != ctx.module_before:
        errs.append("the linked dedup_probe.py changed")
    target = os.path.join("fixtures", "vaults", "t1-behind", "wiki", "sources", "fixture-2024-planted-preprint.md")
    path = os.path.join(ctx.tmp, target)
    data = bytearray(open(path, "rb").read())
    data[-2] ^= 1
    with open(path, "wb") as fh:
        fh.write(bytes(data))
    caught = diff(after, manifest(ctx.tmp))
    print(f"    control: one byte changed in {target}; the manifest names {caught}")
    if caught != [target]:
        errs.append(f"the control's change was not caught as exactly {target}: {caught}")
    return errs


def t17(ctx):
    """An unversioned page dates by its oldest capture: a version posted between two captures warns.
    A raw that never names the id is passed over while one does (the trap); with none, every raw counts."""
    return check(ctx, "capture-dates", "fold.xml", 1,
                 [hdr("capture-dates", 3, 3, 3, 0, "fold.xml"),
                  "LIKELY BEHIND wiki/sources/fixture-2026-raws-name-no-id.md · 2401.00015 unversioned, captured by "
                  "2026-06-01 (converted_on of raw/2-papers/fixture-2026-raws-name-no-id-mirror-first.md) · latest v2 "
                  "updated 2026-09-01",
                  "LIKELY BEHIND wiki/sources/fixture-2026-three-captures.md · 2401.00013 unversioned, captured by "
                  "2026-06-22 (converted_on of raw/2-papers/fixture-2026-three-captures-arxiv-2401-00013-first.md) · "
                  "latest v2 updated 2026-09-01",
                  "behind: 0 · likely behind: 2 · current: 1 · ids answered 3 of 3 · pages 3"],
                 absent=("LIKELY BEHIND wiki/sources/fixture-2026-unrelated-older-raw.md", "BEHIND", "INCOMPLETE"))


def t18(ctx):
    """A page dated only by created:, later than the latest version, is unadjudicated, never current."""
    return check(ctx, "created-only", "fold.xml", 2,
                 [hdr("created-only", 1, 1, 1, 0, "fold.xml"),
                  "UNADJUDICATED wiki/sources/fixture-2026-created-after-latest.md · 2401.00016 unversioned, dated only "
                  "by created 2026-11-10, after the latest v2 updated 2026-10-01",
                  "INCOMPLETE: 1 unversioned page unadjudicated (dated only by created:) · behind so far 0 · "
                  "likely behind so far 0"],
                 absent=("behind:", "BEHIND", "LIKELY BEHIND"))


def t19(ctx):
    """The already-flagged marker takes the date of the list item that names the version, not of an
    older, unrelated flag listed before it."""
    return check(ctx, "flag-list", "fold.xml", 1,
                 [hdr("flag-list", 1, 1, 1, 0, "fold.xml"),
                  "BEHIND wiki/sources/fixture-2026-flag-list.md · 2401.00017 captured v1 (source_url) · latest v2 "
                  "updated 2026-10-12 · already flagged 2026-11-19",
                  "behind: 1 · likely behind: 0 · current: 0 · ids answered 1 of 1 · pages 1"],
                 absent=("INCOMPLETE",))


def load_script(ctx, name):
    """(the script under test imported as a fresh module, None), or (None, why)."""
    try:
        spec = importlib.util.spec_from_file_location(name, ctx.script)
        mod = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(mod)
        return mod, None
    except BaseException as e:   # a script that exits or prints on import is no importable check
        return None, f"the script under test does not import cleanly ({type(e).__name__}: {e})"


FLAG_FORM = "`v<L> of <id>`"


def t20(ctx):
    """The flag wording the step pins: the step's line names the form v<L> of <id>, and a flag written in
    that form is one the script marks as already flagged (with or without an edit spec, as T0 reads it)."""
    try:
        text = open(ctx.skill, encoding="utf-8").read()
        if ctx.edit_spec:
            spec = json.load(open(ctx.edit_spec, encoding="utf-8"))
            text = text.replace(spec["old"], spec["new"], 1)
    except (OSError, ValueError, KeyError) as e:
        return [f"the step text cannot be read ({type(e).__name__}: {e})"]
    line = next((x for x in text.splitlines() if NAME in x), "")
    print(f"    the line naming {NAME} pins the flag form {FLAG_FORM}: {FLAG_FORM in line}")
    if FLAG_FORM not in line:
        return [f"the step line naming {NAME} pins no flag wording {FLAG_FORM}"]
    mod, why = load_script(ctx, "preprint_versions_flag_form")
    if why:
        return [why]
    named = FLAG_FORM.strip("`").replace("<L>", "2").replace("<id>", "2401.00008")
    block = f'---\nflagged: "2026-11-19 deep-lint (freshness): arXiv lists {named}, updated 2026-10-12."\n---\n'
    got = mod.flag_date(block, "2401.00008", 2)
    print(f"    a flag naming {named!r} gives {got!r}")
    return [] if got == " · already flagged 2026-11-19" else [f"a flag in the pinned form is not marked: {got!r}"]


def t21(ctx):
    return check(ctx, "no-sources", "fold.xml", 2,
                 [hdr("no-sources", 0, 0, 0, 0, "fold.xml"),
                  "INCOMPLETE: wiki/sources/ cannot be listed (No such file or directory) · behind so far 0 · "
                  "likely behind so far 0"],
                 absent=("behind:",))


def t22(ctx):
    page = "wiki/sources/fixture-2026-raw-missing.md"
    return check(ctx, "raw-missing", "fold.xml", 2,
                 [hdr("raw-missing", 1, 1, 1, 0, "fold.xml"),
                  f"LIKELY BEHIND {page} · 2401.00018 unversioned, captured by 2026-08-01 (created) · latest v2 "
                  "updated 2026-10-01",
                  f"UNREADABLE {page} · its raw raw/../../outside-the-vault.md lies outside the vault",
                  f"UNREADABLE {page} · its raw raw/2-papers/fixture-2026-raw-missing-absent-arxiv-2401-00018.md "
                  "cannot be read (No such file or directory)",
                  "INCOMPLETE: 1 source page unreadable · behind so far 0 · likely behind so far 1"],
                 absent=("behind:",))


def t23(ctx):
    return check(ctx, "undated", "fold.xml", 2,
                 [hdr("undated", 1, 1, 1, 0, "fold.xml"),
                  "UNREADABLE wiki/sources/fixture-2026-undated.md · 2401.00019 is unversioned and no capture date was "
                  "found (no converted_on: in its raws, no created:)",
                  "INCOMPLETE: 1 source page unreadable · behind so far 0 · likely behind so far 0"],
                 absent=("behind:", "BEHIND", "LIKELY BEHIND"))


def t24(ctx):
    """A crash inside the run, in-process: an error after a warning was counted ends INCOMPLETE (exit 2),
    never exit 1, which reads as a warning list."""
    mod, why = load_script(ctx, "preprint_versions_crash")
    if why:
        return [why]

    def crash(*_a):
        raise RuntimeError("planted crash")
    mod.flag_date = crash   # called just after the BEHIND page is counted
    args = ["--vault", vault(ctx, "t1-behind"), "--reply", reply(ctx, "latest-2401.00001v2.xml")]
    buf = io.StringIO()
    with no_network(), contextlib.redirect_stdout(buf):
        try:
            code = mod.main(args)
        except BaseException as e:   # SystemExit included: the leg must report, never stop the suite
            code = f"raised {type(e).__name__}: {e}"
    lines = [sub(ctx, x) for x in buf.getvalue().splitlines()]
    print("    in-process, flag_date replaced by a planted crash:")
    show(ctx, [NAME] + args, code, lines)
    return verdict(code, lines, 2,
                   [hdr("t1-behind", 1, 1, 1, 0, "latest-2401.00001v2.xml"),
                    "INCOMPLETE: the check stopped on an error (RuntimeError: planted crash) · behind so far 1 · "
                    "likely behind so far 0"],
                   absent=("behind:", "BEHIND"))


LEGS = [("T0 the step edit", t0), ("T1 must warn", t1), ("T2 must not warn", t2), ("T3 the API unreachable", t3),
        ("T4 a partial reply", t4), ("T5 unversioned captures", t5), ("T6 a raw naming two versions", t6),
        ("T7 a malformed or unreadable reply", t7), ("T8 no arXiv page", t8), ("T9 already flagged", t9),
        ("T10 an unreadable page", t10), ("T11 the de-dup module missing", t11),
        ("T12 the de-dup module failing", t12), ("T13 the built-in check failing", t13),
        ("T14 the call path", t14), ("T15 no write in the source", t15),
        ("T17 a version posted between captures", t17), ("T18 dated only by created:", t18),
        ("T19 a flag list, an older flag first", t19), ("T20 the flag wording the step pins", t20),
        ("T21 wiki/sources/ missing", t21), ("T22 a raw missing or outside the vault", t22),
        ("T23 an undated unversioned page", t23), ("T24 a crash inside the run", t24),
        ("T16 read only", t16)]   # T16 stays last: it proves that every leg before it left the tree as it was


def setup(ctx, script, dedup):
    shutil.copytree(FIX, os.path.join(ctx.tmp, "fixtures"), symlinks=True)
    for d in ("wiki/sources", "raw"):
        os.makedirs(os.path.join(vault(ctx, "empty"), d))
    os.makedirs(os.path.join(vault(ctx, "no-sources"), "raw"))   # a vault with no wiki/sources/ (T21)
    trees = {}
    for tree in ("skills", "tree-nomod/skills", "tree-badmod/skills", "tree-brokenmod/skills"):
        os.makedirs(os.path.join(ctx.tmp, tree, "deep-lint"))
        if tree != "tree-nomod/skills":
            os.makedirs(os.path.join(ctx.tmp, tree, "ingest"))
        trees[tree] = os.path.join(ctx.tmp, tree, "deep-lint", NAME)
        if os.path.isfile(script):
            shutil.copyfile(script, trees[tree])
    ctx.script, ctx.script_nomod = trees["skills"], trees["tree-nomod/skills"]
    ctx.script_badmod, ctx.script_brokenmod = trees["tree-badmod/skills"], trees["tree-brokenmod/skills"]
    os.symlink(dedup, os.path.join(ctx.tmp, "skills", "ingest", "dedup_probe.py"))
    with open(os.path.join(ctx.tmp, "tree-badmod", "skills", "ingest", "dedup_probe.py"), "w", encoding="utf-8") as fh:
        fh.write(BAD_MODULE)
    with open(os.path.join(ctx.tmp, "tree-brokenmod", "skills", "ingest", "dedup_probe.py"), "w", encoding="utf-8") as fh:
        fh.write("def broken(:\n")
    ctx.mutant = None
    if os.path.isfile(script):
        text = open(script, encoding="utf-8").read()
        if text.count(MUTANT_ANCHOR) == 1:
            ctx.mutant = os.path.join(ctx.tmp, "skills", "deep-lint", "preprint-versions-mutant.py")
            with open(ctx.mutant, "w", encoding="utf-8") as fh:
                fh.write(text.replace(MUTANT_ANCHOR, MUTANT_SWAP))


def main():
    ap = argparse.ArgumentParser(description="The fixture suite for preprint-versions.py, with no network.")
    ap.add_argument("--script", default=os.path.join(HERE, NAME))
    ap.add_argument("--dedup-probe", default=os.path.join(HERE, "..", "ingest", "dedup_probe.py"))
    ap.add_argument("--skill", default=os.path.join(HERE, "SKILL.md"))
    ap.add_argument("--edit-spec")
    a = ap.parse_args()
    dedup = os.path.realpath(a.dedup_probe)
    if not os.path.isfile(dedup):
        print(f"PROBE FAILED: dedup_probe.py not found at {a.dedup_probe}; the script under test cannot load its id reader")
        return 2
    missing = [d for d in ("vaults", "replies") if not os.path.isdir(os.path.join(FIX, d))]
    if missing:
        print(f"PROBE FAILED: the fixtures lack {', '.join(missing)} under {FIX}")
        return 2
    ctx = Ctx()
    ctx.tmp = tempfile.mkdtemp(prefix="preprint-versions-test-")
    ctx.real, ctx.dedup = os.path.realpath(ctx.tmp), dedup
    ctx.skill, ctx.edit_spec = a.skill, a.edit_spec
    print(f"script under test: {os.path.abspath(a.script)}" + ("" if os.path.isfile(a.script) else " (absent)"))
    print(f"dedup_probe.py: {dedup} (sha256 {sha(dedup)[:16]}…), linked into the tree")
    try:
        setup(ctx, a.script, dedup)
        ctx.before, ctx.module_before = manifest(ctx.tmp), sha(dedup)
        fails = 0
        for name, fn in LEGS:
            print(f"-- {name}")
            try:
                errs = fn(ctx)
            except (Exception, SystemExit) as e:   # SystemExit too: a leg must never end the suite with exit 0
                errs = [f"the leg raised {type(e).__name__}: {e}"]
            if errs:
                fails += 1
                print(f"FAIL  {name}: " + sub(ctx, "; ".join(errs)))
            else:
                print(f"PASS  {name}")
        print(f"PASS {len(LEGS)}/{len(LEGS)}" if not fails else f"FAIL {fails}/{len(LEGS)}")
        return 1 if fails else 0
    finally:
        shutil.rmtree(ctx.tmp)


if __name__ == "__main__":
    sys.exit(main())
