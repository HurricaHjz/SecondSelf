#!/usr/bin/env python3
"""sort_check.py - the ingest Step 6 sort check: before a raw sort, after it, and the path-link scan.

Reads only: it creates, modifies, moves and deletes nothing. Whoever sorts (the head at merge-close,
or a lane its brief grants sorting) moves each file with `mv -n`; this script decides whether the
sort may start and whether it finished.

Why: no wiki page links a raw file by name (`sources:` holds the path), so a link-aware move has
nothing to update and can only rewrite a bare link whose name a raw shares with a page into a path
link. A plain move changes no page, but it has no collision boundary of its own: it can replace an
occupied archive destination, and an original/conversion pair can be left half moved.

Modes:
  pre   --vault ROOT SOURCE=DESTINATION[@SHA] [...]
        Name every file of the sort at once, both members of every original/conversion pair. A
        destination that exists, a source that does not, a destination folder that does not, or a
        file or destination named twice refuses the whole sort (exit 1): nothing may move. Exit 0
        prints one MOVE line per file with its sha256 prefix, the plan (every member with its
        prefix, a JSON list to record before any move) and the post command to run after the moves.
        A recovery names the recorded plan instead, each member with the prefix the first pre
        printed (SOURCE=DESTINATION@SHA): a member still in the inbox with that prefix is a MOVE,
        one already at its destination with it is IN PLACE, and one that changed or is missing
        from both places refuses the sort. The post it prints covers the whole recorded plan again, so a
        member moved before an interruption is verified before anything is recorded as sorted.
  post  --vault ROOT SOURCE=DESTINATION@SHA [...]
        After the moves: each source gone and each destination present with the recorded sha256
        prefix (MOVED), else NOT MOVED or MISMATCH; then the path-link scan. Exit 0 only when every
        move completed and the scan found no path link; only then is a `sorted` checkpoint written.
  pre|post --re-sort
        The same two checks for a raw already filed, moved within raw/ (into raw/duplicates/ above
        all): a source is then a file in a folder under raw/, never in the inbox, and its destination
        a file in another folder under raw/. pre also prints one `NAMES <page>: <path>` line per wiki
        page naming a source's path, since `sources:` holds the path and that page must follow the
        move or retire; NAMES decides nothing, and Step 7's link check catches one left dangling.
  links --vault ROOT
        The path-link scan alone: every Markdown page under wiki/, outside fenced code and code
        spans, for a wikilink or embed whose target starts raw/ or wiki/. One
        `PATHLINK <page>:<line>: <link>` line per hit. A symlinked page is read through its link;
        a symlinked folder, which the walk never enters, and a dangling symlink stop the scan.

Paths are vault-relative or absolute. A source is a file directly in raw/ (the inbox), or under
--re-sort a file in a folder under raw/; a destination sits in a folder under raw/.
Exit 0 = clear; 1 = a refused sort, an incomplete move or a path link; 2 = PROBE FAILED: no raw/ or
wiki/ under the vault, a malformed argument, a path outside raw/, an unreadable page or folder, a
symlinked folder or dangling symlink under wiki/ (pages the scan cannot read), a scan that found no
wikilink at all (it searched nothing), or a same-run control that did not behave.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import sys

sys.dont_write_bytecode = True
HASH_LENGTH = 16  # the sha256 prefix length the ingest de-dup's source_hash uses
LINK = re.compile(r"(!?)\[\[([^\]\n]+?)\]\]")
PATH_TARGET = re.compile(r"(?i)^(?:\./|/)?(?:raw|wiki)/")
CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")


class ProbeError(ValueError):
    pass


def link_target(inner):
    """The target of a wikilink's inner text: before the first (escaped) pipe or heading mark."""
    return re.split(r"\\?\||#", inner, maxsplit=1)[0].strip()


