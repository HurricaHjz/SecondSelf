#!/usr/bin/env python3
"""capture_probe.py — structural capture routing for a web page, and the capture check: a comparison
of a capture with the page the probe fetched, recorded by both save paths as a stamp that warns and
never blocks a write (the gather skill's capture_write.py, and the ingest skill's Step 0 through the
`stamp` verb).

WHY. An article extractor keeps what a reader sees on first load. Text inside a collapsed block
(a details element, a hidden or aria-hidden panel, an accordion) and the labels of a tabbed set
can be dropped while the capture still reads clean, and a conversion score measures only the
text it receives. So a page whose fetched HTML carries such a block is converted whole instead,
each tab label set directly before its own panel, and a capture is compared with the fetched page
so that a loss the comparison sees is written down with the capture.

ONE FETCH, ONE REPRESENTATION. `capture` fetches the page once and routes, converts and
checks that same file:
  ROUTE       a structural marker (below): the page is normalised (each tab label becomes a
              heading directly before its own panel, each details element a block whose summary
              is a bold line before its body, every link destination absolute) and converted by
              `python3 -m markitdown`. Engine: ROUTE_ENGINE.
  NOT-ROUTED  no marker: link destinations are made absolute and defuddle converts the fetched
              copy, never the URL, so nothing is fetched twice. Engine: PLAIN_ENGINE.
THE CHECK reads the fetched ORIGINAL, never the normalised copy, so a normaliser that drops or
mispairs content cannot supply its own answer. It looks for every collapsed container's text in the
capture, whatever its length, in its own order within that container; for every tab label directly
before its own panel's content, after the previous panel's; and for any relative link destination
that survived (the sanitisers downstream defang or strand one). The comparison keeps
every character that carries a value: a table cell holding only a symbol (a check mark, a cross,
a dash) is a unit like any other, and an inequality sign is part of its value, so "< 101" never
matches "> 101"; only Markdown's own punctuation is set aside. Tab labels are paired only through
structures whose pairing is unambiguous: ARIA ids (a tab's aria-controls, or a panel's aria-labelledby, agreeing where both
are present) and mkdocs tabbed sets (whose CSS pairs the i-th label with the i-th block, or a
label with the content right after it). Any other tab structure, a panel no tab reaches, or a
conflict, is ambiguous: such a page is not converted on the structural route, and the check does
not run on it.
THE CHECK ONLY WARNS. What it finds never refuses a write and never fails the probe: a save path
records it as the capture's stamp (STAMP below), and a missing, malformed or failed check is stamped
as not run, never as no loss.

MARKERS (any one routes; no word threshold and no content comparison; each must hold text, a
letter or a digit): a details element; an element with the hidden attribute, aria-hidden="true",
or inline display:none or visibility:hidden; a class `collapse` or one starting `accordion`;
role tablist or tabpanel; an mkdocs tabbed-set, tabbed-content or tabbed-block; a Webflow dropdown
panel, class `w-dropdown-list`, outside a Webflow navbar (a FAQ's answers sit in such panels, written
as nav elements, and defuddle 0.19.4 drops a nav element whole, whatever its class); a controlled
collapsed or tabbed target, i.e. an element whose id another element's aria-controls names, when
that controller reads aria-expanded="false" or role="tab", or the target is a tab panel or
hidden. A controller naming a visible, expanded target (a sort button over a result list) does
not route, and neither does a dropdown inside a navbar (an element of class `w-nav`): that is the
site's menu, not the page's content. markitdown keeps hidden text as it stands (measured on
markitdown 0.1.8), so the normaliser rewrites no visibility; were a later release to drop it, the
check would find the loss.

VERBS
  capture URL --work DIR [--curl P] [--defuddle P] [--python P] [--user-agent UA]
      The whole chain. DIR must be new or empty and outside any vault (a directory holding raw/
      and wiki/). Writes DIR/page.html (the fetched bytes), DIR/converted.html (the copy the
      converter read), DIR/capture.md and DIR/result.json, and nothing else. Exit 0: a capture
      was made, and the check's stamp for it is printed whatever the check found; 2 PROBE FAILED:
      no capture was made (result.json records the stage and the reason).
  stamp RESULT --body FILE --url URL --engine ENGINE [--allow-degraded WHY]
      Stdout only, for a save path with no writer of its own (ingest Step 0): checks FILE against
      the page the result names and prints the provenance lines to prepend: converted_from (URL),
      converted_by (ENGINE, the engine that produced FILE, never taken from the result), the
      capture_check stamp and, with WHY, capture_quality "declared — WHY" (damage the check cannot
      see), then the checkpoint values to record. Exit 0 whatever the check found and whether or
      not it ran; 2 only when no provenance can be printed: FILE unreadable or empty, URL not one
      http(s) URL, ENGINE or WHY empty or longer than one line.
  route PAGE --http 'CODE CONTENT-TYPE' --curl-exit N
      Stdout only: exit 0 NOT-ROUTED, 1 ROUTE (each marker named), 2 PROBE FAILED.
  normalise PAGE --base-url URL -o OUT
      Writes OUT only (new, outside any vault): the copy ROUTE converts. Exit 0, or 2.
  check PAGE CAPTURE --base-url URL
      Stdout only: the check alone, its stamp printed. Exit 0 no loss found, 1 suspected loss,
      2 not run (ambiguous tabs) or PROBE FAILED.

PROBE FAILED (exit 2, no capture made) on: curl failing, whatever status it printed (a transfer
can fail after a 200 header); an HTTP status outside 2xx, however substantial the body; a content
type that is not HTML; a missing, empty or unparsable page; ambiguous tab pairing on a page that
routes; a converter that fails or prints nothing; a failed built-in control (planted pages and
captures, checked on every run before the real page); any unexpected exception before the capture
is written. A failed run still writes result.json with status "fail" where its directory is its
own. What the check finds never fails the probe, and a check that cannot run leaves the capture
made, its verdict "not run".

LANE GRANTS. A lane's command fence reads a script run as a read, so it sees neither the fetch nor
the writes inside this script, and the script honours the lane's own grants itself. In a lane
(LLM_WIKI_LANE set, and not the head role, LLM_WIKI_FENCE_ROLE=head, whose network grant lives in its
grant file) a fetch needs its host named in LLM_WIKI_LANE_NETWORK (hosts separated by commas or
whitespace; empty or absent is no network; an exact host or a subdomain of a listed one), and no
redirect is followed (one could leave the grant; its target is named in the failure instead).
Wherever LLM_WIKI_LANE_WRITES is present, as the ingest skill's sanitise.py reads it, a file is
written only inside those roots or the scratch root /tmp. Elsewhere nothing here changes.

THE RESULT (result.json, schema RESULT_SCHEMA) records the URL; curl's exit status with the HTTP
status, content type and effective URL; the base URL; the route, markers and engine; the sha256
of the fetched page and of the capture; and the check of the probe's own capture (its verdict, its
counts and its findings). Its status says only whether the chain made its capture ("pass") or not
("fail"); what the check found is the check's verdict, never the status.

STAMP. `check_stamp` (capture_write.py's write, and `stamp`) holds a result to the URL being saved,
which is required; it reads a record of a capture (status pass) only when it is complete and agrees
with itself and with the page (`result_problems`: the fetch a successful HTML transfer, the controls
this probe's own, the converter the route's, the check's counts and verdict matching the page, the
files it names present with the hashes it records), and a failed probe's record only where the
probe fetched the page (`page_problems`). It then re-reads that page, recomputes its route and base,
and checks the body about to be saved against it, whichever engine produced that body. The stamp
is one line, in one of three forms:
  "suspected loss — <findings> (<counts>); <CHECK_LIMITS>"
  "no loss found by the unit check (<counts>); <CHECK_LIMITS>"
  "not run — <why>": no result, an unreadable, malformed or failed one, a page the probe never
      fetched, tabs the check cannot pair, a check that failed to run.
It never says that a capture is verified, complete or clean: CHECK_LIMITS names what the unit check
does not compare. Nothing here records anything in a run ledger.
"""
import argparse
import codecs
import collections
import datetime
import hashlib
import html as html_lib
import json
import os
import re
import subprocess
import sys
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

RESULT_SCHEMA = "capture-probe-result/2"   # /1 was the stopped admission design's record
ROUTE_ENGINE = "curl+markitdown (structural route)"
PLAIN_ENGINE = "curl+defuddle"
# The fetch sends defuddle 0.19's own request headers (its DEFAULT_UA and Accept, and its bot
# variant for github.com), so a server answers this fetch as it answered defuddle's.
DEFUDDLE_UA = "Mozilla/5.0 (compatible; Defuddle/1.0; +https://defuddle.md)"
BOT_UA_HOSTS = ("github.com",)
ACCEPT = "text/html,application/xhtml+xml"
CURL_MAX_TIME = 120        # seconds for one fetch; set by judgement, unmeasured
CURL_MAX_REDIRS = 10       # redirects followed; set by judgement, unmeasured
CONVERT_TIMEOUT = 300      # seconds for one converter run; set by judgement, unmeasured
REASON_MAX = 300           # characters of a reason kept in a result or a stamp; set by judgement
SHOW_MAX = 5               # failures named per check; set by judgement
SNIFF_BYTES = 4096         # meta-charset prescan; set by judgement, above the HTML standard's 1,024
META_SENTINEL = "capture-probe-meta"
CURL_FORMAT = ("\n" + META_SENTINEL + " %{http_code}\t%{content_type}\t%{url_effective}\t%{num_redirects}"
               "\t%{redirect_url}\n")
LANE_VAR, NETWORK_VAR, WRITES_VAR = "LLM_WIKI_LANE", "LLM_WIKI_LANE_NETWORK", "LLM_WIKI_LANE_WRITES"
HTML_TYPES = ("text/html", "application/xhtml+xml")
EXIT_PASS, EXIT_ROUTE, EXIT_FAILED = 0, 1, 2
# The capture check's three verdicts, and the stamp's opening words for each.
VERDICT_NONE, VERDICT_LOSS, VERDICT_NOT_RUN = "no loss found", "suspected loss", "not run"
VERDICTS = (VERDICT_NONE, VERDICT_LOSS, VERDICT_NOT_RUN)
# What the unit check does not compare, named in the stamp of every check that ran: it reads only the
# text of collapsed blocks and tab panels; it sets Markdown's own punctuation aside on both sides
# (STRIP_CHARS below); it reads a table as runs of text, so an empty cell leaves no unit; it compares
# no image and no link target beyond catching a relative one; it folds case and collapses spacing.
CHECK_LIMITS = ("not compared: text outside collapsed blocks and tab panels, literal punctuation Markdown also "
                "uses (asterisks, underscores, backticks, tildes, bars, hashes, brackets, backslashes and double "
                "quotes), empty-cell positions in tables, images and link targets other than a relative one, "
                "case and spacing")
FINDINGS_MAX = 400         # characters of findings kept in a stamp; set by judgement, unmeasured
STAMP_MAX = 900            # characters of a whole stamp: FINDINGS_MAX, the counts and CHECK_LIMITS fit; set by judgement


class ProbeFailure(Exception):
    def __init__(self, stage, reason):
        super().__init__(reason)
        self.stage, self.reason = stage, reason


WS = re.compile(r"\s+")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def squash(text):
    return WS.sub(" ", text).strip()


def clip(text, limit=REASON_MAX):
    text = squash(CONTROL_CHARS.sub(" ", str(text)))
    return text if len(text) <= limit else text[: limit - 1] + "…"


