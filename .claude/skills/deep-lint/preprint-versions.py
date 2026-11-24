#!/usr/bin/env python3
"""preprint-versions.py - lists, warning only, each wiki source page whose captured arXiv version is
behind arXiv's latest. Deep-lint's freshness step runs it; it writes nothing (no file, no flag).

Usage:
  python3 -B preprint-versions.py --vault <root> [--reply FILE] [--api-url URL] [--timeout S] [--batch N]

Reads the frontmatter of every wiki/sources/*.md (the first 64 KiB, up to the closing ---) and the
arXiv ids in its source_url / converted_from / url / doi / arxiv / arxiv_id fields, through the ingest
skill's dedup_probe.py (loaded from ../ingest/, never copied). The captured version is the v<N> in
source_url; else a v<N> in another of those fields for the same id; else the highest <id>v<N> in the
first 8 KiB of each raw its sources: list names; else the page is unversioned, its capture dated by
the oldest converted_on: of the raws whose head names the id (of all its raws when none does), else
by the page's created:. A page dated by created: alone is UNADJUDICATED where the latest version
predates it: created: bounds the capture only from above, so it never shows a page current.
Asks the arXiv API for each id's latest version: one GET per batch of ids, 3 s apart, no retry, no
redirect followed. --reply reads a saved Atom reply instead and makes no call.

Prints a header line, then any of
  BEHIND <page> · <id> captured v<K> (<where>) · latest v<L> updated <date>[ · already flagged <date>]
  LIKELY BEHIND <page> · <id> unversioned, captured by <date> (<field>) · latest v<L> updated <date>[ ...]
  UNREADABLE <page> · <why>
  UNADJUDICATED <page> · <id> unversioned, dated only by created <date>, after the latest v<L> updated <date>
  UNANSWERED <id> · <pages>
and one last line, either
  INCOMPLETE: <why> · behind so far <k> · likely behind so far <j>                         (exit 2)
or
  behind: <k> · likely behind: <j> · current: <c> · ids answered <m> of <m> · pages <p>
                                                   (exit 1 when k + j > 0, exit 0 when both are 0)
`PROBE FAILED: <what>` (exit 2) when dedup_probe.py is missing, does not load or fails its self-test.
The exit-0 line prints only when the built-in check passed, every page was read, at least one page
carries an arXiv id, every id was answered and no page is unadjudicated. "already flagged" marks a
page whose flagged: line already names v<L> of <id>, so a deep-lint run adds no second flag; its date
is the one in the flag (or list item) that names it. Counts are of page-id pairs: a
page naming two ids is judged once for each. There is no --help: exit 0 means the clean line only.
"""
import argparse, importlib.util, os, re, sys, time
import urllib.error, urllib.request
import xml.etree.ElementTree as ET

API_URL = "https://export.arxiv.org/api/query"
USER_AGENT = "llm-wiki-deep-lint-preprint-versions/1 (a personal research vault's version check)"
SPACING_S = 3            # the arXiv API manual asks callers to "incorporate a 3 second delay" between calls
BATCH = 200              # ids per call: set by judgement, unmeasured
TIMEOUT_S = 30           # per call: set by judgement, unmeasured
PAGE_CAP = 64 * 1024     # frontmatter window: the de-dup probe's FRONT_CAP
RAW_HEAD = 8 * 1024      # raw bytes searched for <id>v<N>: set by judgement (an abstract page names its versions near its top)
REPLY_CAP = 32 << 20     # bytes read from one reply: set by judgement, unmeasured
ATOM = "{http://www.w3.org/2005/Atom}"
ENTRY_ID = re.compile(r"/abs/(\d{4}\.\d{4,5}|[a-z][a-z-]*(?:\.[a-z]{2})?/\d{7})v(\d+)$", re.I)
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
OPEN = re.compile(r"---[ \t]*\r?\n")
CLOSE = re.compile(r"^---[ \t]*\r?$", re.M)
PLANTED = ("https://arxiv.org/html/2401.00001v2", "arXiv:2401.00001v12", "https://arxiv.org/abs/2401.00001")


dp = None   # the loaded dedup_probe module, set by main()


class ProbeFailed(Exception):
    pass


def version_in(value, aid):
    """The highest v<N> written straight after the arXiv id in a string, or None."""
    pat = r"(?<![0-9A-Za-z-])" + re.escape(aid) + r"v(\d+)(?!\d)"
    found = [int(n) for n in re.findall(pat, value or "", re.I)]
    return max(found) if found else None


def latest_of(entry_id):
    """(id, version) from an Atom entry's <id> .../abs/<id>v<N>, or None (the API's error entry)."""
    m = ENTRY_ID.search((entry_id or "").strip())
    return (m.group(1).lower(), int(m.group(2))) if m else None