def scan_text(text):
    """(wikilinks, hits) for one page: every wikilink and embed outside fenced code and code spans,
    and the (line, link) of each whose target starts raw/ or wiki/."""
    links, hits, fence = 0, [], None
    for n, line in enumerate(text.splitlines(), 1):
        opener = FENCE.match(line)
        if fence is None and opener:
            fence = opener.group(1)
            continue
        if fence is not None:
            run = opener.group(1) if opener else ""
            if run and run[0] == fence[0] and len(run) >= len(fence) and not line.strip()[len(run):].strip():
                fence = None
            continue
        visible = CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)
        for m in LINK.finditer(visible):
            links += 1
            if PATH_TARGET.match(link_target(m.group(2))):
                hits.append((n, m.group(0)))
    return links, hits


def scan_wiki(vault):
    """(pages, wikilinks, [(page, line, link)]) over every Markdown page under wiki/. os.walk never
    enters a symlinked folder (followlinks=False), so the pages behind one would go unread: a
    symlinked folder, and a dangling symlink, are a broken premise, never skipped. A symlinked page
    is read through its link, under the link's own path."""
    errors, pages, links, hits, unread = [], 0, 0, [], []
    top = os.path.join(vault, "wiki")
    for root, dirs, files in os.walk(top, onerror=lambda e: errors.append(str(e))):
        dirs.sort()
        unread += [os.path.join(root, name) + " (symlinked folder)" for name in dirs
                   if os.path.islink(os.path.join(root, name))]
        unread += [os.path.join(root, name) + " (dangling symlink)" for name in sorted(files)
                   if os.path.islink(os.path.join(root, name)) and not os.path.exists(os.path.join(root, name))]
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            if os.path.islink(path) and not os.path.exists(path):
                continue  # named above: a dangling link stops the scan
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
            except OSError as error:
                raise ProbeError("unreadable page, never skipped: %s (%s)" % (path, error))
            pages += 1
            n, found = scan_text(text)
            links += n
            hits += [(os.path.relpath(path, vault), line, link) for line, link in found]
    if errors:
        raise ProbeError("unreadable folder under wiki/: " + "; ".join(errors[:3]))
    if unread:
        raise ProbeError("%d symlink(s) under wiki/ the scan cannot read through, never skipped: %s"
                         % (len(unread), "; ".join(os.path.relpath(u, vault) for u in unread[:3])
                            + ("; …" if len(unread) > 3 else "")))
    if not pages:
        raise ProbeError("no Markdown page under wiki/: the scan searched nothing")
    if not links:
        raise ProbeError("%d pages but no wikilink at all: the scan searched nothing" % pages)
    return pages, links, hits