# A provenance field name followed by its colon: a frontmatter reader that looks for an engine field
# anywhere on a line (the deep-lint skill's recapture compare refuses such a line) must never meet one
# inside a stamp, which can quote a page's own text.
ENGINE_FIELD_LIKE = re.compile(r"(?i)(?<![a-z0-9_])(['\"]?)(converted_by|conversion_engine|converter)(['\"]?)[ \t]*:")


def stamp_value(text, limit=STAMP_MAX):
    """One line fit for a double-quoted frontmatter value: control characters and line breaks gone,
    a double quote written as a single one and a backslash as a slash (either would end or escape the
    value), and a provenance field name never followed by its colon."""
    text = clip(text, limit).replace('"', "'").replace("\\", "/")
    return ENGINE_FIELD_LIKE.sub(lambda m: m.group(1) + m.group(2) + m.group(3) + " -", text)


def has_word(text):
    return any(ch.isalnum() for ch in text)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- the document tree
VOID = frozenset("area base br col embed hr img input keygen link meta param source track wbr".split())
RAW_TEXT = frozenset(("script", "style"))
FOREIGN = frozenset(("svg", "math"))
HEADINGS = frozenset(("h1", "h2", "h3", "h4", "h5", "h6"))
P_CLOSERS = frozenset((
    "address article aside blockquote center details dialog dir div dl dd dt fieldset figcaption "
    "figure footer form h1 h2 h3 h4 h5 h6 header hgroup hr li main menu nav ol p pre section "
    "summary table ul").split())
SCOPE_STOP = frozenset("html table td th caption object template button marquee applet".split())
TABLE_TAGS = frozenset("table caption colgroup tbody thead tfoot tr td th".split())
# Unit boundaries: the elements markitdown sets apart from unspaced neighbours (measured on
# markitdown 0.1.8 by wrapping each tag between unspaced words), plus details and summary, which the
# normaliser turns into blocks itself. Splitting where the converter glues would give a finding on a
# capture that lost nothing; joining where it separates is harmless, since whitespace is collapsed
# before comparing.
BLOCK = frozenset((
    "article blockquote br dd details div dl dt figcaption h1 h2 h3 h4 h5 h6 hr li ol p pre section "
    "summary table td th tr ul").split())
# Subtrees whose text is not page prose a converter renders (form controls, media, scripts). The
# routing, the tab analysis and the validation all skip the same subtrees, so they never disagree.
EXCLUDED = frozenset((
    "script style template noscript svg math select textarea head title iframe object embed "
    "canvas datalist audio video").split())
MARKER_SKIP = EXCLUDED


class Node:
    __slots__ = ("tag", "attrs", "children", "parent", "data")

    def __init__(self, tag, attrs=None, data=None):
        self.tag, self.attrs, self.data = tag, ({} if attrs is None else attrs), data
        self.children, self.parent = [], None

    def append(self, child):
        child.parent = self
        self.children.append(child)

    def get(self, name, default=None):
        return self.attrs.get(name, default)

    @property
    def is_element(self):
        return not self.tag.startswith("#")


def iter_elements(root, skip=frozenset()):
    """Elements below root in document order; a skipped element and its subtree are not visited."""
    stack = [c for c in reversed(root.children) if c.is_element and c.tag not in skip]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(c for c in reversed(node.children) if c.is_element and c.tag not in skip)


def ancestors(node):
    node = node.parent
    while node is not None:
        yield node
        node = node.parent


def is_ancestor(a, b):
    """True when a is b or an ancestor of b."""
    while b is not None:
        if b is a:
            return True
        b = b.parent
    return False