SELF_TEST = [
    (version_in, (PLANTED[0], "2401.00001"), 2),
    (version_in, (PLANTED[1], "2401.00001"), 12),
    (version_in, (PLANTED[2], "2401.00001"), None),
    (latest_of, ("http://arxiv.org/abs/2401.00001v2",), ("2401.00001", 2)),
    (latest_of, ("http://arxiv.org/abs/hep-th/9901001v3",), ("hep-th/9901001", 3)),
    (latest_of, ("http://arxiv.org/api/errors#incorrect_id_format_for_2401.0000x",), None),
]


def self_check(dp):
    bad = [f"{f.__name__}{a!r} gave {f(*a)!r}, expected {want!r}" for f, a, want in SELF_TEST if f(*a) != want]
    return bad + [f"arxiv_ids({s!r}) gave {dp.arxiv_ids(s)!r}" for s in PLANTED if dp.arxiv_ids(s) != {"2401.00001"}]


def load_dedup_probe():
    """The ingest skill's dedup_probe.py, loaded as capture_write.py's _dedup_keys loads it."""
    path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ingest", "dedup_probe.py"))
    if not os.path.isfile(path):
        raise ProbeFailed(f"the de-dup key module is missing ({path}); the arXiv ids cannot be read without it")
    spec = importlib.util.spec_from_file_location("dedup_probe", path)
    mod = importlib.util.module_from_spec(spec)
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True   # no cache file beside the ingest skill
    try:
        spec.loader.exec_module(mod)
        missing = [n for n in ("ARXIV_KEYS", "arxiv_ids", "frontmatter", "self_test") if not hasattr(mod, n)]
        bad = [f"it lacks {', '.join(missing)}"] if missing else mod.self_test()
    except Exception as e:
        raise ProbeFailed(f"the de-dup key module does not load ({path}: {type(e).__name__}: {e})")
    finally:
        sys.dont_write_bytecode = keep
    if bad:
        raise ProbeFailed("the de-dup key self-test failed: " + "; ".join(bad))
    return mod


def read_block(path):
    """(the text up to the frontmatter's closing ---, None), or (None, why)."""
    try:
        with open(path, "rb") as fh:
            text = fh.read(PAGE_CAP).decode("utf-8", errors="replace").removeprefix("﻿")
    except OSError as e:
        return None, f"cannot be read ({e.strerror or e})"
    m = OPEN.match(text)
    if not m:
        return None, "no frontmatter block (the page does not open with a line ---)"
    end = CLOSE.search(text, m.end())
    if not end:
        return None, f"its frontmatter block does not close within the first {PAGE_CAP // 1024} KiB"
    return text[:end.end()], None


def read_raw(vault, rel):
    path = os.path.realpath(os.path.join(vault, rel))
    if not path.startswith(os.path.realpath(vault) + os.sep):
        return None, "lies outside the vault"
    try:
        with open(path, "rb") as fh:
            return fh.read(RAW_HEAD).decode("utf-8", errors="replace"), None
    except OSError as e:
        return None, f"cannot be read ({e.strerror or e})"


def list_field(block, key):
    """The items of a frontmatter list: a flow list [a, b], a block of '- item' lines, or one value."""
    lines = block.splitlines()
    for i, line in enumerate(lines):
        m = re.match(re.escape(key) + r":\s*(.*)$", line, re.I)
        if not m:
            continue
        val = re.sub(r"\s+#.*$", "", m.group(1)).strip()
        if val.startswith("["):
            items = val.strip("[]").split(",")   # shortcut: an item holding a comma splits; use a YAML reader if a raw name ever holds one
        elif val:
            items = [val]
        else:
            items = []
            for nxt in lines[i + 1:]:
                im = re.match(r"\s*-\s+(.*)$", nxt)
                if not im:
                    break
                items.append(re.sub(r"\s+#.*$", "", im.group(1)))
        return [x.strip().strip("\"'") for x in items if x.strip()]
    return []


def flag_date(block, aid, latest):
    """' · already flagged <date>' when a flagged: entry already names v<latest> of <id>, else ''. The date
    is the first in the list item that names it, never one from another flag listed before it."""
    lines = block.splitlines()
    pat = re.compile(r"\bv%d of %s(?!\d)" % (latest, re.escape(aid)), re.I)
    for i, line in enumerate(lines):
        if not re.match(r"flagged:", line, re.I):
            continue
        items = [line]
        for nxt in lines[i + 1:]:
            if not nxt[:1].isspace():
                break
            if re.match(r"\s*-\s", nxt):
                items.append(nxt)
            else:
                items[-1] += " " + nxt
        for entry in items:
            if pat.search(entry):
                d = DATE.search(entry)
                return " · already flagged " + (d.group() if d else "(undated)")
    return ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None   # a 3xx comes back as an HTTPError: the ids go to the named host or nowhere