def sha_prefix(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()[:HASH_LENGTH]


class Disk:
    """The real filesystem, read only."""
    def exists(self, path):
        return os.path.lexists(path)

    def isdir(self, path):
        return os.path.isdir(path)

    def sha(self, path):
        return sha_prefix(path)


def plan(pairs, state):
    """[(verdict, source, destination, detail)] for the whole sort. pairs holds (source,
    destination, recorded): recorded is None for a fresh member, or the sha256 prefix the first pre
    printed for a member of a recorded plan (a recovery). MOVE carries the prefix to verify after
    the move; IN PLACE is a recorded member already at its destination with its recorded prefix;
    REFUSED gives the reason. A file or destination named twice is refused too."""
    out = []
    sources = [p[0] for p in pairs]
    destinations = [p[1] for p in pairs]
    for source, destination, recorded in pairs:
        if sources.count(source) > 1:
            out.append(("REFUSED", source, destination, "source named twice"))
        elif destinations.count(destination) > 1:
            out.append(("REFUSED", source, destination, "destination named twice"))
        elif state.exists(source):
            if state.exists(destination):
                out.append(("REFUSED", source, destination,
                            "destination exists (sha256:%s), never overwritten" % state.sha(destination)))
            elif not state.isdir(os.path.dirname(destination)):
                out.append(("REFUSED", source, destination, "destination folder missing"))
            elif recorded and state.sha(source) != recorded:
                out.append(("REFUSED", source, destination, "source changed since the plan "
                            "(sha256:%s, recorded %s)" % (state.sha(source), recorded)))
            else:
                out.append(("MOVE", source, destination, "sha256:" + (recorded or state.sha(source))))
        elif not recorded:
            out.append(("REFUSED", source, destination, "source missing"))
        elif not state.exists(destination):
            out.append(("REFUSED", source, destination, "member missing: neither in the inbox nor at "
                        "its destination (recorded %s)" % recorded))
        elif state.sha(destination) != recorded:
            out.append(("REFUSED", source, destination, "moved member changed since the plan "
                        "(destination sha256:%s, recorded %s)" % (state.sha(destination), recorded)))
        else:
            out.append(("IN PLACE", source, destination, "sha256:" + recorded))
    return out


def verify(moves, state):
    """[(verdict, source, destination, detail)] after the moves: MOVED, NOT MOVED or MISMATCH."""
    out = []
    for source, destination, expected in moves:
        if state.exists(source):
            out.append(("NOT MOVED", source, destination, "source still present"))
        elif not state.exists(destination):
            out.append(("NOT MOVED", source, destination, "destination absent"))
        elif state.sha(destination) != expected:
            out.append(("MISMATCH", source, destination,
                        "destination sha256:%s, recorded %s" % (state.sha(destination), expected)))
        else:
            out.append(("MOVED", source, destination, "sha256:" + expected))
    return out


class Fake:
    """An in-memory tree for the controls: {path: bytes} and a set of folders."""
    def __init__(self, files, folders):
        self.files, self.folders = files, folders

    def exists(self, path):
        return path in self.files or path in self.folders

    def isdir(self, path):
        return path in self.folders

    def sha(self, path):
        return hashlib.sha256(self.files[path]).hexdigest()[:HASH_LENGTH]


def digest(data):
    return hashlib.sha256(data).hexdigest()[:HASH_LENGTH]


def controls():
    """Planted cases through the functions that decide; raises ProbeError when one misbehaves."""
    links, hits = scan_text("A [" "[Page]] and a [" "[raw/x/y]] and ![" "[wiki/sources/z|alias]].\n"
                            "`[" "[raw/in/span]]` stays code.\n"
                            "```\n[" "[raw/in/fence]]\n```\n")
    if links != 3 or [h[0] for h in hits] != [1, 1]:
        raise ProbeError("path-link controls failed (%d links, hits %r)" % (links, hits))
    tree = Fake({"/c/raw/a.md": b"a", "/c/raw/a.pdf": b"p", "/c/raw/2/a.pdf": b"old"}, {"/c/raw", "/c/raw/2"})
    cases = [([("/c/raw/a.md", "/c/raw/2/a.md"), ("/c/raw/a.pdf", "/c/raw/2/a.pdf")], ["MOVE", "REFUSED"]),
             ([("/c/raw/b.md", "/c/raw/2/b.md")], ["REFUSED"]),
             ([("/c/raw/a.md", "/c/raw/9/a.md")], ["REFUSED"]),
             ([("/c/raw/a.md", "/c/raw/2/a.md"), ("/c/raw/a.md", "/c/raw/2/b.md")], ["REFUSED", "REFUSED"]),
             ([("/c/raw/a.md", "/c/raw/2/a.md")], ["MOVE"])]
    planned = [plan([pair + (None,) for pair in pairs], tree) for pairs, _want in cases]
    reasons = [planned[0][1][3], planned[1][0][3], planned[2][0][3], planned[3][0][3]]
    if ([tuple(p[0] for p in got) for got in planned] != [tuple(want) for _pairs, want in cases]
            or "never overwritten" not in reasons[0]
            or reasons[1:] != ["source missing", "destination folder missing", "source named twice"]
            or tree.files["/c/raw/2/a.pdf"] != b"old"):
        raise ProbeError("sort refusal controls failed: %r" % (planned,))
    half = Fake({"/c/raw/a.md": b"a", "/c/raw/2/a.pdf": b"p"}, {"/c/raw", "/c/raw/2"})
    checked = verify([("/c/raw/a.md", "/c/raw/2/a.md", digest(b"a")), ("/c/raw/a.pdf", "/c/raw/2/a.pdf", digest(b"p")),
                      ("/c/raw/c.md", "/c/raw/2/a.pdf", digest(b"other"))], half)
    if [c[0] for c in checked] != ["NOT MOVED", "MOVED", "MISMATCH"]:
        raise ProbeError("move verification controls failed: %r" % (checked,))
    resumed = [plan([("/c/raw/a.md", "/c/raw/2/a.md", digest(b"a")), ("/c/raw/a.pdf", "/c/raw/2/a.pdf", digest(b"p"))], half),
               plan([("/c/raw/a.pdf", "/c/raw/2/a.pdf", digest(b"other"))], half),
               plan([("/c/raw/b.pdf", "/c/raw/2/b.pdf", digest(b"p"))], half),
               plan([("/c/raw/a.md", "/c/raw/2/a.md", digest(b"other"))], half)]
    if ([tuple(p[0] for p in got) for got in resumed] != [("MOVE", "IN PLACE"), ("REFUSED",), ("REFUSED",), ("REFUSED",)]
            or [got[0][3].split(" (")[0] for got in resumed[1:]]
            != ["moved member changed since the plan", "member missing: neither in the inbox nor at its destination",
                "source changed since the plan"]):
        raise ProbeError("recovery controls failed: %r" % (resumed,))
    return ("controls: an occupied destination, a missing source, a missing folder and a doubled "
            "source refused · a half-moved pair read NOT MOVED · a changed destination read MISMATCH · "
            "a resumed pair's moved member read IN PLACE, a changed, missing or altered member REFUSED · "
            "a planted raw/ and wiki/ path link hit while a bare link, a code span and a fenced block did not")


def vault_root(value):
    root = os.path.realpath(value)
    for name in ("raw", "wiki"):
        if not os.path.isdir(os.path.join(root, name)):
            raise ProbeError("%s has no %s/ folder: not a vault root (pass --vault)" % (root, name))
    return root


def inside_raw(vault, value, inbox):
    """The real path of a source (inbox=True: a file directly in raw/) or of a file in a folder under
    raw/ (inbox=False: a destination, or a source under --re-sort); anything else is a broken premise."""
    raw = os.path.join(vault, "raw")
    path = os.path.realpath(value if os.path.isabs(value) else os.path.join(vault, value))
    parent = os.path.dirname(path)
    if inbox and parent != raw:
        raise ProbeError("source %s is not a file directly in raw/ (the inbox)" % value)
    if not inbox and (parent == raw or not parent.startswith(raw + os.sep)):
        raise ProbeError("%s is not in a folder under raw/" % value)
    return path


def parse_pairs(vault, values, need_hash, re_sort=False):
    """[(source, destination, recorded sha256 prefix or None)]. post needs every prefix; pre takes
    one where a recovery names a member of the recorded plan. Under re_sort a source is a filed raw,
    and its destination sits in another folder: a move inside one folder is no re-sort."""
    out = []
    for value in values:
        spec, at, digest = value.rpartition("@")
        if not (at and re.fullmatch(r"[0-9a-f]{%d}" % HASH_LENGTH, digest)):
            spec, digest = value, None  # no recorded prefix (an @ in a file name stays in the path)
        source, sep, destination = spec.partition("=")
        if not (sep and source and destination) or (need_hash and digest is None):
            raise ProbeError("want SOURCE=DESTINATION%s, got %r" % ("@SHA" if need_hash else "[@SHA]", value))
        from_path = inside_raw(vault, source, not re_sort)
        to_path = inside_raw(vault, destination, False)
        if re_sort and os.path.dirname(from_path) == os.path.dirname(to_path):
            raise ProbeError("re-sort of %s stays in one folder: name another folder under raw/" % source)
        out.append((from_path, to_path, digest))
    if not out:
        raise ProbeError("no SOURCE=DESTINATION named: nothing to check")
    return out


def rel(vault, path):
    return os.path.relpath(path, vault)


def pages_naming(vault, paths):
    """[(page, vault-relative path)] for each wiki page whose text names one of `paths`, read as
    scan_wiki reads the pages (a page it cannot read stops the scan there, as a broken probe)."""
    wanted = [rel(vault, p) for p in paths]
    out = []
    wiki = os.path.join(vault, "wiki")
    for folder, _dirs, names in os.walk(wiki):
        for name in sorted(names):
            if not name.endswith(".md"):
                continue
            page = os.path.join(folder, name)
            with open(page, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            out += [(rel(vault, page), w) for w in wanted if w in text]
    return sorted(out)


def run_links(vault):
    pages, links, hits = scan_wiki(vault)
    for page, line, link in hits:
        print("PATHLINK %s:%d: %s" % (page, line, link))
    print("path-links: pages %d · wikilinks %d · hits %d" % (pages, links, len(hits)))
    return len(hits)


def main(argv=None):
    ap = argparse.ArgumentParser(description="The ingest Step 6 sort check (reads only).",
                                 epilog="Exit 0 clear; 1 refused, incomplete or a path link; 2 PROBE FAILED.")
    ap.add_argument("mode", choices=("pre", "post", "links"))
    ap.add_argument("--vault", required=True, help="the vault root (holds raw/ and wiki/)")
    ap.add_argument("--re-sort", action="store_true",
                    help="pre or post: the sources are raws already filed, moved within raw/")
    ap.add_argument("pairs", nargs="*", metavar="SOURCE=DESTINATION[@SHA]")
    args = ap.parse_args(argv)
    try:
        line = controls()
        vault = vault_root(args.vault)
        if args.mode == "links":
            if args.pairs or args.re_sort:
                raise ProbeError("links takes no SOURCE=DESTINATION and no --re-sort")
            hits = run_links(vault)
            print(line)
            return 1 if hits else 0
        if args.mode == "pre":
            planned = plan(parse_pairs(vault, args.pairs, False, args.re_sort), Disk())
            refused = [p for p in planned if p[0] == "REFUSED"]
            for verdict, source, destination, detail in planned:
                pair = "%s -> %s" % (rel(vault, source), rel(vault, destination))
                if verdict == "REFUSED":
                    print("REFUSED %s: %s" % (pair, detail))
                elif verdict == "IN PLACE":  # moved before an interruption; nothing to move
                    print("IN PLACE %s %s" % (pair, detail))
                elif refused:  # a refused sort moves nothing, so it prints no MOVE line to act on
                    print("WAITS %s: the sort is refused" % pair)
                else:
                    print("MOVE %s %s" % (pair, detail))
            if refused:
                print("pre: files %d · refused %d — nothing may move; resolve each refusal and run pre again"
                      % (len(planned), len(refused)))
            else:
                specs = ["%s=%s@%s" % (rel(vault, s), rel(vault, d), detail[len("sha256:"):])
                         for _v, s, d, detail in planned]
                moving = sum(p[0] == "MOVE" for p in planned)
                print("pre: files %d · to move %d · in place %d · refused 0 — record the plan, move each "
                      "MOVE line with mv -n, then run post:" % (len(planned), moving, len(planned) - moving))
                # JSON with every non-ASCII character and apostrophe escaped: it pastes into a
                # single-quoted printf argument unchanged.
                print("plan: " + json.dumps(specs).replace("'", "\\u0027"))
                post = ["python3", os.path.abspath(__file__), "post", "--vault", vault] + specs
                post += ["--re-sort"] if args.re_sort else []
                print("post: " + " ".join(shlex.quote(part) for part in post))
                if args.re_sort:
                    for page, path in pages_naming(vault, [p[1] for p in planned]):
                        print("NAMES %s: %s" % (page, path))
            print(line)
            return 1 if refused else 0
        checked = verify(parse_pairs(vault, args.pairs, True, args.re_sort), Disk())
        for verdict, source, destination, detail in checked:
            print("%s %s -> %s: %s" % (verdict, rel(vault, source), rel(vault, destination), detail))
        bad = [c for c in checked if c[0] != "MOVED"]
        print("sort: files %d · moved %d · not moved %d · mismatched %d"
              % (len(checked), len(checked) - len(bad), sum(c[0] == "NOT MOVED" for c in checked),
                 sum(c[0] == "MISMATCH" for c in checked)))
        hits = run_links(vault)
        print(line)
        return 1 if bad or hits else 0
    except (OSError, ProbeError) as error:
        print("PROBE FAILED: %s" % error)
        return 2
    except Exception as error:  # an unexpected failure is a broken probe, never a finding (exit 1)
        print("PROBE FAILED: internal error %s: %s" % (type(error).__name__, error))
        return 2


if __name__ == "__main__":
    sys.exit(main())