class _TreeBuilder(HTMLParser):
    """A tolerant tree: the HTML standard's implied end tags for p, li, dd, dt, table cells and rows,
    headings and options; an end tag with no open match, or one that would cross a table cell or a
    button, is ignored; void and foreign self-closing elements take no children."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def _close(self, names, stop):
        for i in range(len(self.stack) - 1, 0, -1):
            tag = self.stack[i].tag
            if tag in names:
                del self.stack[i:]
                return
            if tag in stop:
                return

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, True)

    def _start(self, tag, attrs, selfclosing):
        foreign = any(n.tag in FOREIGN for n in self.stack)
        if not foreign:
            if tag in P_CLOSERS:
                self._close(("p",), SCOPE_STOP)
            if tag == "li":
                self._close(("li",), SCOPE_STOP | {"ul", "ol"})
            elif tag in ("dd", "dt"):
                self._close(("dd", "dt"), SCOPE_STOP | {"dl"})
            elif tag in ("td", "th"):
                self._close(("td", "th"), {"tr", "table", "html", "template"})
            elif tag == "tr":
                self._close(("tr",), {"table", "html", "template"})
            elif tag in ("thead", "tbody", "tfoot"):
                self._close(("thead", "tbody", "tfoot"), {"table", "html", "template"})
            elif tag in HEADINGS and self.stack[-1].tag in HEADINGS:
                self.stack.pop()
            elif tag in ("option", "optgroup") and self.stack[-1].tag == "option":
                self.stack.pop()
        node = Node(tag)
        for name, value in attrs:
            node.attrs.setdefault(name, value)
        self.stack[-1].append(node)
        if tag in VOID or (selfclosing and (foreign or tag in FOREIGN)):
            return
        self.stack.append(node)

    def handle_endtag(self, tag):
        if tag in VOID:
            if tag == "br":
                self._start("br", [], False)
            return
        stop = frozenset() if tag in TABLE_TAGS else SCOPE_STOP
        for i in range(len(self.stack) - 1, 0, -1):
            here = self.stack[i].tag
            if here == tag:
                del self.stack[i:]
                return
            if here in stop:
                return

    def handle_data(self, data):
        top = self.stack[-1]
        if top.children and top.children[-1].tag == "#text":
            top.children[-1].data += data
        else:
            top.append(Node("#text", data=data))

    def handle_comment(self, data):
        self.stack[-1].append(Node("#comment", data=data))

    def handle_decl(self, decl):
        self.stack[-1].append(Node("#decl", data=decl))

    def unknown_decl(self, data):
        pass


def parse_html(text):
    builder = _TreeBuilder()
    builder.feed(text)
    builder.close()
    return builder.root


def text_of(node, skip=EXCLUDED):
    """The raw text below node, excluded subtrees left out."""
    parts, stack = [], [node]
    while stack:
        cur = stack.pop()
        if cur.tag == "#text":
            parts.append(cur.data)
        elif (cur.is_element or cur.tag == "#root") and (cur is node or cur.tag not in skip):
            stack.extend(reversed(cur.children))
    return "".join(parts)


def describe(node):
    ident = node.get("id")
    classes = (node.get("class") or "").split()[:2]
    return "<" + node.tag + ("#" + ident if ident else "") + "".join("." + c for c in classes) + ">"


# ---------------------------------------------------------------- markers
DISPLAY_NONE = re.compile(r"(?:^|;)\s*display\s*:\s*none\s*(?:!\s*important\s*)?(?=;|$)", re.I)
VISIBILITY_HIDDEN = re.compile(r"(?:^|;)\s*visibility\s*:\s*hidden\s*(?:!\s*important\s*)?(?=;|$)", re.I)


def tokens(node, name):
    return (node.get(name) or "").split()


def hiding_markers(node):
    found = []
    if "hidden" in node.attrs:
        found.append("hidden attribute")
    if (node.get("aria-hidden") or "").strip().lower() == "true":
        found.append("aria-hidden")
    style = node.get("style") or ""
    if DISPLAY_NONE.search(style):
        found.append("inline display:none")
    if VISIBILITY_HIDDEN.search(style):
        found.append("inline visibility:hidden")
    return found


def controllers_by_target(root):
    out = collections.defaultdict(list)
    for node in iter_elements(root, MARKER_SKIP):
        for target in tokens(node, "aria-controls"):
            out[target].append(node)
    return out


def own_markers(node, controllers):
    """The marker names this element carries itself (whether it holds text is the caller's test)."""
    found = ["details"] if node.tag == "details" else []
    found += hiding_markers(node)
    classes = tokens(node, "class")
    if "collapse" in classes:
        found.append("class collapse")
    if any(c.startswith("accordion") for c in classes):
        found.append("class accordion*")
    if "w-dropdown-list" in classes and not any("w-nav" in tokens(a, "class") for a in ancestors(node)):
        found.append("class w-dropdown-list")
    roles = tokens(node, "role")
    for role in ("tablist", "tabpanel"):
        if role in roles:
            found.append("role " + role)
    for cls in ("tabbed-set", "tabbed-content", "tabbed-block"):
        if cls in classes:
            found.append("mkdocs " + cls)
    ident = node.get("id")
    if ident and ident in controllers:
        collapsed_or_tab = any((c.get("aria-expanded") or "").strip().lower() == "false"
                               or "tab" in tokens(c, "role") for c in controllers[ident])
        if collapsed_or_tab or "tabpanel" in roles or hiding_markers(node):
            found.append("controlled collapsed or tabbed target")
    return found


def find_markers(root):
    """Counter of marker names over the elements that carry one and hold text."""
    controllers = controllers_by_target(root)
    counts = collections.Counter()
    for node in iter_elements(root, MARKER_SKIP):
        names = own_markers(node, controllers)
        if names and has_word(text_of(node)):
            counts.update(names)
    return counts


def marker_line(markers):
    return ", ".join(f"{name} ×{n}" for name, n in sorted(markers.items())) or "none"


# ---------------------------------------------------------------- tab sets and their pairing
class TabSet:
    __slots__ = ("kind", "root", "pairs")

    def __init__(self, kind, root, pairs):
        self.kind, self.root, self.pairs = kind, root, pairs   # pairs: (label text, panel, label node)


def label_text(node):
    text = squash(text_of(node))
    if not has_word(text):
        text = squash(node.get("aria-label") or node.get("title") or "")
    return text if has_word(text) else ""


def _mkdocs_set(node):
    kids = [k for k in node.children if k.is_element]
    boxes = [k for k in kids if "tabbed-labels" in tokens(k, "class")]
    contents = [k for k in kids if "tabbed-content" in tokens(k, "class")]
    inputs = [k for k in kids if k.tag == "input"]
    if boxes:
        # Alternate style: the set's inputs, one labels box, one content box of blocks; the CSS shows
        # the i-th block when the i-th input is checked, and a label checks the input its for= names.
        if len(boxes) != 1 or len(contents) != 1:
            return None, f"an mkdocs tabbed set with {len(boxes)} label boxes and {len(contents)} content boxes"
        labels = [k for k in boxes[0].children if k.is_element and k.tag == "label"]
        blocks = [k for k in contents[0].children if k.is_element and "tabbed-block" in tokens(k, "class")]
        ids = [k.get("id") for k in inputs]
        if not (len(labels) == len(blocks) == len(inputs) > 0):
            return None, (f"an mkdocs tabbed set with {len(labels)} labels, {len(inputs)} inputs "
                          f"and {len(blocks)} blocks")
        pairs, used = [], set()
        for lab in labels:
            target = lab.get("for")
            if not target or target in used or ids.count(target) != 1:
                return None, "an mkdocs tab label whose for= names no single input of its set"
            used.add(target)
            text = label_text(lab)
            if not text:
                return None, "an mkdocs tab label with no text"
            pairs.append((text, blocks[ids.index(target)], lab))
        return TabSet("mkdocs-order", node, pairs), None
    # Classic style: input, label, content, repeated; the CSS shows the content right after the label.
    pairs = []
    for i, kid in enumerate(kids):
        if kid.tag == "label":
            nxt = kids[i + 1] if i + 1 < len(kids) else None
            if nxt is None or "tabbed-content" not in tokens(nxt, "class"):
                return None, "an mkdocs tab label not followed by its content"
            text = label_text(kid)
            if not text:
                return None, "an mkdocs tab label with no text"
            pairs.append((text, nxt, kid))
    if not pairs or len(pairs) != len(contents):
        return None, f"an mkdocs tabbed set with {len(pairs)} labelled contents of {len(contents)}"
    return TabSet("mkdocs-adjacent", node, pairs), None


def _nearest_tablist(node):
    for anc in ancestors(node):
        if "tablist" in tokens(anc, "role"):
            return anc
    return None


def _aria_set(tablist, by_id, duplicates, labelled_by):
    tabs = [n for n in iter_elements(tablist, MARKER_SKIP)
            if "tab" in tokens(n, "role") and _nearest_tablist(n) is tablist]
    if not tabs:
        return None, "a tablist with no tab"
    pairs, used = [], set()
    for tab in tabs:
        controls = tokens(tab, "aria-controls")
        if len(controls) > 1:
            return None, "a tab whose aria-controls names several elements"
        panel = None
        if controls:
            if controls[0] in duplicates:
                return None, f"a tab whose aria-controls names a duplicated id ({controls[0]})"
            panel = by_id.get(controls[0])
            if panel is None:
                return None, f"a tab whose aria-controls names no element ({controls[0]})"
        tab_id = tab.get("id")
        if tab_id and tab_id not in duplicates:
            named = labelled_by.get(tab_id, [])
            if len(named) > 1:
                return None, f"several elements labelled by one tab ({tab_id})"
            if named:
                if panel is not None and named[0] is not panel:
                    return None, f"a tab whose aria-controls and its panel's aria-labelledby disagree ({tab_id})"
                panel = named[0]
        if panel is None:
            return None, "a tab with no aria-controls and no panel labelled by it"
        if id(panel) in used:
            return None, "two tabs naming one panel"
        if is_ancestor(panel, tab) or is_ancestor(tab, panel):
            return None, "a tab panel that contains its own tab"
        used.add(id(panel))
        text = label_text(tab)
        if not text:
            return None, "a tab with no label text"
        pairs.append((text, panel, tab))
    return TabSet("aria-ids", tablist, pairs), None


def find_tab_sets(root):
    """(recognised tab sets, problems). A problem is an ambiguity: the page is not converted on the
    structural route, and the check does not run on it."""
    elements = list(iter_elements(root, MARKER_SKIP))
    by_id, duplicates = {}, set()
    labelled_by = collections.defaultdict(list)
    for node in elements:
        ident = node.get("id")
        if ident:
            if ident in by_id:
                duplicates.add(ident)
            else:
                by_id[ident] = node
        for ref in tokens(node, "aria-labelledby"):
            labelled_by[ref].append(node)
    sets, problems = [], []
    for node in elements:
        if "tabbed-set" in tokens(node, "class"):
            found, why = _mkdocs_set(node)
        elif "tablist" in tokens(node, "role"):
            found, why = _aria_set(node, by_id, duplicates, labelled_by)
        else:
            continue
        if found:
            sets.append(found)
        else:
            problems.append(f"{why} {describe(node)}")
    claimed = collections.Counter(id(p) for s in sets for _, p, _ in s.pairs)
    if any(n > 1 for n in claimed.values()):
        problems.append("one panel claimed by two tab sets")
    roots = [s.root for s in sets if s.kind.startswith("mkdocs")]
    for node in elements:
        classes = tokens(node, "class")
        stray_panel = "tabpanel" in tokens(node, "role") and id(node) not in claimed
        stray_mkdocs = (("tabbed-content" in classes or "tabbed-block" in classes)
                        and not any(is_ancestor(r, node) for r in roots))
        if (stray_panel or stray_mkdocs) and has_word(text_of(node)):
            problems.append(("a tab panel that no recognised tab labels " if stray_panel
                             else "mkdocs tab content outside a recognised tabbed set ") + describe(node))
    return sets, problems


# ---------------------------------------------------------------- what the capture must hold
class Token:
    __slots__ = ("kind", "text", "norm", "pair", "chain", "container")

    def __init__(self, kind, text, pair=None, chain=(), container=None):
        self.kind, self.text, self.pair, self.chain, self.container = kind, text, pair, chain, container
        self.norm = norm_text(text)


def expected_tokens(root, sets):
    """From the ORIGINAL document: (collapsed units outside every tab panel, the ordered tokens of
    the tab pairs, each label followed by its own panel's units, nested sets unrolled in place).
    A unit is a maximal run of text between block boundaries; it counts as collapsed when any of
    its text sits under a marker, and it belongs to the outermost marked element above that text
    (its container, whose units the capture must keep in their order). A unit counts whenever its
    comparison form keeps anything: a cell holding only a symbol, a check mark or a dash, is a
    value. Label nodes are left out of units: each label is its own token."""
    label_nodes = {id(lab) for s in sets for _, _, lab in s.pairs}
    panels = {}
    for s in sets:
        for text, panel, _lab in s.pairs:
            panels[id(panel)] = (len(panels), text)
    controllers = controllers_by_target(root)
    collapsed, paired = [], []
    buf, state = [], {"risk": False, "container": None, "next": 0}
    ctx = [(False, (), None)]                # (under a marker, chain of enclosing panel ids, container)

    def flush():
        if not buf:
            return
        text = squash("".join(buf))
        buf.clear()
        risk, state["risk"] = state["risk"], False
        container, state["container"] = state["container"], None
        chain = ctx[-1][1]
        tok = Token("unit", text, chain=chain, container=container)
        if not tok.norm:
            return
        if chain:
            paired.append(tok)
        elif risk:
            collapsed.append(tok)

    stack = [(root, False, False)]
    while stack:
        node, leaving, pushed = stack.pop()
        if leaving:
            if node.tag in BLOCK or id(node) in panels:
                flush()
            if pushed:
                ctx.pop()
            continue
        if node.tag == "#text":
            buf.append(node.data)
            if ctx[-1][0]:
                state["risk"] = True
                if state["container"] is None:
                    state["container"] = ctx[-1][2]
            continue
        if not (node.is_element or node.tag == "#root"):
            continue
        if node.tag in EXCLUDED or id(node) in label_nodes or node.tag == "br":
            flush()
            continue
        panel = panels.get(id(node))
        if node.tag in BLOCK or panel:
            flush()
        risk, chain, container = ctx[-1]
        if panel:
            paired.append(Token("label", panel[1], pair=panel[0], chain=chain))
            ctx.append((True, chain + (panel[0],), container))
            pushed = True
        elif node.is_element and own_markers(node, controllers):
            if container is None:
                state["next"] += 1
                container = state["next"]
            ctx.append((True, chain, container))
            pushed = True
        stack.append((node, True, pushed))
        stack.extend((c, False, False) for c in reversed(node.children))
    flush()
    return collapsed, paired


# ---------------------------------------------------------------- reading the capture
IMG_MD = re.compile(r"!\[(?:\\.|[^\]\\\n])*\]\((?:[^()\n]|\([^()\n]*\))*\)")
LINK_MD = re.compile(r"\[((?:\\.|[^\]\\\n])*)\]\((?:[^()\n]|\([^()\n]*\))*\)")
REF_LINK = re.compile(r"\[((?:\\.|[^\]\\\n])*)\]\[[^\]\n]*\]")
REF_DEF = re.compile(r"(?m)^[ ]{0,3}\[[^\]\n]+\]:[ \t]*\S.*$")
AUTOLINK = re.compile(r"(?<!\\)<((?:https?|mailto):[^>\s]+)>")
HTML_TAG = re.compile(r"(?<!\\)</?([A-Za-z][A-Za-z0-9]*)\b[^>\n]*>")   # an escaped \< is text, never a tag
MD_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
# Markdown's own punctuation, and the quotes markitdown sets round <q>, set aside on both sides of the
# comparison. The signs < and > are NOT here: an inequality is part of a value ("< 101" is not "> 101"),
# and the Markdown that writes a > of its own is undone in capture_text instead.
STRIP_CHARS = re.compile(r"[*_`~|#\[\]\\\"]")
# A table's delimiter row, or a thematic break: syntax only, so a cell holding a dash cannot be matched
# against it.
TABLE_DELIMITER = re.compile(r"(?m)^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(?:\|[ \t]*:?-{3,}:?[ \t]*)*\|?[ \t]*$")
QUOTE_MARK = re.compile(r"^[ ]{0,3}>[ ]?")


def drop_format(text):
    """Text without its Unicode format characters (soft hyphens, zero-width and direction marks):
    invisible, and kept or dropped by converters at will."""
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def norm_text(text):
    """The comparison form of a text, applied alike to the page's units and to the capture:
    compatibility-normalised, format characters and Markdown punctuation removed, whitespace
    collapsed, case-folded. Symbols and the signs < and > stay: they carry values."""
    text = drop_format(unicodedata.normalize("NFKC", text))
    return squash(STRIP_CHARS.sub("", text)).casefold()


def unquote_continuations(markdown):
    """Each line that continues a blockquote (the line before it also opens with >) loses one quote
    marker, so a quoted unit that runs over several lines reads as one. The first line keeps its
    marker: neither converter escapes a page's own leading > (measured on markitdown 0.1.8; defuddle
    0.19.4 writes \\>), and a stray marker before a unit cannot hide it from a substring search."""
    out, quoted = [], False
    for line in markdown.split("\n"):
        m = QUOTE_MARK.match(line)
        out.append(line[m.end():] if m and quoted else line)
        quoted = m is not None
    return "\n".join(out)


def capture_text(markdown):
    """The capture's prose in comparison form: table delimiter rows dropped, blockquote
    continuations unquoted, images dropped, links reduced to their text, inline HTML tags removed
    (a block tag leaves a space), Markdown escapes undone."""
    text = TABLE_DELIMITER.sub(" ", unquote_continuations(markdown))
    text = IMG_MD.sub(" ", text)
    text = LINK_MD.sub(lambda m: m.group(1), text)
    text = REF_LINK.sub(lambda m: m.group(1), text)
    text = REF_DEF.sub(" ", text)
    text = AUTOLINK.sub(lambda m: m.group(1), text)
    text = HTML_TAG.sub(lambda m: " " if m.group(1).lower() in BLOCK else "", text)
    text = MD_ESCAPE.sub(lambda m: m.group(1), text)
    return norm_text(text)


def find_free(hay, needle, start):
    """First index at or after start where needle occurs with no letter or digit glued to an end
    that is itself a letter or digit; -1 when there is none."""
    if not needle:
        return -1
    i = hay.find(needle, start)
    while i != -1:
        end = i + len(needle)
        glued_before = i > 0 and hay[i - 1].isalnum() and needle[0].isalnum()
        glued_after = end < len(hay) and hay[end].isalnum() and needle[-1].isalnum()
        if not glued_before and not glued_after:
            return i
        i = hay.find(needle, i + 1)
    return -1


def _core(text):
    i = 0
    while i < len(text) and not text[i].isalnum():
        i += 1
    return text[i:]


LIST_NUMBER = re.compile(r"\d{1,9}[.)](?![^\W_])")


def _starts_after(hay, j):
    """Where the next expected text may begin after position j: past punctuation and spacing, and
    also past one ordered-list number (the converter numbers ordered lists; the page's text does not)."""
    while j < len(hay) and not hay[j].isalnum():
        j += 1
    yield j
    m = LIST_NUMBER.match(hay, j)
    if m:
        k = m.end()
        while k < len(hay) and not hay[k].isalnum():
            k += 1
        yield k


def locate_label(hay, label, nxt, start):
    """The first occurrence of label at or after start that the next expected token follows with
    nothing but punctuation, spacing or a list number between (nxt None: the panel is empty)."""
    pos = find_free(hay, label.norm, start)
    core = _core(nxt.norm) if nxt is not None else ""
    while pos != -1:
        if not core:
            return pos
        for j in _starts_after(hay, pos + len(label.norm)):
            end = j + len(core)
            if hay.startswith(core, j) and not (end < len(hay) and hay[end].isalnum() and core[-1].isalnum()):
                return pos
        pos = find_free(hay, label.norm, pos + 1)
    return -1


LINK_DEST = re.compile(
    r"(!?)\[(?:\\.|[^\]\\\n])*\]\(\s*(<[^>\n]*>|(?:[^()\s]|\([^()\s]*\))+)"
    r"(?:\s+(?:\"[^\"\n]*\"|'[^'\n]*'|\([^)\n]*\)))?\s*\)")
REF_DEST = re.compile(r"(?m)^[ ]{0,3}\[[^\]\n]+\]:[ \t]*(<[^>\n]*>|\S+)")
CODE_FENCE = re.compile(r"(?ms)^[ ]{0,3}(`{3,}|~{3,})[^\n]*\n.*?^[ ]{0,3}\1[ \t]*$")
CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1", re.S)
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
# An image the capturer has downloaded into the vault's assets folder is deliberately relative.
ASSET_IMAGE = re.compile(r"^(?:\.\./)*assets/")


def relative_destinations(markdown):
    """(relative link or image destinations outside code, number of destinations seen)."""
    text = CODE_SPAN.sub(" ", CODE_FENCE.sub(" ", markdown))
    found, seen = [], 0
    candidates = [(m.group(1) == "!", m.group(2)) for m in LINK_DEST.finditer(text)]
    candidates += [(False, m.group(1)) for m in REF_DEST.finditer(text)]
    for is_image, dest in candidates:
        dest = dest.strip().strip("<>").strip()
        seen += 1
        if not dest or dest.startswith("#") or SCHEME.match(dest):
            continue
        if is_image and ASSET_IMAGE.match(dest):
            continue
        found.append(dest)
    return found, seen


# ---------------------------------------------------------------- the validation
def check_capture(page_text, base_url, markdown):
    """Check a capture against the fetched ORIGINAL page (parsed afresh here; never the normalised
    copy). Returns a report whose `failures` list names each finding (empty when the unit check found
    none) and whose `ambiguous` list names the tab structures it could not pair (then it compares
    nothing else, and its verdict is not run)."""
    root = parse_html(page_text)
    markers = find_markers(root)
    report = {"route": "ROUTE" if markers else "NOT-ROUTED", "markers": dict(markers),
              "failures": [], "ambiguous": [], "collapsed": 0, "sets": 0, "labels": 0, "pairing": {},
              "links": 0, "base_url": base_url}
    sets, problems = find_tab_sets(root)
    if problems:
        report["ambiguous"] = problems[:SHOW_MAX]
        report["failures"].append("ambiguous tab pairing: " + "; ".join(problems[:SHOW_MAX]))
        return report
    report["sets"] = len(sets)
    report["pairing"] = dict(collections.Counter(s.kind for s in sets))
    collapsed, paired = expected_tokens(root, sets)
    hay = capture_text(markdown)
    report["collapsed"] = len(collapsed)
    report["labels"] = sum(1 for tok in paired if tok.kind == "label")   # the page's labels, whatever the capture holds
    missing, disordered = [], []
    containers = collections.OrderedDict()
    for t in collapsed:
        containers.setdefault(t.container, []).append(t)
    for units in containers.values():        # each container's units in their own order
        cursor = 0
        for t in units:
            pos = find_free(hay, t.norm, cursor)
            if pos >= 0:
                cursor = pos + len(t.norm)
            elif find_free(hay, t.norm, 0) >= 0:
                disordered.append(t)
            else:
                missing.append(t)
    for found, what in ((missing, "collapsed text missing from the capture"),
                        (disordered, "collapsed text out of its order within its block (a value moved, "
                                     "swapped or reversed)")):
        if found:
            named = "; ".join('"' + clip(t.text, 80) + '"' for t in found[:SHOW_MAX])
            more = f" (+{len(found) - SHOW_MAX} more)" if len(found) > SHOW_MAX else ""
            report["failures"].append(f"{what}: {named}{more}")
    cursor, current = 0, ""
    for k, tok in enumerate(paired):
        if tok.kind == "label":
            current = tok.text
            nxt = paired[k + 1] if k + 1 < len(paired) and tok.pair in paired[k + 1].chain else None
            pos = locate_label(hay, tok, nxt, cursor)
            if pos < 0:
                opens = f' (its panel opens with "{clip(nxt.text, 60)}")' if nxt is not None else ""
                report["failures"].append(f'tab label "{clip(tok.text, 80)}" is not directly before '
                                          f"its own panel, after the previous one{opens}")
                break
            cursor = pos + len(tok.norm)
        else:
            pos = find_free(hay, tok.norm, cursor)
            if pos < 0:
                report["failures"].append(f'panel content missing or out of order under tab "{clip(current, 80)}": '
                                          f'"{clip(tok.text, 80)}"')
                break
            cursor = pos + len(tok.norm)
    relative, seen = relative_destinations(markdown)
    report["links"] = seen
    if relative:
        more = f" (+{len(relative) - SHOW_MAX} more)" if len(relative) > SHOW_MAX else ""
        report["failures"].append("relative link destination survived conversion: "
                                  + ", ".join(clip(d, 100) for d in relative[:SHOW_MAX]) + more)
    return report


def check_line(report):
    kinds = ", ".join(f"{k} ×{v}" for k, v in sorted(report["pairing"].items())) or "none"
    return (f"collapsed units {report['collapsed']} · tab sets {report['sets']} ({kinds}) · "
            f"labels {report['labels']} · link destinations {report['links']}")


def verdict_of(report):
    """The check's verdict on a check_capture report: not run when it could not pair the tabs."""
    if report.get("ambiguous"):
        return VERDICT_NOT_RUN
    return VERDICT_LOSS if report["failures"] else VERDICT_NONE


def not_run(why):
    """The stamp of a check that did not run, with the reason it did not."""
    return stamp_value(f"{VERDICT_NOT_RUN} — {why}")


def stamp_of(report):
    """The one-line stamp for a check_capture report. A check that ran names its counts and what it
    does not compare (CHECK_LIMITS), so its stamp is never read as a statement that nothing was lost."""
    if report.get("ambiguous"):
        return not_run("the check cannot pair the page's tab labels with their panels: ambiguous tab pairing: "
                       + "; ".join(report["ambiguous"]))
    counts = (f"collapsed units {report['collapsed']} · tab labels {report['labels']} · "
              f"link destinations {report['links']}")
    if report["failures"]:
        found = clip("; ".join(report["failures"]), FINDINGS_MAX)
        return stamp_value(f"{VERDICT_LOSS} — {found} ({counts}); {CHECK_LIMITS}")
    return stamp_value(f"{VERDICT_NONE} by the unit check ({counts}); {CHECK_LIMITS}")


# ---------------------------------------------------------------- link destinations and charset
# URL attributes made absolute, the lazy-image ones defuddle promotes included.
URL_ATTRS = ("href", "src", "poster", "cite", "action", "formaction", "data-src", "data-original", "data-lazy-src")
SRCSET_ATTRS = ("srcset", "data-srcset")
SAFE_ATTR = re.compile(r"^[^\s\"'<>/=\x00-\x1f]+$")
META_UTF8 = '<meta charset="utf-8">'


def absolutise(value, base):
    v = value.strip()
    if not v or v.startswith("#") or SCHEME.match(v):
        return value
    try:
        return urljoin(base, v)
    except ValueError:
        return value


def absolutise_srcset(value, base):
    """Each candidate's URL made absolute, its descriptor kept (the HTML standard's split: a URL is a
    run of non-space characters, trailing commas end it, a descriptor runs to the next comma)."""
    out, i, n = [], 0, len(value)
    while i < n:
        while i < n and (value[i].isspace() or value[i] == ","):
            i += 1
        if i >= n:
            break
        j = i
        while j < n and not value[j].isspace():
            j += 1
        url = value[i:j]
        if url.endswith(","):
            out.append(absolutise(url.rstrip(","), base))
            i = j
            continue
        k = j
        while k < n and value[k] != ",":
            k += 1
        desc = value[j:k].strip()
        out.append(absolutise(url, base) + (" " + desc if desc else ""))
        i = k + 1
    return ", ".join(out)


def document_base(effective_url, root):
    """The base every relative reference resolves against: the first <base href>, itself resolved
    against the URL the fetch ended at, else that URL."""
    for node in iter_elements(root, frozenset(("template",))):
        if node.tag == "base" and node.get("href"):
            candidate = urljoin(effective_url, node.get("href").strip())
            if urlsplit(candidate).scheme in ("http", "https"):
                return candidate
            break
    return effective_url


META_CHARSET = re.compile(rb"""<meta[^>]+?charset\s*=\s*["']?\s*([A-Za-z0-9_.:\-]+)""", re.I)


def decode_html(data, content_type=""):
    if data[:3] == b"\xef\xbb\xbf":
        return data[3:].decode("utf-8", "replace")
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", "replace")
    m = re.search(r"charset\s*=\s*[\"']?([A-Za-z0-9_.:\-]+)", content_type or "", re.I)
    charset = m.group(1) if m else None
    if not charset:
        m = META_CHARSET.search(data[:SNIFF_BYTES])
        charset = m.group(1).decode("ascii", "replace") if m else "utf-8"
    charset = charset.lower()
    if charset in ("iso-8859-1", "latin1", "latin-1", "us-ascii", "ascii"):
        charset = "cp1252"                    # as the HTML standard reads those labels
    try:
        codecs.lookup(charset)
    except LookupError:
        charset = "utf-8"
    return data.decode(charset, "replace")


def _charset_meta(attrs):
    d = dict(attrs)
    return "charset" in d or (d.get("http-equiv") or "").strip().lower() == "content-type"


def _attr_text(name, value):
    return " " + name if value is None else ' %s="%s"' % (name, html_lib.escape(value, quote=True))


class _Rewriter(HTMLParser):
    """NOT-ROUTED preparation: the fetched markup token for token, with each URL attribute made
    absolute and the charset declared as UTF-8 (the copy is written in UTF-8); nothing else moves,
    so the extractor reads the page's own structure."""

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.out, self.raw, self.meta_done = base, [], None, False

    def _start(self, tag, attrs, close):
        if tag == "meta" and _charset_meta(attrs):
            return
        kept, changed = [], False
        for name, value in attrs:
            new = value
            if value is not None and name in URL_ATTRS:
                new = absolutise(value, self.base)
            elif value is not None and name in SRCSET_ATTRS:
                new = absolutise_srcset(value, self.base)
            changed = changed or new != value
            kept.append((name, new))
        if changed:
            text = "<%s%s%s>" % (tag, "".join(_attr_text(k, v) for k, v in kept if SAFE_ATTR.match(k)),
                                 " /" if close else "")
        else:
            text = self.get_starttag_text()
        self.out.append(text)
        if tag in RAW_TEXT and not close:
            self.raw = tag
        if tag == "head" and not self.meta_done:
            self.out.append(META_UTF8)
            self.meta_done = True

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, True)

    def handle_endtag(self, tag):
        if tag == self.raw:
            self.raw = None
        self.out.append("</%s>" % tag)

    def handle_data(self, data):
        self.out.append(data if self.raw else html_lib.escape(data, quote=False))

    def handle_comment(self, data):
        self.out.append("<!--%s-->" % data)

    def handle_decl(self, decl):
        self.out.append("<!%s>" % decl)

    def handle_pi(self, data):
        self.out.append("<?%s>" % data)

    def unknown_decl(self, data):
        self.out.append("<![%s]>" % data)