OPENER = urllib.request.build_opener(_NoRedirect)


def fetch(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with OPENER.open(req, timeout=timeout) as resp:
        return resp.read(REPLY_CAP + 1)


def read_reply(body, latest):
    """Adds {id: (version, updated date)} from one Atom reply; returns why it is unreadable, or None."""
    if len(body) > REPLY_CAP:
        return f"a reply exceeds {REPLY_CAP >> 20} MiB"
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        return f"a reply could not be read as XML ({e})"
    if root.tag != ATOM + "feed":
        return f"a reply is not an Atom feed (its root is <{root.tag}>)"
    for entry in root.findall(ATOM + "entry"):
        got = latest_of(entry.findtext(ATOM + "id"))
        upd = DATE.match((entry.findtext(ATOM + "updated") or "").strip())
        if got and upd and (got[0] not in latest or got[1] > latest[got[0]][0]):
            latest[got[0]] = (got[1], upd.group())
    return None


def one_line(e):
    return " ".join(f"{type(e).__name__}: {getattr(e, 'reason', e)}".split())


def run(a, counts):
    vault = os.path.abspath(a.vault)
    reasons, unreadable, pairs = [], [], []   # pairs: (page, id, capture, flagged-entry block)
    src = os.path.join(vault, "wiki", "sources")
    try:
        names = sorted(n for n in os.listdir(src) if n.endswith(".md") and not n.startswith("."))
    except OSError as e:
        names = []
        reasons.append(f"wiki/sources/ cannot be listed ({e.strerror or e})")
    for name in names:
        rel = f"wiki/sources/{name}"
        block, why = read_block(os.path.join(src, name))
        if why:
            unreadable.append((rel, why))
            continue
        fm = dp.frontmatter(block)
        fields = {k: fm[k] for k in dp.ARXIV_KEYS if fm.get(k)}
        ids = set()
        for k, v in fields.items():
            ids |= dp.arxiv_ids(v, bare=k in ("arxiv", "arxiv_id"))
        heads = None
        for aid in sorted(ids):
            cap = next((("v", n, k) for k in ["source_url"] + [k for k in dp.ARXIV_KEYS if k != "source_url"]
                        for n in [version_in(fields.get(k), aid)] if n is not None), None)
            if cap is None:
                if heads is None:
                    heads = []
                    for r in (x for x in list_field(block, "sources") if x.startswith("raw/")):
                        head, why = read_raw(vault, r)
                        if why:
                            unreadable.append((rel, f"its raw {r} {why}"))
                        else:
                            heads.append((r, head))
                found = [(n, r) for r, head in heads for n in [version_in(head, aid)] if n is not None]
                if found:
                    n, r = max(found)
                    cap = ("v", n, f"raw {r}")
                else:   # the oldest capture of this paper: a later date could pass a behind page as current
                    pool = [(r, head) for r, head in heads if aid in dp.arxiv_ids(head)] or heads
                    dates = [(d.group(), f"converted_on of {r}") for r, head in pool
                             for d in [DATE.match(dp.frontmatter(head).get("converted_on", ""))] if d]
                    created = DATE.match(fm.get("created", ""))
                    cap = ("u",) + (min(dates) if dates else (created.group(), "created") if created else (None, None))
            pairs.append((rel, aid, cap, block))
    pages = sorted({p for p, *_ in pairs})
    ids = sorted({aid for _p, aid, *_ in pairs})
    batches = 0 if a.reply else -(-len(ids) // a.batch)
    print(f"preprint-versions: {vault} · source pages {len(names)} · with an arXiv id {len(pages)} · "
          f"distinct ids {len(ids)} · batches {batches}" + (f" · saved reply {a.reply}" if a.reply else ""), flush=True)
    if not names and not reasons:
        reasons.append("no source page found under wiki/sources/")
    elif names and not pages:
        reasons.append(f"no source page with an arXiv id found among the {len(names) - len({p for p, _w in unreadable})} read")

    latest, asked = {}, set()
    if ids and a.reply:
        try:
            with open(a.reply, "rb") as fh:
                why = read_reply(fh.read(REPLY_CAP + 1), latest)
        except OSError as e:
            why = f"the saved reply cannot be read ({e.strerror or e})"
        if why:
            reasons.append(why)
        else:
            asked.update(ids)
    elif ids:
        for i in range(0, len(ids), a.batch):
            batch = ids[i:i + a.batch]
            if i:
                time.sleep(SPACING_S)
            try:
                body = fetch(f"{a.api_url}?id_list={','.join(batch)}&max_results={len(batch)}", a.timeout)
            except urllib.error.HTTPError as e:
                why = f"the arXiv API answered HTTP {e.code}"
            except Exception as e:   # URLError, a timeout, a dropped connection, an unopenable URL
                why = f"the arXiv API could not be reached ({one_line(e)})"
            else:
                why = read_reply(body, latest)
            if why:   # no retry, and no later batch: the run is incomplete either way
                reasons.append(why + (f" on batch {i // a.batch + 1} of {batches}" if batches > 1 else ""))
                break
            asked.update(batch)

    out, unanswered, unjudged = [], {}, []
    for rel, aid, cap, block in pairs:
        if aid not in latest:
            unanswered.setdefault(aid, []).append(rel)
            continue
        n_latest, upd = latest[aid]
        if cap[0] == "v":
            if cap[1] < n_latest:
                counts["k"] += 1
                out.append(f"BEHIND {rel} · {aid} captured v{cap[1]} ({cap[2]}) · latest v{n_latest} updated {upd}"
                           + flag_date(block, aid, n_latest))
            else:
                counts["c"] += 1
        elif n_latest == 1:
            counts["c"] += 1
        elif cap[1] is None:
            unreadable.append((rel, f"{aid} is unversioned and no capture date was found (no converted_on: in its raws, no created:)"))
        # the API shows a new version only from the midnight after it was processed, so a capture dated
        # the day of <updated> can hold the earlier one: the same day counts as likely behind
        elif upd >= cap[1]:
            counts["j"] += 1
            out.append(f"LIKELY BEHIND {rel} · {aid} unversioned, captured by {cap[1]} ({cap[2]}) · latest v{n_latest} "
                       f"updated {upd}" + flag_date(block, aid, n_latest))
        elif cap[2] == "created":   # the capture is on or before created:, so it may predate the latest version
            unjudged.append((rel, f"UNADJUDICATED {rel} · {aid} unversioned, dated only by created {cap[1]}, "
                                  f"after the latest v{n_latest} updated {upd}"))
        else:
            counts["c"] += 1
    for line in out:   # in page order, as the pages were read
        print(line)
    for rel, why in sorted(set(unreadable)):
        print(f"UNREADABLE {rel} · {why}")
    for _rel, line in unjudged:
        print(line)
    for aid in sorted(x for x in unanswered if x in asked):
        print(f"UNANSWERED {aid} · {', '.join(sorted(set(unanswered[aid])))}")
    if unreadable:
        n = len({p for p, _w in unreadable})
        reasons.append(f"{n} source page{'s' if n != 1 else ''} unreadable")
    if unjudged:
        n = len({p for p, _l in unjudged})
        reasons.append(f"{n} unversioned page{'s' if n != 1 else ''} unadjudicated (dated only by created:)")
    if unanswered:
        reasons.append(f"{len(unanswered)} of {len(ids)} ids unanswered")
    if reasons:
        print(f"INCOMPLETE: {'; '.join(reasons)} · behind so far {counts['k']} · likely behind so far {counts['j']}")
        return 2
    print(f"behind: {counts['k']} · likely behind: {counts['j']} · current: {counts['c']} · "
          f"ids answered {len(ids)} of {len(ids)} · pages {len(pages)}")
    return 1 if counts["k"] + counts["j"] else 0


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(f"INCOMPLETE: {message} · behind so far 0 · likely behind so far 0")
        sys.exit(2)


def main(argv=None):
    global dp
    # no --help, whose exit 0 would print no clean line: the docstring above is the usage
    ap = _Parser(add_help=False)
    ap.add_argument("--vault", required=True)
    ap.add_argument("--reply", help="a saved Atom reply, read in place of the call")
    ap.add_argument("--api-url", default=API_URL)
    ap.add_argument("--timeout", type=float, default=TIMEOUT_S)
    ap.add_argument("--batch", type=int, default=BATCH)
    a = ap.parse_args(argv)
    if a.batch < 1 or a.timeout <= 0:
        ap.error("--batch and --timeout must be positive")
    try:
        dp = load_dedup_probe()
    except ProbeFailed as e:
        print(f"PROBE FAILED: {e}")
        return 2
    bad = self_check(dp)
    if bad:
        print(f"INCOMPLETE: the built-in check failed ({'; '.join(bad)}) · behind so far 0 · likely behind so far 0")
        return 2
    counts = {"k": 0, "j": 0, "c": 0}
    try:
        return run(a, counts)
    except Exception as e:   # a crash must never exit 1, which reads as a warning list
        print(f"INCOMPLETE: the check stopped on an error ({one_line(e)}) · behind so far {counts['k']} · "
              f"likely behind so far {counts['j']}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