def prepare_plain(page_text, base):
    rewriter = _Rewriter(base)
    rewriter.feed(page_text)
    rewriter.close()
    out = rewriter.out
    if not rewriter.meta_done:
        at = 1 if out and out[0].startswith("<!") and not out[0].startswith("<!--") else 0
        out.insert(at, META_UTF8)
    return "".join(out)


def serialise(root):
    out, stack = [], [(root, False)]
    while stack:
        node, closing = stack.pop()
        if closing:
            out.append("</%s>" % node.tag)
            continue
        tag = node.tag
        if tag == "#text":
            parent = node.parent.tag if node.parent is not None else ""
            out.append(node.data if parent in RAW_TEXT else html_lib.escape(node.data, quote=False))
        elif tag == "#comment":
            out.append("<!--%s-->" % node.data)
        elif tag == "#decl":
            out.append("<!%s>" % node.data)
        elif tag == "#root":
            stack.extend((c, False) for c in reversed(node.children))
        else:
            attrs = "".join(_attr_text(k, v) for k, v in node.attrs.items() if SAFE_ATTR.match(k))
            out.append("<%s%s>" % (tag, attrs))
            if tag not in VOID:
                stack.append((node, True))
                stack.extend((c, False) for c in reversed(node.children))
    return "".join(out)


def _insert(parent, index, child):
    child.parent = parent
    parent.children.insert(index, child)


def _summary_to_bold(summary):
    """A summary holding only inline content becomes a paragraph of bold text; one holding a block
    (a heading, say) becomes a plain block. Either way it ends before the body starts."""
    if any(n.tag in BLOCK for n in iter_elements(summary)):
        summary.tag = "div"
        return
    summary.tag = "p"
    strong = Node("strong")
    for kid in summary.children:
        strong.append(kid)
    summary.children = []
    summary.append(strong)


def normalise(root, sets, base):
    """ROUTE preparation, in place: every URL attribute absolute against base; the charset declared
    as UTF-8; each tab label a heading placed directly before its own panel (h4, one level deeper
    per enclosing panel, h6 at most; set by judgement) and the label nodes removed; each details
    element a block whose summary ends before the body. Returns the serialised copy."""
    for node in iter_elements(root):
        for name in URL_ATTRS:
            if node.attrs.get(name):
                node.attrs[name] = absolutise(node.attrs[name], base)
        for name in SRCSET_ATTRS:
            if node.attrs.get(name):
                node.attrs[name] = absolutise_srcset(node.attrs[name], base)
    for node in [n for n in iter_elements(root) if n.tag == "meta" and _charset_meta(n.attrs.items())]:
        node.parent.children.remove(node)
    head = next((n for n in iter_elements(root) if n.tag == "head"), None)
    if head is not None:
        _insert(head, 0, Node("meta", {"charset": "utf-8"}))
    else:
        at = 0
        while at < len(root.children) and root.children[at].tag == "#decl":
            at += 1
        _insert(root, at, Node("meta", {"charset": "utf-8"}))
    panel_ids = {id(p) for s in sets for _, p, _ in s.pairs}
    for s in sets:
        for text, panel, _lab in s.pairs:
            depth = sum(1 for anc in ancestors(panel) if id(anc) in panel_ids)
            heading = Node("h%d" % min(6, 4 + depth))
            heading.append(Node("#text", data=text))
            parent = panel.parent
            _insert(parent, parent.children.index(panel), heading)
    for s in sets:
        for _text, _panel, lab in s.pairs:
            if lab.parent is not None and lab in lab.parent.children:
                lab.parent.children.remove(lab)
    for node in [n for n in iter_elements(root) if n.tag == "details"]:
        node.tag = "div"
        node.attrs.pop("open", None)
        for kid in node.children:
            if kid.is_element and kid.tag == "summary":
                _summary_to_bold(kid)
    return serialise(root)


# ---------------------------------------------------------------- built-in controls
CONTROL_COLLAPSED_PAGE = (
    '<!DOCTYPE html><html><head><title>Control</title></head><body><article><h1>Control page</h1>'
    '<p>Visible control prose.</p><details><summary>Control terms</summary>'
    '<p>Planted collapsed control sentence.</p></details></article></body></html>')
CONTROL_TABS_PAGE = (
    '<!DOCTYPE html><html><body><article><h1>Control limits</h1>'
    '<div class="tabbed-set tabbed-alternate" data-tabs="1:2">'
    '<input checked="checked" id="__tabbed_1_1" name="__tabbed_1" type="radio">'
    '<input id="__tabbed_1_2" name="__tabbed_1" type="radio">'
    '<div class="tabbed-labels"><label for="__tabbed_1_1">Control system one</label>'
    '<label for="__tabbed_1_2">Control system two</label></div><div class="tabbed-content">'
    '<div class="tabbed-block"><table><tr><th>Item</th><th>Value</th></tr><tr><td>alpha</td><td>101</td></tr></table></div>'
    '<div class="tabbed-block"><table><tr><th>Item</th><th>Value</th></tr><tr><td>beta</td><td>202</td></tr></table></div>'
    '</div></div></article></body></html>')
CONTROL_PLAIN_PAGE = (
    '<!DOCTYPE html><html><body><article><h1>Control article</h1>'
    '<p>Plain control prose with nothing collapsed.</p><button aria-controls="control-results">Sort</button>'
    '<div id="control-results">Visible control results.</div></article></body></html>')
CONTROL_TABS_GOOD = ("# Control limits\n\n#### Control system one\n\n| Item | Value |\n| --- | --- |\n| alpha | 101 |\n\n"
                     "#### Control system two\n\n| Item | Value |\n| --- | --- |\n| beta | 202 |\n")
CONTROL_TABS_SWAPPED = ("# Control limits\n\n#### Control system one\n\n| Item | Value |\n| --- | --- |\n| beta | 202 |\n\n"
                        "#### Control system two\n\n| Item | Value |\n| --- | --- |\n| alpha | 101 |\n")
CONTROL_COLLAPSED_GOOD = "# Control page\n\nVisible control prose.\n\n**Control terms**\n\nPlanted collapsed control sentence.\n"
CONTROL_COLLAPSED_LOST = "# Control page\n\nVisible control prose.\n\n**Control terms**\n"
CONTROL_RELATIVE = CONTROL_COLLAPSED_GOOD + "\nSee [the terms](terms).\n"
# Symbol-only cells and inequality signs are values: a capture that reverses the marks or flips a sign
# must give a finding, the table as converted none (markitdown 0.1.8 writes the table below for this page).
CONTROL_SYMBOLS_PAGE = (
    '<!DOCTYPE html><html><body><article><h1>Control values</h1><details><summary>Control allowances</summary>'
    '<table><tr><th>Item</th><th>Allowed</th><th>Limit</th></tr>'
    '<tr><td>alpha</td><td>✓</td><td>&lt; 101</td></tr><tr><td>beta</td><td>✗</td><td>&gt; 202</td></tr>'
    '</table></details></article></body></html>')
CONTROL_SYMBOLS_GOOD = ("# Control values\n\n**Control allowances**\n\n| Item | Allowed | Limit |\n| --- | --- | --- |\n"
                        "| alpha | ✓ | < 101 |\n| beta | ✗ | > 202 |\n")
CONTROL_SYMBOLS_REVERSED = CONTROL_SYMBOLS_GOOD.replace("✓", "\x00").replace("✗", "✓").replace("\x00", "✗")
CONTROL_SYMBOLS_FLIPPED = CONTROL_SYMBOLS_GOOD.replace("< 101", "> 101")
# A Webflow dropdown holds page content outside a navbar and the site's menu inside one, so one marker
# has to tell the two apart: the first control routes on the panel, the second holds the menu alone.
CONTROL_NAVBAR = ('<div class="w-nav"><nav class="w-nav-menu"><div class="w-dropdown"><div class="w-dropdown-toggle">Control menu</div>'
                  '<nav class="w-dropdown-list"><a href="/control/">Control link</a></nav></div></nav></div>')
CONTROL_DROPDOWN_PAGE = (
    '<!DOCTYPE html><html><body>' + CONTROL_NAVBAR + '<article><h1>Control questions</h1>'
    '<div class="w-dropdown"><div class="w-dropdown-toggle">Control question</div>'
    '<nav class="w-dropdown-list"><p>Planted dropdown control answer.</p></nav></div></article></body></html>')
CONTROL_NAVBAR_PAGE = ('<!DOCTYPE html><html><body>' + CONTROL_NAVBAR + '<article><h1>Control article</h1>'
                       '<p>Plain control prose under a site menu.</p></article></body></html>')
CONTROL_DROPDOWN_GOOD = "# Control questions\n\nControl question\n\nPlanted dropdown control answer.\n"
CONTROL_DROPDOWN_LOST = "# Control questions\n\nControl question\n"
CONTROL_BASE = "https://control.invalid/page/"


def run_controls(route=True, check=True):
    """(passed, total, names of the failed controls), checked in process on every run."""
    passed, failed = 0, []

    def expect(name, condition):
        nonlocal passed
        if condition:
            passed += 1
        else:
            failed.append(name)
    if route:
        expect("a planted details block routes", "details" in find_markers(parse_html(CONTROL_COLLAPSED_PAGE)))
        expect("a planted mkdocs set routes", "mkdocs tabbed-set" in find_markers(parse_html(CONTROL_TABS_PAGE)))
        expect("a planted plain article does not route", not find_markers(parse_html(CONTROL_PLAIN_PAGE)))
        expect("a planted Webflow dropdown routes, its navbar menu not counted",
               find_markers(parse_html(CONTROL_DROPDOWN_PAGE)) == {"class w-dropdown-list": 1})
        expect("a planted Webflow navbar menu alone does not route", not find_markers(parse_html(CONTROL_NAVBAR_PAGE)))
    if check:
        expect("the planted collapsed capture as converted gives no finding",
               not check_capture(CONTROL_COLLAPSED_PAGE, CONTROL_BASE, CONTROL_COLLAPSED_GOOD)["failures"])
        expect("the planted capture without its sentence gives a finding",
               bool(check_capture(CONTROL_COLLAPSED_PAGE, CONTROL_BASE, CONTROL_COLLAPSED_LOST)["failures"]))
        expect("the planted tab capture, each label before its own table, gives no finding",
               not check_capture(CONTROL_TABS_PAGE, CONTROL_BASE, CONTROL_TABS_GOOD)["failures"])
        expect("swapped tables under the labels give a finding",
               bool(check_capture(CONTROL_TABS_PAGE, CONTROL_BASE, CONTROL_TABS_SWAPPED)["failures"]))
        expect("a surviving relative link gives a finding",
               bool(check_capture(CONTROL_COLLAPSED_PAGE, CONTROL_BASE, CONTROL_RELATIVE)["failures"]))
        expect("the planted table of check marks and inequalities as converted gives no finding",
               not check_capture(CONTROL_SYMBOLS_PAGE, CONTROL_BASE, CONTROL_SYMBOLS_GOOD)["failures"])
        expect("reversed check-mark cells give a finding",
               bool(check_capture(CONTROL_SYMBOLS_PAGE, CONTROL_BASE, CONTROL_SYMBOLS_REVERSED)["failures"]))
        expect("a flipped inequality gives a finding",
               bool(check_capture(CONTROL_SYMBOLS_PAGE, CONTROL_BASE, CONTROL_SYMBOLS_FLIPPED)["failures"]))
        expect("the planted dropdown capture as converted gives no finding",
               not check_capture(CONTROL_DROPDOWN_PAGE, CONTROL_BASE, CONTROL_DROPDOWN_GOOD)["failures"])
        expect("the planted dropdown capture without its answer gives a finding",
               bool(check_capture(CONTROL_DROPDOWN_PAGE, CONTROL_BASE, CONTROL_DROPDOWN_LOST)["failures"]))
    return passed, passed + len(failed), failed


def require_controls(route=True, check=True):
    passed, total, failed = run_controls(route, check)
    if failed:
        raise ProbeFailure("controls", "built-in controls failed: " + "; ".join(failed))
    return f"{passed}/{total}"


# ---------------------------------------------------------------- fetch and convert
URL_OK = re.compile(r"^https?://\S+$")


def in_lane():
    """A lane's network rules apply: the wrapper set LLM_WIKI_LANE and this is not the head role."""
    return bool(os.environ.get(LANE_VAR)) and (os.environ.get("LLM_WIKI_FENCE_ROLE") or "").strip() != "head"


def writes_restricted():
    """As sanitise.py reads it: the fence sets LLM_WIKI_LANE_WRITES for every lane (empty when read-only)."""
    return WRITES_VAR in os.environ or in_lane()


def lane_hosts():
    return [h.strip().lower() for h in re.split(r"[,\s]+", os.environ.get(NETWORK_VAR) or "") if h.strip()]


def host_granted(host, grant):
    host = (host or "").strip().lower()
    return any(host == g or host.endswith("." + g) for g in grant)


def lane_write_roots():
    roots = [os.path.realpath(p) for p in (os.environ.get(WRITES_VAR) or "").split(os.pathsep) if p.strip()]
    return roots + [os.path.abspath("/tmp"), os.path.realpath("/tmp")]


def within(path, roots):
    path = os.path.realpath(path)
    return any(path == r or path.startswith(r.rstrip(os.sep) + os.sep) for r in roots)


def require_lane_write(path, what):
    if writes_restricted() and not within(path, lane_write_roots()):
        raise ProbeFailure("start", f"{what} {path} lies outside the lane's write grants ({WRITES_VAR} or /tmp)")


def run_fetch(url, page_path, curl, user_agent=None, follow=True):
    """Run curl once; return what it reported, its exit status always included. follow=False (a lane)
    returns a redirect as it is, its target named, rather than following it."""
    host = (urlsplit(url).hostname or "").lower()
    bot = any(host == h or host.endswith("." + h) for h in BOT_UA_HOSTS)
    agent = user_agent or (DEFUDDLE_UA + " bot" if bot else DEFUDDLE_UA)
    argv = [curl, "-sS"] + (["-L", "--max-redirs", str(CURL_MAX_REDIRS)] if follow else []) + [
        "--max-time", str(CURL_MAX_TIME), "--compressed", "-A", agent, "-H", "Accept: " + ACCEPT,
        "-o", page_path, "-w", CURL_FORMAT, url]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=CURL_MAX_TIME + 30)
    except FileNotFoundError:
        raise ProbeFailure("fetch", f"curl not found ({curl})")
    except subprocess.TimeoutExpired:
        raise ProbeFailure("fetch", f"curl did not return within {CURL_MAX_TIME + 30} s")
    fetch = {"curl_exit": proc.returncode, "curl_stderr": clip(proc.stderr or "", 200)}
    meta = None
    for line in (proc.stdout or "").splitlines():
        if line.startswith(META_SENTINEL + " "):
            meta = line[len(META_SENTINEL) + 1:]
    fields = meta.split("\t") if meta is not None else []
    if len(fields) >= 4:
        code, content_type, effective, redirects = fields[:4]
        fetch.update(http_code=int(code) if code.strip().isdigit() else code.strip(),
                     content_type=content_type.strip(), effective_url=effective.strip(),
                     redirects=int(redirects) if redirects.strip().isdigit() else None,
                     redirect_url=fields[4].strip() if len(fields) > 4 else "")
    return fetch


def judge_fetch(fetch, page_path, need_effective=True):
    """Raise ProbeFailure unless the fetch is a successful HTML response with a body."""
    code, rc = fetch.get("http_code"), fetch.get("curl_exit")
    if "http_code" not in fetch:
        raise ProbeFailure("fetch", f"curl reported no response metadata (exit {rc}): "
                                    f"{fetch.get('curl_stderr') or 'no message'}")
    if rc != 0:
        raise ProbeFailure("fetch", f"curl exit {rc} under HTTP {code}: the transfer failed whatever the status "
                                    f"line said ({fetch.get('curl_stderr') or 'no message'})")
    if isinstance(code, int) and 300 <= code <= 399 and fetch.get("redirect_url"):
        raise ProbeFailure("fetch", f"HTTP {code}: a redirect to {fetch['redirect_url']}, not followed in a lane "
                                    "(it could leave the network grant); probe that URL if the grant names its host")
    if not (isinstance(code, int) and 200 <= code <= 299):
        raise ProbeFailure("fetch", f"HTTP {code}: an error response is never the page, however substantial its body")
    media = (fetch.get("content_type") or "").split(";")[0].strip().lower()
    if media not in HTML_TYPES:
        raise ProbeFailure("fetch", f"content type '{fetch.get('content_type') or 'none'}' is not HTML")
    if need_effective and urlsplit(fetch.get("effective_url") or "").scheme not in ("http", "https"):
        raise ProbeFailure("fetch", f"no http(s) effective URL ({fetch.get('effective_url') or 'none'})")
    if not os.path.isfile(page_path) or os.path.getsize(page_path) == 0:
        raise ProbeFailure("fetch", "the fetched page is missing or empty")


def run_converter(route, source, python, defuddle):
    if route == "ROUTE":
        argv, name = [python, "-B", "-m", "markitdown", source], "markitdown"
    else:
        argv, name = [defuddle, "parse", source, "--markdown"], "defuddle"
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=CONVERT_TIMEOUT)
    except FileNotFoundError:
        raise ProbeFailure("convert", f"{name} not found ({argv[0]})")
    except subprocess.TimeoutExpired:
        raise ProbeFailure("convert", f"{name} did not return within {CONVERT_TIMEOUT} s")
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise ProbeFailure("convert", f"{name} exited {proc.returncode}: {err[-1] if err else 'no message'}")
    out = proc.stdout.decode("utf-8", "replace")
    if not out.strip():
        raise ProbeFailure("convert", f"{name} printed nothing")
    return argv, out


# ---------------------------------------------------------------- the only writes this script makes
def vault_above(path):
    """The nearest directory at or above path that holds both raw/ and wiki/, else None."""
    cur = os.path.realpath(path)
    while True:
        if os.path.isdir(os.path.join(cur, "raw")) and os.path.isdir(os.path.join(cur, "wiki")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def make_work(work):
    work = os.path.abspath(work)
    if os.path.lexists(work) and (not os.path.isdir(work) or os.listdir(work)):
        raise ProbeFailure("start", f"--work {work} must be a new or empty directory")
    vault = vault_above(work)
    if vault:
        raise ProbeFailure("start", f"--work {work} lies inside a vault ({vault}); use a directory outside it")
    require_lane_write(work, "--work")
    os.makedirs(work, mode=0o700, exist_ok=True)
    return work


def write_new(path, text):
    """Create path, which must not exist, holding text in UTF-8."""
    with open(path, "x", encoding="utf-8", newline="") as fh:
        fh.write(text)


def write_result(work, result):
    tmp = os.path.join(work, ".result.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, os.path.join(work, "result.json"))


# ---------------------------------------------------------------- the chain
def _self_sha():
    try:
        with open(os.path.abspath(__file__), "rb") as fh:
            return sha256_bytes(fh.read())
    except OSError:
        return None


CHECK_KEYS = ("collapsed", "sets", "labels", "pairing", "links", "failures", "ambiguous")


def run_capture(url, work, curl="curl", defuddle="defuddle", python=None, user_agent=None, normaliser=None):
    """The whole chain into work; returns (exit code, result). The normaliser parameter exists so the
    suite can plant a faulty one and show the check still finds the loss in its output. What the check
    finds is recorded as its verdict and never fails the chain; a check that raises is recorded as not
    run, and the capture stands."""
    python = python or sys.executable
    normaliser = normaliser or normalise
    result = {"schema": RESULT_SCHEMA, "status": "fail", "stage": "start", "reason": "", "url": url,
              "created": datetime.datetime.now().isoformat(timespec="seconds"), "probe_sha256": _self_sha()}
    own_dir = False
    stage = "start"
    try:
        if not URL_OK.match(url or ""):
            raise ProbeFailure("start", "the URL must be one http(s) URL with no whitespace")
        lane = in_lane()
        if lane and not host_granted(urlsplit(url).hostname, lane_hosts()):
            raise ProbeFailure("start", f"the lane's network grant ({NETWORK_VAR}) does not name "
                                        f"{urlsplit(url).hostname}; nothing was fetched")
        work = make_work(work)
        own_dir = True
        stage = "controls"
        result["controls"] = require_controls()
        stage = "fetch"
        page = os.path.join(work, "page.html")
        fetch = run_fetch(url, page, curl, user_agent, follow=not lane)
        result["fetch"] = fetch
        judge_fetch(fetch, page)
        with open(page, "rb") as fh:
            data = fh.read()
        result.update(html_file="page.html", html_sha256=sha256_bytes(data),
                      content_type=fetch["content_type"], effective_url=fetch["effective_url"])
        stage = "route"
        text = decode_html(data, fetch["content_type"])
        root = parse_html(text)
        base = document_base(fetch["effective_url"], root)
        markers = find_markers(root)
        route = "ROUTE" if markers else "NOT-ROUTED"
        result.update(base_url=base, route=route, markers=dict(markers),
                      engine=ROUTE_ENGINE if markers else PLAIN_ENGINE)
        stage = "normalise"
        if markers:
            sets, problems = find_tab_sets(root)
            if problems:
                raise ProbeFailure("normalise", "ambiguous tab pairing: " + "; ".join(problems[:SHOW_MAX]))
            result["pairing"] = dict(collections.Counter(s.kind for s in sets))
            converted = normaliser(root, sets, base)
        else:
            converted = prepare_plain(text, base)
        converted_path = os.path.join(work, "converted.html")
        write_new(converted_path, converted)
        result["converted_file"] = "converted.html"
        stage = "convert"
        argv, markdown = run_converter(route, converted_path, python, defuddle)
        result["converter"] = argv
        write_new(os.path.join(work, "capture.md"), markdown)
        result.update(capture_file="capture.md", capture_sha256=sha256_bytes(markdown.encode("utf-8")))
        stage = "check"
        try:
            report = check_capture(text, base, markdown)
            result["check"] = {k: report[k] for k in CHECK_KEYS}
            result["check"]["verdict"] = verdict_of(report)
        except Exception as exc:              # a check that cannot run leaves the capture made, its verdict not run
            result["check"] = {"verdict": VERDICT_NOT_RUN,
                               "reason": clip(f"the check failed: {type(exc).__name__}: {exc}")}
        result.update(status="pass", stage="done", reason="")
        code = EXIT_PASS
    except ProbeFailure as exc:
        result.update(status="fail", stage=exc.stage, reason=clip(exc.reason))
        code = EXIT_FAILED
    except Exception as exc:                  # any surprise is a failure, never a pass
        result.update(status="fail", stage="internal",
                      reason=clip(f"unexpected {type(exc).__name__} during {stage}: {exc}"))
        code = EXIT_FAILED
    if own_dir:
        try:
            write_result(work, result)
            result["result_file"] = os.path.join(work, "result.json")
        except OSError as exc:
            result.update(status="fail", reason=clip(f"cannot write result.json: {exc}"))
            code = EXIT_FAILED
    return code, result


# ---------------------------------------------------------------- consumers
SHA_HEX = re.compile(r"^[0-9a-f]{64}$")
FETCH_KEYS = ("curl_exit", "curl_stderr", "http_code", "content_type", "effective_url", "redirects", "redirect_url")
CHECK_COUNTS = ("collapsed", "sets", "labels", "links")


def media_type(content_type):
    return (content_type or "").split(";")[0].strip().lower() if isinstance(content_type, str) else ""


def _count(value):
    """A non-negative integer that is not a bool (JSON true would otherwise read as 1)."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def http_url(value):
    return isinstance(value, str) and URL_OK.match(value) is not None


def _is_time(value):
    try:
        datetime.datetime.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def _hex(value):
    return isinstance(value, str) and SHA_HEX.match(value) is not None


def _converter_ok(argv, route):
    """The converter run `run_converter` records for this route, reading the work directory's copy."""
    if not (isinstance(argv, list) and argv and all(isinstance(a, str) and a for a in argv)):
        return False
    if route == "ROUTE":
        return len(argv) == 5 and argv[1:4] == ["-B", "-m", "markitdown"] and os.path.basename(argv[4]) == "converted.html"
    return (route == "NOT-ROUTED" and len(argv) == 4 and argv[1] == "parse" and argv[3] == "--markdown"
            and os.path.basename(argv[2]) == "converted.html")


def fetch_problem(fetch):
    """Why a fetch record is not a complete, successful HTML transfer the check can read, or None."""
    if not isinstance(fetch, dict) or any(k not in fetch for k in FETCH_KEYS):
        return ("no fetch record with all its fields (curl's exit status, its message, the HTTP status, content "
                "type, effective URL and redirects)")
    rc, code = fetch["curl_exit"], fetch["http_code"]
    if not (_count(rc) and rc == 0):
        return f"curl exit {clip(repr(rc), 20)}: the transfer failed, whatever the status"
    if not (_count(code) and 200 <= code <= 299):
        return f"HTTP {clip(repr(code), 20)}: not a successful response"
    if media_type(fetch["content_type"]) not in HTML_TYPES:
        return f"content type {clip(repr(fetch['content_type']), 60)} is not HTML"
    if not http_url(fetch["effective_url"]):
        return "no http(s) effective URL in the fetch"
    if not (fetch["redirects"] is None or _count(fetch["redirects"])):
        return "a malformed redirect count"
    if not (isinstance(fetch["redirect_url"], str) and isinstance(fetch["curl_stderr"], str)):
        return "malformed curl output fields"
    return None


def page_problems(result):
    """What a record lacks to name a fetched page the check can read: a creation time, a fetch that was
    a successful HTML transfer, the top-level content type and effective URL agreeing with it, and the
    page file with its sha256 (the page's bytes are held to it when they are read). An empty list is a
    page the check may read."""
    problems = [] if _is_time(result.get("created")) else ["no creation time"]
    why = fetch_problem(result.get("fetch"))
    if why:
        return problems + [why]
    fetch = result["fetch"]
    if result.get("content_type") != fetch["content_type"]:
        problems.append("a content type that disagrees with the fetch")
    if result.get("effective_url") != fetch["effective_url"]:
        problems.append("an effective URL that disagrees with the fetch")
    if not (result.get("html_file") == "page.html" and _hex(result.get("html_sha256"))):
        problems.append("no fetched page and its sha256")
    return problems


def result_problems(result, controls):
    """What the record of a capture (status pass) lacks, or where it contradicts itself: every field
    `run_capture` writes when it makes its capture, each of its kind and agreeing with the others.
    controls is this probe's own "k/k" line. An empty list is a complete, consistent record;
    `check_stamp` then holds it to the page and to the files it names."""
    problems = []

    def need(ok, what):
        if not ok:
            problems.append(what)
    need(result.get("stage") == "done" and result.get("reason") == "",
         f"a capture recorded at stage {clip(repr(result.get('stage')), 40)} with reason {clip(repr(result.get('reason')), 80)}")
    need(result.get("probe_sha256") is None or _hex(result.get("probe_sha256")), "a malformed probe_sha256")
    need(result.get("controls") == controls,
         f"controls {clip(repr(result.get('controls')), 40)}, not this probe's {controls}")
    problems += page_problems(result)
    need(http_url(result.get("base_url")), "no http(s) base URL")
    route, markers, engine = result.get("route"), result.get("markers"), result.get("engine")
    marks_ok = isinstance(markers, dict) and all(isinstance(k, str) and _count(v) and v > 0 for k, v in markers.items())
    need(route in ("ROUTE", "NOT-ROUTED") and marks_ok and (route == "ROUTE") == bool(markers),
         f"route {clip(repr(route), 30)} does not agree with its markers {clip(repr(markers), 80)}")
    family = "markitdown" if route == "ROUTE" else "defuddle"
    need(isinstance(engine, str) and family in engine.lower(),
         f"engine {clip(repr(engine), 60)} is no {family} engine for a {route} page")
    need(result.get("converted_file") == "converted.html" and _converter_ok(result.get("converter"), route),
         f"converter {clip(repr(result.get('converter')), 120)} is not the {route} page's converter run on converted.html")
    need(result.get("capture_file") == "capture.md" and _hex(result.get("capture_sha256")), "no capture and its sha256")
    check = result.get("check")
    if not isinstance(check, dict) or check.get("verdict") not in VERDICTS:
        problems.append("no check record with its verdict")
    elif check["verdict"] == VERDICT_NOT_RUN:
        need(isinstance(check.get("reason"), str) and check["reason"].strip() != "",
             "a check recorded as not run with no reason")
    else:
        failures = check.get("failures")
        listed = isinstance(failures, list) and all(isinstance(f, str) for f in failures)
        need(listed, "a check record without its list of findings")
        need(listed and (check["verdict"] == VERDICT_LOSS) == bool(failures),
             f"a check verdict {clip(repr(check['verdict']), 30)} that disagrees with its findings {clip(repr(failures), 120)}")
        need(check.get("ambiguous") == [], "a check record of a capture naming tabs it could not pair")
        need(all(_count(check.get(k)) for k in CHECK_COUNTS) and isinstance(check.get("pairing"), dict),
             "a check record without its counts (collapsed, sets, labels, links) and pairing")
        need(route != "ROUTE" or result.get("pairing") == check.get("pairing"), "a pairing that disagrees with the check's")
    return problems


def _problems_line(problems):
    more = f" (+{len(problems) - SHOW_MAX} more)" if len(problems) > SHOW_MAX else ""
    return "; ".join(problems[:SHOW_MAX]) + more


def check_stamp(result_path, body, url, also_url=None):
    """(verdict, stamp, info): what the capture check finds for this body, as the one-line stamp a save
    path records. It never raises and refuses nothing: no result, an unreadable, malformed or failed
    one, and any unexpected failure give "not run — <why>", never no loss. The result must be for url,
    which is required (a record with no URL never matches an absent one), or for also_url (an open
    copy's address). A record of a capture (status pass) is read only complete and consistent
    (`result_problems`); a failed probe's record only where the probe fetched the page
    (`page_problems`), so a fallback's body is checked against the page the probe fetched. The page is
    re-read and held to its sha256, re-routed and its base recomputed, and the body is checked against
    it, whichever engine produced the body; for a record of a capture, the page's own counts must agree
    with the recorded check, and so must its findings when the body is the probe's own capture. info
    carries the report, the route and whether the body is the probe's own capture."""
    info = {}
    try:
        if not http_url(url):
            return VERDICT_NOT_RUN, not_run(f"no http(s) URL to hold the result to (got {clip(repr(url), 60)})"), info
        if not result_path:
            return VERDICT_NOT_RUN, not_run("no probe result given"), info
        if not os.path.isfile(result_path):
            return VERDICT_NOT_RUN, not_run("no probe result at the path given"), info
        try:
            with open(result_path, encoding="utf-8") as fh:
                result = json.load(fh)
        except (OSError, ValueError) as exc:
            return VERDICT_NOT_RUN, not_run(f"the probe result is unreadable ({type(exc).__name__}: {exc})"), info
        if not isinstance(result, dict) or result.get("schema") != RESULT_SCHEMA:
            return VERDICT_NOT_RUN, not_run(f"the file given is not a {RESULT_SCHEMA} record (an earlier probe's, "
                                            "or another file): probe the page again"), info
        info["result"] = result
        if not http_url(result.get("url")) or result["url"] not in [u for u in (url, also_url) if http_url(u)]:
            return VERDICT_NOT_RUN, not_run(f"the probe result is for {clip(repr(result.get('url')), 120)}, not {url}"), info
        status = result.get("status")
        if status == "fail":
            if page_problems(result):
                return VERDICT_NOT_RUN, not_run(
                    "the probe made no capture and fetched no page the check can read: it failed at "
                    f"{result.get('stage') or 'an unrecorded stage'}: {result.get('reason') or 'no reason recorded'}"), info
            if result.get("stage") in ("start", "controls", "fetch"):   # the page is recorded only after a fetch succeeds
                return VERDICT_NOT_RUN, not_run(f"a malformed probe result: a probe that failed at {result['stage']} "
                                                "records a fetched page"), info
        elif status == "pass":
            problems = result_problems(result, require_controls(route=True, check=True))
            if problems:
                return VERDICT_NOT_RUN, not_run("a malformed probe result: " + _problems_line(problems)), info
        else:
            return VERDICT_NOT_RUN, not_run(f"a malformed probe result: status {clip(repr(status), 30)} is not one "
                                            "the probe writes"), info
        here = os.path.dirname(os.path.abspath(result_path))
        page = os.path.join(here, "page.html")
        if not os.path.isfile(page):
            return VERDICT_NOT_RUN, not_run("the fetched page beside the result is missing"), info
        with open(page, "rb") as fh:
            data = fh.read()
        if sha256_bytes(data) != result["html_sha256"]:
            return VERDICT_NOT_RUN, not_run("the fetched page has changed since the probe"), info
        fetch = result["fetch"]
        text = decode_html(data, fetch["content_type"])
        root = parse_html(text)
        markers = dict(find_markers(root))
        route = "ROUTE" if markers else "NOT-ROUTED"
        if "route" in result and route != result["route"]:
            return VERDICT_NOT_RUN, not_run(f"a malformed probe result: the fetched page routes {route}, not "
                                            f"{clip(repr(result['route']), 30)} as the result says"), info
        if "markers" in result and markers != result["markers"]:
            return VERDICT_NOT_RUN, not_run(f"a malformed probe result: the fetched page's markers "
                                            f"({marker_line(markers)}) are not the result's "
                                            f"({clip(repr(result['markers']), 120)})"), info
        base = document_base(fetch["effective_url"], root)
        if "base_url" in result and base != result["base_url"]:
            return VERDICT_NOT_RUN, not_run(f"a malformed probe result: the fetched page's base URL is {base}, not "
                                            f"{clip(repr(result['base_url']), 120)} as the result says"), info
        identical = None
        if status == "pass":
            captured = os.path.join(here, "capture.md")
            if not os.path.isfile(captured):
                return VERDICT_NOT_RUN, not_run("the capture beside the result is missing"), info
            with open(captured, "rb") as fh:
                if sha256_bytes(fh.read()) != result["capture_sha256"]:
                    return VERDICT_NOT_RUN, not_run("the capture beside the result is not the capture it records "
                                                    "(its sha256 differs)"), info
            identical = sha256_bytes(body.encode("utf-8")) == result["capture_sha256"]
        require_controls(route=True, check=True)
        report = check_capture(text, base, body)
        info.update(report=report, route=route, body_identical=identical)
        recorded = result["check"] if status == "pass" else None
        if recorded and recorded["verdict"] != VERDICT_NOT_RUN:
            # collapsed, sets, labels and pairing come from the page alone; links and findings from the body.
            keys = ["collapsed", "sets", "labels", "pairing"] + (["links", "failures"] if identical else [])
            differ = [k for k in keys if report[k] != recorded[k]]
            if differ:
                return VERDICT_NOT_RUN, not_run(
                    "a malformed probe result: its check record disagrees with the fetched page ("
                    + ", ".join(f"{k} {clip(repr(recorded[k]), 80)} recorded, {clip(repr(report[k]), 80)} found"
                                for k in differ) + ")"), info
        return verdict_of(report), stamp_of(report), info
    except ProbeFailure as exc:
        why = f"the check's {exc.reason}" if exc.stage == "controls" else f"{exc.stage}: {exc.reason}"
        return VERDICT_NOT_RUN, not_run(why), info
    except Exception as exc:                  # a check that fails to run is stamped not run, never no loss
        return VERDICT_NOT_RUN, not_run(f"the check failed: {type(exc).__name__}: {exc}"), info


# ---------------------------------------------------------------- verbs
def _read_page(path, content_type):
    if not os.path.isfile(path):
        raise ProbeFailure("start", f"no page at {path}")
    with open(path, "rb") as fh:
        data = fh.read()
    if not data.strip():
        raise ProbeFailure("start", f"the page {path} is empty")
    return decode_html(data, content_type)


def cmd_capture(a):
    code, result = run_capture(a.url, a.work, a.curl, a.defuddle, a.python, a.user_agent)
    fetch = result.get("fetch") or {}
    print(f"capture_probe: {a.url}")
    if fetch:
        print(f"fetch: curl exit {fetch.get('curl_exit')} · HTTP {fetch.get('http_code', '?')} · "
              f"{fetch.get('content_type') or 'no content type'} · effective {fetch.get('effective_url') or '?'} · "
              f"{fetch.get('redirects')} redirects")
    if result.get("route"):
        print(f"route: {result['route']} · markers: {marker_line(result.get('markers') or {})}")
    if result.get("controls"):
        print(f"controls: {result['controls']}")
    where = result.get("result_file") or "(no result.json: the directory is not this run's)"
    if code == EXIT_PASS:
        capture = os.path.join(os.path.abspath(a.work), "capture.md")
        print(f"converted: {result['engine']} → capture.md ({os.path.getsize(capture)} bytes)")
        with open(capture, encoding="utf-8", errors="replace") as fh:
            _verdict, stamp, _info = check_stamp(where, fh.read(), a.url)
        print(f"check: {stamp}")
        print(f"result: {where} · a capture was made: save {capture} with --engine '{result['engine']}' "
              f"--probe-result {where} (gather's writer), or through `stamp` (ingest Step 0); the check line above "
              "is the stamp it records, a warning that never blocks the save")
    else:
        print(f"PROBE FAILED: {result['stage']}: {result['reason']}")
        print(f"result: {where} · no capture was made: take the chain's next engine, and pass this result with "
              "its body (--probe-result, or `stamp`) so the body is checked against the page wherever the probe "
              "fetched one")
    return code


def parse_http(value):
    parts = (value or "").strip().split(None, 1)
    if not parts:
        raise ProbeFailure("fetch", "--http is empty")
    code = int(parts[0]) if parts[0].isdigit() else parts[0]
    return code, (parts[1] if len(parts) > 1 else "")


def cmd_route(a):
    try:
        controls = require_controls(route=True, check=False)
        code, content_type = parse_http(a.http)
        fetch = {"curl_exit": a.curl_exit, "http_code": code, "content_type": content_type}
        judge_fetch(fetch, a.page, need_effective=False)
        markers = find_markers(parse_html(_read_page(a.page, content_type)))
    except ProbeFailure as exc:
        print(f"PROBE FAILED: {exc.stage}: {exc.reason}")
        return EXIT_FAILED
    except Exception as exc:
        print(f"PROBE FAILED: internal: unexpected {type(exc).__name__}: {exc}")
        return EXIT_FAILED
    print(f"route: {'ROUTE' if markers else 'NOT-ROUTED'} · markers: {marker_line(markers)} · controls {controls}")
    return EXIT_ROUTE if markers else EXIT_PASS


def cmd_check(a):
    try:
        controls = require_controls(route=False, check=True)
        page = _read_page(a.page, a.content_type)
        with open(a.capture, encoding="utf-8", errors="replace") as fh:
            markdown = fh.read()
        if not markdown.strip():
            raise ProbeFailure("check", f"the capture {a.capture} is empty")
        report = check_capture(page, a.base_url, markdown)
    except ProbeFailure as exc:
        print(f"PROBE FAILED: {exc.stage}: {exc.reason}")
        return EXIT_FAILED
    except Exception as exc:
        print(f"PROBE FAILED: internal: unexpected {type(exc).__name__}: {exc}")
        return EXIT_FAILED
    verdict = verdict_of(report)
    print(f"check: {stamp_of(report)} · route {report['route']} · {check_line(report)} · controls {controls}")
    for failure in report["failures"]:
        print(f"  finding: {failure}")
    return {VERDICT_NONE: EXIT_PASS, VERDICT_LOSS: EXIT_ROUTE, VERDICT_NOT_RUN: EXIT_FAILED}[verdict]


def cmd_normalise(a):
    try:
        out = os.path.abspath(a.output)
        if os.path.lexists(out):
            raise ProbeFailure("start", f"{out} exists; normalise writes a new file only")
        vault = vault_above(os.path.dirname(out))
        if vault:
            raise ProbeFailure("start", f"{out} lies inside a vault ({vault})")
        require_lane_write(out, "-o")
        root = parse_html(_read_page(a.page, a.content_type))
        sets, problems = find_tab_sets(root)
        if problems:
            raise ProbeFailure("normalise", "ambiguous tab pairing: " + "; ".join(problems[:SHOW_MAX]))
        write_new(out, normalise(root, sets, document_base(a.base_url, root)))
    except ProbeFailure as exc:
        print(f"PROBE FAILED: {exc.stage}: {exc.reason}")
        return EXIT_FAILED
    except Exception as exc:
        print(f"PROBE FAILED: internal: unexpected {type(exc).__name__}: {exc}")
        return EXIT_FAILED
    kinds = ", ".join(f"{k} ×{v}" for k, v in sorted(collections.Counter(s.kind for s in sets).items())) or "none"
    print(f"normalised: {out} · tab sets {len(sets)} ({kinds}) · labels {sum(len(s.pairs) for s in sets)}")
    return EXIT_PASS


def one_line(value):
    return isinstance(value, str) and value.strip() != "" and re.search(r"[\r\n]", value) is None


def cmd_stamp(a):
    """The provenance lines for a body saved with no writer of its own (ingest Step 0). The check warns
    and refuses nothing: whatever it finds, and whether or not it runs, the lines are printed and the
    exit is 0. Only an input that leaves no provenance to print, or would break the frontmatter, exits 2.
    converted_by is the --engine given, the engine that produced this body, never the probe's."""
    for flag, value in (("--engine", a.engine), ("--allow-degraded", a.allow_degraded)):
        if value is not None and not one_line(value):
            print(f"BAD INPUT: {flag} needs a one-line value (a line break would inject frontmatter); nothing printed")
            return EXIT_FAILED
    if not http_url(a.url):
        print("BAD INPUT: --url needs one http(s) URL with no whitespace (it is the converted_from line); "
              "nothing printed")
        return EXIT_FAILED
    try:
        with open(a.body, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
    except OSError as exc:
        print(f"BAD INPUT: the body is unreadable ({type(exc).__name__}: {exc}); nothing printed")
        return EXIT_FAILED
    if not body.strip():
        print("BAD INPUT: the body is empty, so there is nothing to save; nothing printed")
        return EXIT_FAILED
    _verdict, stamp, info = check_stamp(a.result, body, a.url)
    print(f"check: {stamp}")
    probe_engine = (info.get("result") or {}).get("engine")
    if info.get("body_identical") is True:
        print(f"body: the probe's own capture ({probe_engine})")
    elif info.get("body_identical") is False:
        print(f"body: not the probe's own capture (another engine's, or edited): converted_by names the --engine "
              f"given, never the probe's {probe_engine}")
    print(f"converted_from: {a.url}")
    print(f"converted_by: {a.engine}")
    print(f'capture_check: "{stamp}"')
    fields = f'"capture_check": "{stamp}"'
    if a.allow_degraded is not None:
        declared = stamp_value(f"declared — {a.allow_degraded}", REASON_MAX)
        print(f'capture_quality: "{declared}"')
        fields += f', "degraded": "{declared}"'
    print(f"checkpoint: add {fields} to this source's converted checkpoint"
          + ("; declare it in the run report" if a.allow_degraded is not None else ""))
    return EXIT_PASS


def main(argv=None):
    ap = argparse.ArgumentParser(description="Structural capture routing for a web page, and the capture check's stamp.")
    sub = ap.add_subparsers(dest="verb", required=True)
    c = sub.add_parser("capture", help="fetch once, route, convert and check into a new work directory")
    c.add_argument("url")
    c.add_argument("--work", required=True, help="a new or empty directory outside any vault")
    c.add_argument("--curl", default="curl")
    c.add_argument("--defuddle", default="defuddle")
    c.add_argument("--python", default=None, help="the interpreter that runs `-m markitdown` (default: this one)")
    c.add_argument("--user-agent", dest="user_agent", default=None)
    r = sub.add_parser("route", help="the routing decision for a saved page (stdout only)")
    r.add_argument("page")
    r.add_argument("--http", required=True, help="'<HTTP status> <content type>' as curl reported them")
    r.add_argument("--curl-exit", dest="curl_exit", type=int, required=True, help="curl's exit status")
    n = sub.add_parser("normalise", help="write the copy ROUTE converts")
    n.add_argument("page")
    n.add_argument("--base-url", dest="base_url", required=True)
    n.add_argument("-o", dest="output", required=True)
    n.add_argument("--content-type", dest="content_type", default="")
    k = sub.add_parser("check", help="the capture check alone, its stamp printed (stdout only)")
    k.add_argument("page")
    k.add_argument("capture")
    k.add_argument("--base-url", dest="base_url", required=True)
    k.add_argument("--content-type", dest="content_type", default="")
    s = sub.add_parser("stamp", help="the provenance lines and the capture check's stamp for a body about to be "
                                     "saved (stdout only; ingest Step 0)")
    s.add_argument("result", help="capture_probe.py capture's result.json (a missing one is stamped not run)")
    s.add_argument("--body", required=True)
    s.add_argument("--url", required=True)
    s.add_argument("--engine", required=True,
                   help="the engine that produced the body, printed as converted_by (never taken from the result)")
    s.add_argument("--allow-degraded", dest="allow_degraded", default=None, metavar="WHY",
                   help="declare damage the check cannot see: printed as capture_quality \"declared — WHY\"")
    a = ap.parse_args(argv)
    handler = {"capture": cmd_capture, "route": cmd_route, "normalise": cmd_normalise,
               "check": cmd_check, "stamp": cmd_stamp}[a.verb]
    return handler(a)


if __name__ == "__main__":
    sys.exit(main())
