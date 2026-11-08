#!/usr/bin/env python3
"""The rule register's tool: one data file, one generated page, one weekly pass.

The data file holds the owner's wordings, so it never ships; this tool does, and holds none.

Commands (stdout only, unless the command says WRITES):
  generate        WRITES the page from the data file.
  wording-check   [--trial] [--installed-only LIST]  each approved wording against its home.
  weekly          [--full] [--all-flags]  the one pass: wording check, coverage check with its four
                  listings and the older-rulings listing, copies listing, flags now due, sources
                  changed by recorded fingerprints. It only lists and stops no work.
  record-audit    WRITES the audit block of the data file: the fingerprints, rulings and listed flags
                  the next weekly pass compares with. Run it once the weekly pass has been walked
                  through.
  seed            --map FILES --rules FILE --tracing FILE  the first rows, from the map's rows.
                  --skill-sections adds one row per section of each skill's SKILL.md.
                  Prints the data document; --out FILE WRITES it, only where nothing exists.
  in-place        candidates for the rules already in their right home, for one helper to read, with
                  the inventory of pages they come from and what it leaves out.
  cleanup         the weekly clean-up's listing: store sizes and old records nothing names.

Every command takes --vault DIR (default: derived from this file's place), --data FILE and --today
YYYY-MM-DD. A staged copy passes --vault, since its folder is not its installed place.

The wording check.
  Comparison: stored wording and home, after joining wrapped lines and collapsing spaces and list
  indentation. Every word, punctuation mark, capital and emphasis mark must then match. A row's home
  is its file and section: where the row names a section, the wording must stand inside it, its
  comments and nested headings included. The same words elsewhere in the file are a miss that says so.
  First step, its control: the load marker at the top of the preference file must be found, which
  proves the reading works, and a sentence and a copy differing from it by a single word, each
  built in memory and kept nowhere, must give one match and one miss, proving the comparison.
  Either wrong: "could not check", never a result. No approved wording serves as the control.
  No data file and no page, as in a fresh public copy: "not applicable".
  It reads only the homes the register names, never a dated record. A row with approved words whose
  home is a dated record takes the status "listed, not checked", with its reason, and fails no install.
  "Could not check" also covers what the check was not given whole: a LIST naming any row the register
  does not hold, or a row called approved that holds no wording to compare.
  LIST is a file of row ids, one a line, or ids joined by commas; a map row's id names its spans, and
  a merged row or a carried waiting text names the row that holds its words.
  The trial state, on when --trial is given or the data says "trial": true: it logs what it would
  have blocked and blocks nothing. The seed sets it on; the lead sets it off after the first install.

The flags. Each comes up once, when it is due: a dated flag once its date has passed; a flag naming
  an event, or with no clause, at the first pass that sees it. record-audit records what came up, and
  after that a flag is only counted, unless its text changes or 28 days pass since it was last
  listed, so a pending event is not lost. --all-flags lists every one.

Exit codes.
  0  the command ran. Misses outside an install are listed and exit 0; so does the weekly pass.
  1  wording-check inside an install with the trial state off: a just-placed text missed, or its
     home was refused unread. seed: an anomaly was left; the document is still produced, each listed.
  2  PROBE FAILED: a broken premise, "could not check" among them; never reported as clean.

Fingerprints are sha256 of content, recorded at each audit. Neither file dates nor git are used.
The clean-up's age test alone reads file dates, since that rule is about age.
"""

import argparse
import collections
import datetime
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import time

DATA_REL = "wiki/developments/rule-register-data.json"
PAGE_REL = "wiki/developments/rule-register.md"
ALWAYS_ON = ("CLAUDE.md", "CUSTOMISATION.md")
MARKER_FILE = "CUSTOMISATION.md"
LOAD_MARKER = "CUSTOMISATION-LOADED-v1"
SCHEMA_VERSION = 1

# Dated records. The wording check never searches them and refuses a row that names one as a home.
DATED_FILES = ("wiki/log.md", "wiki/developments/owner-rulings-history.md",
               "wiki/developments/known-issues.md")
DATED_PREFIXES = ("output/reports/",)
OWNER_NOTES_HEADING = "## Dated owner notes"
# Registries nearly every page names; a change to them says nothing about a page that names them.
# The data file changes at every audit, by the audit's own record.
REGISTRIES = ("wiki/log.md", "wiki/index.md")
NOT_A_NAMED_SOURCE = REGISTRIES + (DATA_REL,)
WALK_SKIP = {".git", "__pycache__", "node_modules", ".obsidian", ".trash", ".claudian"}
# The wording status of approved words whose home is a dated record, which the check never reads.
LISTED = "listed, not checked"
# Where the framework's own pages live, so a rule with no date mark may stand on any of them. The
# other wiki folders hold the outside world's words, so a rule word there is counted and left out.
# Set by judgement, unmeasured.
FRAMEWORK_FOLDERS = ("wiki/developments/", "wiki/syntheses/", "wiki/user/")

LIST_CAP = 40      # lines shown per listing, the count always whole; set by judgement, unmeasured
OLDER_SHOWN = 3    # older rulings shown beside a new one, closest first; set by judgement, unmeasured
EXCERPT = 150      # characters of a text shown in a listing line; set by judgement, unmeasured
CLEANUP_DAYS = 14  # the owner's rule on old records; its number is set by judgement, unmeasured

FRONTMATTER = re.compile(r"\A---\n.*?\n---[ \t]*(?:\n|\Z)", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)
LOCAL_MARKER = re.compile(r"<!--\s*vault-local:(?:begin|end)\s*-->")
QUOTE_PREFIX = re.compile(r"^[ \t]*(?:>[ \t]?)+", re.M)
HYPHEN_WRAP = re.compile(r"(?<=\w-)[ \t]*\n[ \t]*(?=\w)")
SPACES = re.compile(r"\s+")
LIST_MARK = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
LIST_START = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^(```|~~~)")
RULE_LINE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")
IMPORT_LINE = re.compile(r"^@\S+$")
TABLE_SEP = re.compile(r"^\|?[\s:|-]+\|?$")
SENTENCE_END = re.compile(r"(?<=[.!?])[\"”)\]*_`]*\s+(?=[A-Z*\"“`(\[])")
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’-]*")
BACKTICKED = re.compile(r"`([^`\n]+)`")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")
MONTH_RE = "|".join(MONTHS)
ISO_DATE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
PROSE_DAYS = re.compile(r"((?:\d{1,2}(?:,\s*|\s+and\s+|\s+to\s+))*\d{1,2})\s+(%s)\b" % MONTH_RE)
RULING_WORD = re.compile(r"\b(owner|ruling|rulings|ruled|decision|decided|approved|instruction)\b",
                         re.I)
PARENS = re.compile(r"\(([^()]*)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
PAGE_HAS_RULING = re.compile(
    r"\bowner(?:'s)?(?: ruling| rulings| decision| decisions| instruction)?[^.\n]{0,40}?"
    r"\b(?:20\d\d-\d\d-\d\d|\d{1,2} (?:%s) 20\d\d)" % MONTH_RE, re.I)
CLEAR_CLAUSE = re.compile(r"\b(?:clears?|clearing|cleared by|until|due(?: on| by)?|"
                          r"review(?:ed)? (?:on|by))\b[^.;]*", re.I)
# A word that sorts a candidate for the reader; it decides nothing. Set by judgement, unmeasured.
RULE_WORD = re.compile(r"\b(?:must|never|always|shall|do not|don't|may not)\b", re.I)
WIKI_PATH = re.compile(r"wiki/[A-Za-z0-9_./ -]+?\.md")
WIKILINK = re.compile(r"\[\[([^\]|#\n]+)")
SPAWN_GROUP = re.compile(r"^(run-\d{8}-[^-.]+)")   # a run's records share its id: run-<date>-<name>
HELD_NAMES = {"backup", "backups", "held", "staged-register.md", "steps.jsonl", "part.json",
              "targets.json"}


def bare_heading(text):
    """A heading path's last part, without its hash marks, as the rule list's rows carry it."""
    part = (text or "").split(" > ")[-1].strip()
    return re.sub(r"^#+\s*", "", part).strip()


def blank(text):
    return "\n" * text.count("\n")


def blank_owner_notes(raw):
    """Blank a page's dated owner notes, keeping line numbers. The check never searches them."""
    if OWNER_NOTES_HEADING not in raw:
        return raw
    out, skipping = [], False
    for line in raw.split("\n"):
        if line.strip() == OWNER_NOTES_HEADING:
            skipping = True
        elif skipping and re.match(r"^#{1,2}\s", line):
            skipping = False
        out.append("" if skipping else line)
    return "\n".join(out)


def block_source(raw):
    """A file's text as rows are cut from it: no frontmatter, comments or owner notes."""
    raw = raw.replace("\r\n", "\n")
    match = FRONTMATTER.match(raw)
    if match:
        raw = blank(match.group(0)) + raw[match.end():]
    raw = COMMENT.sub(lambda m: blank(m.group(0)), raw)
    return blank_owner_notes(raw)


def normal(text):
    """Join wrapped lines; collapse spaces, list indentation and quote marks at a line's start.

    Inline vault-local markers are read past. Nothing else changes: words, punctuation, capitals
    and emphasis marks stay exactly as they are. A rule may have its home in a how-to comment or a
    helper definition's frontmatter, so neither is taken out of the text compared.
    """
    text = LOCAL_MARKER.sub("", text.replace("\r\n", "\n"))
    text = QUOTE_PREFIX.sub("", text)
    text = HYPHEN_WRAP.sub("", text)
    return SPACES.sub(" ", text).strip()


def needle_of(text):
    """A stored wording ready to look for: normalised, without the list mark its row opened with."""
    return LIST_MARK.sub("", normal(text))


def positions(needle, hay):
    """Each place `needle` occurs in `hay` as whole words, so a word extended never matches."""
    found, start = [], 0
    while needle:
        at = hay.find(needle, start)
        if at < 0:
            break
        end = at + len(needle)
        left_ok = not needle[0].isalnum() or at == 0 or not hay[at - 1].isalnum()
        right_ok = not needle[-1].isalnum() or end == len(hay) or not hay[end].isalnum()
        if left_ok and right_ok:
            found.append(at)
        start = at + 1
    return found


def matches(needle, hay):
    """True when a needle already normalised stands in a normalised text. The one comparison."""
    return bool(positions(needle, hay))


def excerpt(text, size=EXCERPT):
    text = SPACES.sub(" ", text or "").strip()
    return text if len(text) <= size else text[:size].rsplit(" ", 1)[0] + " …"


def word_diff(stored, current):
    """The difference word by word, with a little context: [-taken out-] {+put in+}."""
    a, b = stored.split(" "), current.split(" ")
    pieces = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            run = a[i1:i2]
            pieces.append(" ".join(run) if len(run) <= 12
                          else " ".join(run[:5] + ["…"] + run[-5:]))
        else:
            if i2 > i1:
                pieces.append("[-" + " ".join(a[i1:i2]) + "-]")
            if j2 > j1:
                pieces.append("{+" + " ".join(b[j1:j2]) + "+}")
    return " ".join(pieces)


def split_sentences(text):
    return [piece.strip() for piece in SENTENCE_END.split(text) if piece.strip()]


def dates_in(span):
    """ISO dates in a span, whichever way it writes them. A prose date with no year gives none."""
    found = ["%s-%s-%s" % m.groups() for m in ISO_DATE.finditer(span)]
    for match in PROSE_DAYS.finditer(span):
        year = re.search(r"\b(20\d\d)\b", span[match.end():])
        if year:
            month = MONTHS.index(match.group(2)) + 1
            found.extend("%s-%02d-%02d" % (year.group(1), month, int(day))
                         for day in re.findall(r"\d{1,2}", match.group(1)))
    return found


def ruling_marks(text):
    """The dated ruling markers in a block: bracketed or bold spans naming a date and a ruling."""
    marks = {}
    for span in PARENS.findall(text) + BOLD.findall(text):
        dates = dates_in(span)
        if dates and RULING_WORD.search(span):
            # A marker in brackets inside a bold lead is one ruling, seen twice.
            date = max(dates)
            if len(span) > len(marks.get(date, "")):
                marks[date] = span
    return sorted(marks.items())


Block = collections.namedtuple("Block", "line section text")


def parse_blocks(raw):
    """The file's text blocks: one bullet, paragraph, table row or fenced line each.

    Headings, blank lines, rules, fences, table headers, imports, comments and frontmatter are no
    blocks, as they are no rule rows in the rule list.
    """
    lines = block_source(raw).split("\n")
    blocks, buffer, start, section, in_fence = [], [], 0, "", False

    def flush():
        if buffer:
            blocks.append(Block(start, section, normal("\n".join(buffer))))
            del buffer[:]

    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if FENCE.match(stripped):
            flush()
            in_fence = not in_fence
            blocks.append(Block(number, section, normal(line)))   # a code-block row holds its fences
        elif in_fence:
            if stripped:
                blocks.append(Block(number, section, normal(line)))
        elif not stripped or RULE_LINE.match(stripped) or IMPORT_LINE.match(stripped):
            flush()
        elif HEADING.match(line):
            flush()
            section = HEADING.match(line).group(2)
        elif stripped.startswith("|"):
            flush()
            following = lines[number].strip() if number < len(lines) else ""
            if not TABLE_SEP.match(stripped) and not TABLE_SEP.match(following or "x"):
                blocks.append(Block(number, section, normal(line)))
        else:
            if LIST_START.match(line):
                flush()
            if not buffer:
                start = number
            buffer.append(line)
    flush()
    return blocks


def never_read(rel):
    """Cold storage and credentials are never opened, whatever a page or row names."""
    parts = rel.split("/")
    name = parts[-1]
    return parts[0] == "attic" or name.endswith(".env") or name.startswith("credentials")


def is_dated_record(rel):
    parts = rel.split("/")
    name = parts[-1].lower()
    return (rel in DATED_FILES or rel.startswith(DATED_PREFIXES) or "handoffs" in parts
            or "decisions" in name or "handoff" in name)


class Vault:
    """Read-only access to the vault, each file read and normalised at most once."""

    def __init__(self, root):
        self.root = os.path.realpath(root)
        self._raw, self._normal, self._blocks, self._sections = {}, {}, {}, {}

    def canonical(self, rel):
        if not rel:
            return ""
        path = os.path.expanduser(rel)
        if os.path.isabs(path):
            real = os.path.normpath(path)
            if real.startswith(self.root + os.sep):
                return real[len(self.root) + 1:]
            return path
        return os.path.normpath(path)

    def path(self, rel):
        rel = self.canonical(rel)
        return rel if os.path.isabs(rel) else os.path.join(self.root, rel)

    def raw(self, rel):
        rel = self.canonical(rel)
        if never_read(rel):
            return None
        if rel not in self._raw:
            try:
                with open(self.path(rel), encoding="utf-8", errors="replace") as stream:
                    self._raw[rel] = stream.read()
            except OSError:
                self._raw[rel] = None
        return self._raw[rel]

    def text(self, rel, with_notes=False):
        """The file's text, normalised, or None when it cannot be read. Owner notes stay out,
        since the wording check never searches them, unless the caller is no wording check."""
        key = (self.canonical(rel), with_notes)
        if key not in self._normal:
            raw = self.raw(rel)
            if raw is None:
                self._normal[key] = None
            else:
                raw = raw.replace("\r\n", "\n")
                self._normal[key] = normal(raw if with_notes else blank_owner_notes(raw))
        return self._normal[key]

    def blocks(self, rel):
        rel = self.canonical(rel)
        if rel not in self._blocks:
            raw = self.raw(rel)
            self._blocks[rel] = [] if raw is None else parse_blocks(raw)
        return self._blocks[rel]

    def headings(self, rel):
        """A file's headings outside fences, as (level, text), or None when it cannot be read."""
        raw = self.raw(rel)
        if raw is None:
            return None
        found, in_fence = [], False
        for line in block_source(raw).split("\n"):
            if FENCE.match(line.strip()):
                in_fence = not in_fence
            elif not in_fence and HEADING.match(line):
                match = HEADING.match(line)
                found.append((len(match.group(1)), match.group(2)))
        return found

    def section_text(self, rel, section):
        """A section's text as the comparison reads it, normalised, or "" where it has no such section.

        It runs to the next heading no deeper than its own, so nested headings stay inside. Comments
        stay in the text, since a rule may have its home in a how-to comment, but a heading-like line
        inside a comment or fence opens and closes nothing. Dated owner notes stay out.
        """
        wanted = bare_heading(section)
        key = (self.canonical(rel), wanted)
        if key not in self._sections:
            raw = self.raw(rel)
            selected, level, fenced = [], None, False
            if raw is not None:
                raw = raw.replace("\r\n", "\n")
                # Each blanking keeps the line count, so the two lists stay line for line.
                for line, seen in zip(blank_owner_notes(raw).split("\n"), block_source(raw).split("\n")):
                    if FENCE.match(seen.strip()):
                        fenced = not fenced
                    heading = None if fenced else HEADING.match(seen)
                    if heading:
                        depth = len(heading.group(1))
                        if level is not None and depth <= level:
                            level = None
                        if level is None and bare_heading(heading.group(2)) == wanted:
                            level = depth
                            continue
                    if level is not None:
                        selected.append(line)
            self._sections[key] = normal("\n".join(selected))
        return self._sections[key]

    def walk(self, top):
        """Vault-relative paths of the files under `top`, skipping cold storage and tool state."""
        found = []
        for folder, subdirs, names in os.walk(os.path.join(self.root, top)):
            rel_folder = os.path.relpath(folder, self.root)
            rel_folder = "" if rel_folder == "." else rel_folder + "/"
            subdirs[:] = sorted(d for d in subdirs if d not in WALK_SKIP
                                and not (rel_folder == "" and d == "attic"))
            found.extend(rel_folder + name for name in sorted(names) if name != ".DS_Store")
        return found


def store_root():
    """The machine-local store, derived as the delegate skill's tools derive it."""
    given = os.environ.get("LLM_WIKI_STORE") or os.path.join(os.path.expanduser("~"), ".llm-wiki")
    return os.path.realpath(os.path.expanduser(given))


def write_atomic(path, text, keep_mode=True):
    """The one place this tool writes: a new copy beside the file, swapped in by one rename."""
    mode = os.stat(path).st_mode & 0o777 if keep_mode and os.path.exists(path) else 0o600
    temporary = os.path.join(os.path.dirname(path) or ".", "." + os.path.basename(path) + ".new")
    with open(temporary, "w", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def probe_failed(what):
    print("PROBE FAILED: " + what)
    return 2


def vault_root(args):
    return args.vault or os.path.abspath(os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "..", "..", ".."))


class Context:
    def __init__(self, args):
        self.vault = Vault(vault_root(args))
        self.data_path = args.data or os.path.join(self.vault.root, DATA_REL)
        self.page_path = getattr(args, "page", None) or os.path.join(self.vault.root, PAGE_REL)
        self.today = args.today or datetime.date.today().isoformat()
        self.data, self.problem = None, None
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, encoding="utf-8") as stream:
                    self.data = json.load(stream)
                if not (isinstance(self.data, dict) and isinstance(self.data.get("rows"), list)):
                    self.problem, self.data = "the data file holds no list of rows", None
            except (OSError, ValueError) as error:
                self.problem = "the data file cannot be read: %s" % error
        elif os.path.exists(self.page_path):
            # A fresh public copy has neither. The page without its data is a broken premise.
            self.problem = "the page exists but its data file is gone: %s" % self.data_path

    @property
    def rows(self):
        return self.data["rows"] if self.data else []

    @property
    def absent(self):
        return self.data is None and self.problem is None


# ---- the wording check -------------------------------------------------------------------------

def prove_control(vault):
    """(True, the control line) or (False, why). Both results form one line, apart from any miss."""
    raw = vault.raw(MARKER_FILE)
    if raw is None:
        return False, "%s cannot be read, so the reading is unproved" % MARKER_FILE
    top = raw.replace("\r\n", "\n").split("\n## ", 1)[0]
    lines = [line for line in top.split("\n") if LOAD_MARKER in line]
    if not lines:
        return False, "the load marker is not at the top of %s" % MARKER_FILE
    sentence = normal(lines[0])
    words = sentence.split(" ")
    changeable = [i for i, word in enumerate(words) if word.isalpha() and len(word) > 2
                  and word != word[::-1]]
    if not changeable:
        return False, "the load marker's line gives no word to change, so the comparison is unproved"
    changed = list(words)
    changed[changeable[len(changeable) // 2]] = words[changeable[len(changeable) // 2]][::-1]
    copy = " ".join(changed)
    # The text compared with is itself made in memory, wrapped, so the joining is proved too.
    wrapped = normal("\n  ".join(words))
    one_match = matches(needle_of(sentence), wrapped)
    one_miss = not matches(needle_of(copy), wrapped)
    if not (one_match and one_miss):
        return False, "the comparison gave %s on the sentence and %s on its one-word copy" % (
            "a match" if one_match else "a miss", "a miss" if one_miss else "a match")
    return True, ("CONTROL: load marker found in %s; a sentence and its one-word copy, both in "
                  "memory: 1 match, 1 miss" % MARKER_FILE)


Miss = collections.namedtuple("Miss", "row_id map_row home section stored current difference outside")


def approved_of(row):
    return row.get("approved") or []


def names_of(row):
    """Every id an install's LIST may name this row by: its own, its map row's, the rows merged into
    it and the waiting texts it carries."""
    row_id = row.get("id")
    names = {row_id, row.get("map_row"), str(row_id).split("#")[0]}
    names.update(row.get("merged_from") or [])
    names.update(row.get("carries") or [])
    return {name for name in names if name}


def incomplete_rows(ctx):
    """Why the rows cannot all be checked, or nothing. A row called approved with no wording would
    pass having compared nothing; a row listed, not checked is only that where its reason holds."""
    empty, unlisted = [], []
    for row in ctx.rows:
        if row.get("wording") == "approved-record":
            if not approved_of(row) and row.get("check") != "reading-only":
                empty.append(str(row.get("id")))
        elif row.get("wording") == LISTED:
            rel = ctx.vault.canonical((row.get("home") or {}).get("file") or "")
            if approved_of(row) or not row.get("wording_reason") or not rel or not is_dated_record(rel):
                unlisted.append(str(row.get("id")))
    why = []
    if empty:
        why.append("approved rows hold no wording to compare: " + ", ".join(sorted(empty)))
    if unlisted:
        why.append("rows are %s with no dated record for a home, no reason, or a wording to compare: %s" % (
            LISTED, ", ".join(sorted(unlisted))))
    return "; ".join(why)


def closest_block(vault, rel, section, stored):
    """The home's current text nearest the stored wording: in its section first, else anywhere."""
    wanted = set(WORD.findall(stored))
    if not wanted:
        return ""
    blocks = vault.blocks(rel)
    named = [b for b in blocks if section and bare_heading(b.section) == bare_heading(section)]
    best, best_score = "", 0.0
    for block in named or blocks:
        words = set(WORD.findall(block.text))
        score = len(wanted & words) / float(len(wanted | words) or 1)
        if score > best_score:
            best, best_score = block.text, score
    # Under a fifth of the words shared reads as no neighbour; set by judgement, unmeasured.
    return best if best_score >= 0.2 else ""


class WordingResult:
    def __init__(self):
        self.control_ok, self.control_line, self.why = False, "", ""
        self.checked, self.in_home = 0, 0
        self.misses, self.noted, self.refused, self.listed = [], [], [], []


def wording_pass(ctx):
    """The check itself. It reads only the marker file and the homes the register names."""
    result = WordingResult()
    proved, line = prove_control(ctx.vault)
    if not proved:
        result.why = line
        return result
    result.control_line = line
    result.why = incomplete_rows(ctx)
    if result.why:
        return result
    result.control_ok = True
    for row in ctx.rows:
        home = row.get("home") or {}
        rel = ctx.vault.canonical(home.get("file") or "")
        section = home.get("section")
        if row.get("wording") == LISTED:
            result.listed.append((row.get("id"), row.get("wording_reason")))
            continue
        for wording in approved_of(row):
            result.checked += 1
            stored = needle_of(wording.get("text") or "")
            if not rel or is_dated_record(rel) or never_read(rel):
                result.refused.append((row.get("id"), rel))
                continue
            whole = ctx.vault.text(rel)
            hay = ctx.vault.section_text(rel, section) if whole is not None and section else whole
            if hay is not None and stored and matches(stored, hay):
                result.in_home += 1
                continue
            current = "" if hay is None else closest_block(ctx.vault, rel, section, stored)
            noted = [n for n in row.get("noted") or []
                     if hay is not None and matches(needle_of(n.get("home_text") or "\0"), hay)]
            if noted:
                result.noted.append((row.get("id"), noted[-1].get("date")))
                continue
            difference = word_diff(stored, current) if current else "(no similar text in this home)"
            outside = bool(section and whole is not None and stored and matches(stored, whole))
            result.misses.append(Miss(row.get("id"), row.get("map_row"), rel, section, stored, current,
                                      difference, outside))
    return result


def print_wording(result, show_listed=True):
    if result.control_line:
        print(result.control_line)
    if not result.control_ok:
        print("PROBE FAILED: could not check: " + result.why)
        return
    for miss in result.misses:
        print("MISS %s · %s § %s" % (miss.row_id, miss.home, miss.section or "(no section named)"))
        print("  stored: " + miss.stored)
        print("  home:   " + (miss.current or "(no similar text in this home)"))
        print("  diff:   " + miss.difference)
        if miss.outside:
            print("  place:  these words stand whole in this file, outside this section")
    for row_id, rel in result.refused:
        print("REFUSED %s · %s is a dated record or names no file, never a home" % (row_id, rel))
    for row_id, reason in result.listed if show_listed else []:
        print("LISTED %s · %s: %s" % (row_id, LISTED, reason))
    if result.misses:
        print("A miss goes to the owner, who chooses: the stored wording goes back; the new text becomes "
              "the approved wording, the old one going once to the rulings history; or it stays as a "
              "noted difference, stored on the row with its date and the owner's words.")
    print("WORDING: %d approved wordings: %d in their homes, %d missed (%d of them standing outside "
          "their named section), %d noted differences, %d refused homes; %d rows %s" % (
              result.checked, result.in_home, len(result.misses),
              sum(1 for miss in result.misses if miss.outside), len(result.noted),
              len(result.refused), len(result.listed), LISTED))


def installed_ids(value):
    """The ids a LIST names, or (None, why). A file of ids, or ids joined by commas."""
    if os.path.isfile(value):
        with open(value, encoding="utf-8") as stream:
            items = [line.strip() for line in stream
                     if line.strip() and not line.startswith("#")]
    else:
        items = [item.strip() for item in value.split(",") if item.strip()]
        if any("/" in item for item in items):
            return None, "the installed list %s is no file and holds a path" % value
    return items, ""


def cmd_wording_check(args):
    ctx = Context(args)
    # A data file silent on the trial state counts as on; an unreadable one tells nothing, so only
    # the flag can turn the state on then, and a could-not-check fails the install.
    data_trial = ctx.data.get("trial", True) if ctx.data else False
    trial = bool(args.trial or (data_trial and args.installed_only is not None))
    if ctx.absent:
        print("RULE REGISTER · wording check: not applicable (no data file, as in a fresh public copy)")
        return 0
    print("RULE REGISTER · wording check · %s%s" % (ctx.today, " · trial state on" if trial else ""))

    def could_not(why):
        print("PROBE FAILED: could not check: " + why)
        if trial:
            print("TRIAL: would have blocked the install: could not check")
            return 0
        return 2

    if ctx.problem:
        return could_not(ctx.problem)
    listed = None
    if args.installed_only is not None:
        listed, why = installed_ids(args.installed_only)
        if listed is None:
            return could_not(why)
        # A retired row was placed by going: the seed names those, and they have no row to compare.
        known = set(ctx.data.get("retired_rows") or [])
        for row in ctx.rows:
            known |= names_of(row)
        unknown = set(listed) - known
        if unknown:
            # One unknown id means part of what was placed goes unchecked, however many others match.
            return could_not("listed rows absent from the register: " + ", ".join(sorted(unknown)))
    result = wording_pass(ctx)
    print_wording(result)
    if not result.control_ok:
        if trial:
            print("TRIAL: would have blocked the install: could not check")
            return 0
        return 2
    if listed is None and not args.trial:
        return 0
    chosen = set(listed) if listed is not None else None
    selected = [row for row in ctx.rows if chosen is None or names_of(row) & chosen]
    selected_ids = {row.get("id") for row in selected}
    blocked = [m for m in result.misses if m.row_id in selected_ids]
    # A home refused unread could not be checked, and a could-not-check fails an install.
    refused = [(row_id, rel) for row_id, rel in result.refused if row_id in selected_ids]
    unchecked = sum(1 for row_id, _ in result.listed if row_id in selected_ids)
    wordings = sum(len(approved_of(row)) for row in selected)
    for row_id, home in [(m.row_id, m.home) for m in blocked] + refused:
        print("%s %s · %s" % ("TRIAL: would have blocked the install:" if trial else "BLOCKED:",
                              row_id, home))
    failing = bool(blocked or refused)
    print("INSTALL: %s listed as just placed, holding %d approved wordings: %d of them missed, %d "
          "refused; %d rows %s; %s" % (
              "all rows" if chosen is None else str(len(chosen)), wordings, len(blocked), len(refused),
              unchecked, LISTED, "the trial state blocks nothing" if trial else
              "this fails the install" if failing else "nothing fails the install"))
    return 1 if failing and not trial else 0


# ---- what the pass reads from the wiki ---------------------------------------------------------

Page = collections.namedtuple("Page", "rel flagged sources body")


def frontmatter_of(raw):
    match = FRONTMATTER.match(raw)
    return (match.group(0), raw[match.end():]) if match else ("", raw)


def field_value(front, name):
    """A frontmatter field's text, with any indented continuation lines joined."""
    lines = front.split("\n")
    for index, line in enumerate(lines):
        if line.startswith(name + ":"):
            parts = [line[len(name) + 1:].strip()]
            for following in lines[index + 1:]:
                if following[:1] in (" ", "\t") or following.startswith("- "):
                    parts.append(following.strip())
                else:
                    break
            return " ".join(part for part in parts if part)
    return None


def source_items(value):
    if not value:
        return []
    value = value.strip()
    if value.startswith("["):
        value = value.strip("[]")
    items = re.findall(r'"[^"]*"|\'[^\']*\'|[^,]+', value.replace(" - ", ","))
    cleaned = (item.strip().lstrip("- ").strip("\"' ") for item in items)
    return [item for item in cleaned if item]


def read_pages(vault):
    pages = []
    for rel in vault.walk("wiki"):
        if rel.endswith(".md"):
            raw = vault.raw(rel)
            if raw is not None:
                front, body = frontmatter_of(raw.replace("\r\n", "\n"))
                pages.append(Page(rel, field_value(front, "flagged"),
                                  source_items(field_value(front, "sources")), body))
    return pages


def fingerprint(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprints_of(vault, rels):
    prints = {}
    for rel in rels:
        if never_read(rel):
            continue
        try:
            prints[rel] = fingerprint(vault.path(rel))
        except OSError:
            pass
    return prints


def cited_files(vault, pages):
    """Each page's cited sources and named files, keeping only vault files that exist."""
    every = set()
    for top in (".claude", "raw", "output", "wiki", "assets"):
        every.update(vault.walk(top))
    for rel in os.listdir(vault.root):
        if rel != ".DS_Store" and os.path.isfile(os.path.join(vault.root, rel)):
            every.add(rel)
    by_file, unresolved, cited_pages = collections.defaultdict(set), 0, 0
    for page in pages:
        named = set()
        for item in page.sources:
            rel = vault.canonical(item)
            if rel == DATA_REL:
                continue   # the audit's own record changes it, so citing it says nothing of a change
            if rel in every and not never_read(rel):
                named.add(rel)
            else:
                unresolved += 1
        for token in BACKTICKED.findall(page.body):
            token = re.sub(r"[:§#].*$", "", token.strip())
            if token and " " not in token:
                rel = vault.canonical(token) if not token.startswith("~") else token
                if rel in every and not never_read(rel) and rel not in NOT_A_NAMED_SOURCE:
                    named.add(rel)
        named.discard(page.rel)
        if named:
            cited_pages += 1
        for rel in named:
            by_file[rel].add(page.rel)
    return by_file, unresolved, cited_pages


def readmes_of(vault):
    """Every folder README outside the wiki; the attic is skipped by the walk."""
    found = []
    for top in sorted(os.listdir(vault.root)):
        if top in WALK_SKIP or top in ("wiki", "attic", "raw"):
            continue
        if os.path.isdir(os.path.join(vault.root, top)):
            found.extend(rel for rel in vault.walk(top) if os.path.basename(rel) == "README.md")
    return found


def holds_no_rule(rel):
    """A page that lists or records, and holds no rule of its own: a dated record, a registry, and
    the register's own page, which repeats the rulings it lists."""
    return is_dated_record(rel) or rel in REGISTRIES or rel == PAGE_REL


def rule_holding_routes(ctx, pages):
    """Pages that hold rules, each with how it is known: a row's home, named by the data, a dated ruling."""
    routes = {}
    for row in ctx.rows:
        rel = ctx.vault.canonical((row.get("home") or {}).get("file") or "")
        if (rel and rel not in ALWAYS_ON and not is_dated_record(rel) and not os.path.isabs(rel)
                and not row.get("section_row")):
            routes.setdefault(rel, "a row's home")
    for rel in (ctx.data or {}).get("rule_holding_pages") or []:
        routes.setdefault(ctx.vault.canonical(rel), "named by the data")
    for page in pages:
        if not holds_no_rule(page.rel) and PAGE_HAS_RULING.search(page.body):
            routes.setdefault(page.rel, "a dated ruling")
    return routes


def rule_holding_files(ctx, pages):
    return set(rule_holding_routes(ctx, pages))


def rulings_by_home(ctx):
    """Dated rulings in the register's homes, keyed (file, section). Dated records stay out."""
    homes = set(ALWAYS_ON)
    for row in ctx.rows:
        if not row.get("section_row"):
            homes.add(ctx.vault.canonical((row.get("home") or {}).get("file") or ""))
    homes.update(ctx.vault.canonical(rel) for rel in (ctx.data or {}).get("rule_holding_pages") or [])
    found = collections.defaultdict(list)
    for rel in sorted(home for home in homes if home and not is_dated_record(home)):
        for block in ctx.vault.blocks(rel):
            for date, span in ruling_marks(block.text):
                # By its marker, so that rewording the rule's other words is no new ruling.
                ruling_id = hashlib.sha256(("%s|%s|%s|%s" % (
                    rel, block.section, date, span)).encode()).hexdigest()[:16]
                found[(rel, block.section)].append({"id": ruling_id, "date": date,
                                                    "text": block.text, "line": block.line})
    return found


# ---- the weekly listings -----------------------------------------------------------------------

class Report:
    """Listing lines, each capped when printed, the count always whole."""

    def __init__(self, full):
        self.full, self.counts, self.failed = full, collections.OrderedDict(), False

    def listing(self, lines, capped=True):
        shown = lines if self.full or not capped else lines[:LIST_CAP]
        for line in shown:
            print("  " + line)
        if len(shown) < len(lines):
            print("  … and %d more (--full lists them)" % (len(lines) - len(shown)))

    def probe(self, what):
        self.failed = True
        print("PROBE FAILED: " + what)


def unrowed_sentences(vault, rel, row_texts):
    """Sentences of a file's blocks that no register row's text covers, row by row of the mask."""
    blocks = vault.blocks(rel)
    hay, spans, at = [], [], 0
    for block in blocks:
        spans.append((at, at + len(block.text), block))
        hay.append(block.text)
        at += len(block.text) + 1
    hay = " ".join(hay)
    covered, located = bytearray(len(hay)), 0
    for text in row_texts:
        needle = needle_of(text)
        places = positions(needle, hay) if needle else []
        located += 1 if places else 0
        for place in places:
            covered[place:place + len(needle)] = b"\1" * len(needle)
    found = []
    for begin, end, block in spans:
        pieces, piece = [], []
        for index in range(begin, end):
            if covered[index]:
                if piece:
                    pieces.append("".join(piece))
                    piece = []
            else:
                piece.append(hay[index])
        if piece:
            pieces.append("".join(piece))
        for chunk in pieces:
            for sentence in split_sentences(chunk):
                # A lone word left beside a row is no sentence; set by judgement, unmeasured.
                if len(WORD.findall(sentence)) >= 2:
                    found.append((block.line, block.section, sentence))
    return found, located, len(blocks)


def list_coverage(ctx, report, pages):
    texts_by_file = collections.defaultdict(list)
    compared, at_home, left, unread = 0, 0, [], 0
    for row in ctx.rows:
        home = row.get("home") or {}
        rel = ctx.vault.canonical(home.get("file") or "")
        for pointer in row.get("pointers") or []:
            if pointer.get("file") and pointer.get("text"):
                texts_by_file[ctx.vault.canonical(pointer["file"])].append(pointer["text"])
        if row.get("check") == "reading-only":
            unread += 1
            continue
        if row.get("section_row"):
            compared += 1
            wanted = bare_heading(home.get("section"))
            if any(bare_heading(text) == wanted for _, text in ctx.vault.headings(rel) or []):
                at_home += 1
            else:
                left.append("LEFT %s · its section has left %s" % (row.get("id"), rel))
            continue
        if row.get("text"):
            texts_by_file[rel].append(row["text"])
        compared += 1
        hay = ctx.vault.text(rel, with_notes=True) if rel else None
        needle = needle_of(row.get("text") or "")
        if hay is not None and needle and matches(needle, hay):
            at_home += 1
            continue
        note = "the home cannot be read" if hay is None else "its text is gone from the home"
        source = ctx.vault.canonical((row.get("from") or {}).get("file") or "")
        if source and source != rel:
            source_text = ctx.vault.text(source, with_notes=True)
            if source_text is not None and needle and matches(needle, source_text):
                note = "still at its source %s, so its move may have been sent back" % source
        left.append("LEFT %s · %s § %s · %s · %s" % (
            row.get("id"), rel, home.get("section") or "-", note, excerpt(row.get("text"))))
    # 1. always-on rule sentences with no register row
    missing, located, read = [], 0, 0
    for rel in ALWAYS_ON:
        found, got, blocks = unrowed_sentences(ctx.vault, rel, texts_by_file.get(rel, []))
        located += got
        read += blocks
        missing.extend("NOROW %s:%d § %s · %s" % (rel, line, section or "-", excerpt(sentence))
                       for line, section, sentence in found)
    report.counts["no_row"] = len(missing)
    print("COVERAGE 1 · always-on rule sentences with no register row: %d (control: %d blocks read "
          "in %d files, %d row texts located there)" % (len(missing), read, len(ALWAYS_ON), located))
    report.listing(missing)
    homed_here = sum(len(texts_by_file.get(rel, [])) for rel in ALWAYS_ON)
    if not read:
        report.probe("no block read in the always-on files")
    elif homed_here and not located:
        report.probe("none of %d rows homed in the always-on files was found there" % homed_here)
    # 2. register rows whose text has left its home
    report.counts["text_left"] = len(left)
    print("COVERAGE 2 · register rows whose text has left its home: %d (control: %d of %d compared "
          "rows found at home; %d rows moved into data are checked by reading only)" % (
              len(left), at_home, compared, unread))
    report.listing(left)
    if compared and not at_home:
        report.probe("none of %d compared rows was found at its home" % compared)
    # 3. fixed rules that name no failure
    fixed = [row for row in ctx.rows if row.get("shape") in ("fixed", "mechanism")]
    named = [row for row in fixed if (row.get("failure") or "").strip().lower()
             not in ("", "none named")]
    silent = [row for row in fixed if row not in named]
    report.counts["no_failure"] = len(silent)
    print("COVERAGE 3 · fixed rules that name no failure: %d (control: %d fixed or mechanism rows "
          "read of %d, %d naming one)" % (len(silent), len(fixed), len(ctx.rows), len(named)))
    report.listing(["NOFAIL %s · %s · %s · %s" % (
        row.get("id"), row.get("shape"), (row.get("home") or {}).get("file"),
        excerpt(row.get("text"))) for row in silent])
    if ctx.rows and not any(row.get("shape") for row in ctx.rows):
        report.probe("no row carries a shape, so the fixed rules cannot be told")


def compare_prints(current, recorded):
    changed = sorted(rel for rel, value in current.items() if rel in recorded and recorded[rel] != value)
    added = sorted(rel for rel in current if rel not in recorded)
    gone = sorted(rel for rel in recorded if rel not in current)
    same = sum(1 for rel, value in current.items() if recorded.get(rel) == value)
    return changed, added, gone, same


def list_rule_holding(ctx, report, pages, audit):
    files = rule_holding_files(ctx, pages) | set(readmes_of(ctx.vault))
    current = fingerprints_of(ctx.vault, sorted(files))
    recorded = audit.get("rule_files")
    if recorded is None:
        report.counts["rule_files_changed"] = "no baseline"
        print("COVERAGE 4 · rule-holding pages and READMEs changed: no baseline yet, so nothing can "
              "be said (control: %d files fingerprinted; record-audit sets the baseline)" % len(current))
        if not current:
            report.probe("no rule-holding page or README was found to fingerprint")
        return
    changed, added, gone, same = compare_prints(current, recorded)
    report.counts["rule_files_changed"] = len(changed) + len(added) + len(gone)
    print("COVERAGE 4 · rule-holding pages and READMEs changed since the audit of %s: %d changed, "
          "%d new, %d gone (control: %d files fingerprinted, %d unchanged)" % (
              audit.get("at"), len(changed), len(added), len(gone), len(current), same))
    report.listing(["CHANGED " + rel for rel in changed] + ["NEW " + rel for rel in added]
                   + ["GONE " + rel for rel in gone])
    if current and recorded and not same and not changed:
        report.probe("none of the %d recorded fingerprints matches a file now" % len(recorded))


def list_older_rulings(ctx, report, audit):
    found = rulings_by_home(ctx)
    total = sum(len(rulings) for rulings in found.values())
    crowded = sum(1 for rulings in found.values() if len(rulings) > 1)
    recorded = audit.get("rulings")
    if recorded is None:
        report.counts["newer_rulings"] = "no baseline"
        print("OLDER RULINGS · no baseline yet, so no ruling can be called new (control: %d dated "
              "rulings read in %d homes, %d homes holding two or more)" % (
                  total, len(found), crowded))
    else:
        # A count, since two rulings may carry one marker: one more than recorded means a new one,
        # and each that carries it is listed, the reader telling them apart.
        lines, carrying = [], collections.Counter(
            r["id"] for rulings in found.values() for r in rulings)
        for (rel, section), rulings in sorted(found.items()):
            for ruling in rulings:
                older = [r for r in rulings if r["date"] < ruling["date"]]
                if carrying[ruling["id"]] <= recorded.get(ruling["id"], 0) or not older:
                    continue
                words = set(WORD.findall(ruling["text"]))
                older.sort(key=lambda r: -len(words & set(WORD.findall(r["text"]))))
                shown = "; ".join("%s: %s" % (r["date"], excerpt(r["text"], 80))
                                  for r in older[:OLDER_SHOWN])
                lines.append("NEWER %s:%d § %s · %s: %s · beside %d older, closest: %s" % (
                    rel, ruling["line"], section or "-", ruling["date"],
                    excerpt(ruling["text"], 110), len(older), shown))
        report.counts["newer_rulings"] = len(lines)
        print("OLDER RULINGS · newer dated rulings beside older ones since the audit of %s: %d, for "
              "the stale-mark pass to judge (control: %d dated rulings read in %d homes, %d of them "
              "recorded before)" % (audit.get("at"), len(lines), total, len(found),
                                    sum(1 for rs in found.values() for r in rs if r["id"] in recorded)))
        report.listing(lines)
    if not total:
        report.probe("no dated ruling was read in the register's homes")


def forward_files(ctx):
    """The forward-facing files: always-on, skills, templates, helper definitions, hooks, READMEs."""
    files = list(ALWAYS_ON)
    for rel in ctx.vault.walk(".claude/skills"):
        name = os.path.basename(rel)
        if name.endswith((".md", ".txt", ".tmpl")) and not name.startswith("test_"):
            files.append(rel)
    files.extend(rel for rel in ctx.vault.walk(".claude/agents") if rel.endswith(".md"))
    files.extend(rel for rel in ctx.vault.walk(".claude/hooks")
                 if rel.endswith((".py", ".sh")) and not os.path.basename(rel).startswith("test_"))
    files.extend(readmes_of(ctx.vault))
    machine_hooks = os.path.join(store_root(), "hooks")
    if os.path.isdir(machine_hooks):
        files.extend(os.path.join(machine_hooks, name) for name in sorted(os.listdir(machine_hooks))
                     if name.endswith((".py", ".sh")) and not name.startswith("test_"))
    return sorted(set(files))


def list_copies(ctx, report):
    keyed, short = collections.defaultdict(list), []
    wordings = 0
    for row in ctx.rows:
        for wording in approved_of(row):
            needle = needle_of(wording.get("text") or "")
            if needle:
                wordings += 1
                tokens = needle.split(" ")
                entry = (row, needle)
                if len(tokens) >= 7:
                    # Inner words alone: a copy's first or last may abut a quote mark or a bracket.
                    keyed[tuple(tokens[1:6])].append(entry)
                else:
                    short.append(entry)
    files = forward_files(ctx)
    copies, carrier_lines, home_hits = [], [], 0
    carriers_by_row = {}
    for row in ctx.rows:
        carriers_by_row[row.get("id")] = {ctx.vault.canonical(c if isinstance(c, str) else c.get("file", ""))
                                          for c in row.get("carriers") or []}

    def consider(rel, row, needle, hay):
        nonlocal home_hits
        if not matches(needle, hay):
            return
        if rel == ctx.vault.canonical((row.get("home") or {}).get("file") or ""):
            home_hits += 1
        elif rel not in carriers_by_row.get(row.get("id"), ()):
            copies.append("COPY %s · %s · %s" % (row.get("id"), rel, excerpt(needle)))

    for rel in files:
        hay = ctx.vault.text(rel)
        if hay is None:
            continue
        tokens = hay.split(" ")
        seen = set()
        for gram in zip(tokens, tokens[1:], tokens[2:], tokens[3:], tokens[4:]):
            if gram in keyed and gram not in seen:
                seen.add(gram)
                for row, needle in keyed[gram]:
                    consider(rel, row, needle, hay)
        for row, needle in short:
            consider(rel, row, needle, hay)
    declared = 0
    for row in ctx.rows:
        for carrier in sorted(carriers_by_row.get(row.get("id"), ())):
            for wording in approved_of(row):
                declared += 1
                needle = needle_of(wording.get("text") or "")
                hay = ctx.vault.text(carrier)
                if hay is None or not matches(needle, hay):
                    near = closest_block(ctx.vault, carrier, None, needle) if hay else ""
                    carrier_lines.append("CARRIER %s · %s differs from its home · %s" % (
                        row.get("id"), carrier, word_diff(needle, near) if near
                        else "(no similar text there)"))
    report.counts["copies"] = len(copies)
    report.counts["carriers_differing"] = len(carrier_lines)
    print("COPIES · full copies of an approved wording on forward-facing files: %d; declared carriers "
          "differing from their home: %d of %d (control: %d wordings over %d files, %d found at their "
          "homes)" % (len(copies), len(carrier_lines), declared, wordings, len(files), home_hits))
    report.listing(copies + carrier_lines)
    if not files:
        report.probe("no forward-facing file was found")
    elif wordings and not home_hits:
        report.probe("none of %d approved wordings was found at its home by this scan" % wordings)


def clearing_of(flag):
    """(date or None, the clause that says what clears a flag, or None)."""
    clause = None
    for match in CLEAR_CLAUSE.finditer(flag):
        clause = clause or match.group(0)
        dates = dates_in(match.group(0))
        if dates:
            return max(dates), match.group(0)
    return None, clause


Flag = collections.namedtuple("Flag", "rel digest line")


def read_flags(pages, today):
    """Every flag, by what it says today: (due, ahead, event, no clause). A flag's digest is of its
    words, so a re-wrapped line is the same flag and a changed one is not."""
    due, ahead, event, unclear = [], [], [], []
    for page in pages:
        if page.flagged:
            text = page.flagged.strip().strip("\"'")
            digest = hashlib.sha256(normal(text).encode()).hexdigest()[:16]
            date, clause = clearing_of(text)
            if date and date <= today:
                due.append(Flag(page.rel, digest, "DUE %s · cleared by %s · %s" % (
                    page.rel, date, excerpt(text))))
            elif date:
                ahead.append(Flag(page.rel, digest, ""))
            elif clause:
                event.append(Flag(page.rel, digest, "EVENT %s · %s" % (page.rel, excerpt(clause))))
            else:
                unclear.append(Flag(page.rel, digest, "NOCLAUSE %s · %s" % (page.rel, excerpt(text))))
    return due, ahead, event, unclear


# Set by judgement, unmeasured: four weekly passes. Only a reader can tell that a flag's event has
# happened, so a flag still on its page comes up again this long after its last listing; a pending
# event is then not lost, and nothing repeats every week.
FLAG_RELIST_DAYS = 28


def relist_due(listed_on, today):
    """A recorded flag with no recorded listing date, or one this old, comes up again."""
    try:
        then = datetime.date.fromisoformat(listed_on)
        return (datetime.date.fromisoformat(today) - then).days >= FLAG_RELIST_DAYS
    except (TypeError, ValueError):
        return True


def flags_coming_up(pages, today):
    """The flags a pass lists, unless the audit block records them: all but those with a date ahead,
    which are not recorded either, so each comes up once its date has passed."""
    due, _, event, unclear = read_flags(pages, today)
    return due + event + unclear


def list_flags(ctx, report, pages, audit=None, all_flags=False):
    due, ahead, event, unclear = read_flags(pages, ctx.today)
    recorded = (audit or {}).get("flags") or {}
    listed_on = (audit or {}).get("flags_at") or {}
    coming = due + event + unclear
    shown = [flag for flag in coming if all_flags or recorded.get(flag.rel) != flag.digest
             or relist_due(listed_on.get(flag.rel), ctx.today)]
    report.counts["flags_due"] = len(due)
    report.counts["flags_event"] = len(event)
    report.counts["flags_no_clause"] = len(unclear)
    report.counts["flags_listed"] = len(shown)
    print("FLAGS · %d read: %d due by a date that has passed, %d naming a date ahead, %d naming an "
          "event, for the review to judge whether it has passed, %d with no clause saying what "
          "clears them; %d listed here, %d listed at an earlier audit and now only counted, unless "
          "their text changes or %d days pass (--all-flags lists them) (control: %d wiki pages read)" % (
              len(due) + len(ahead) + len(event) + len(unclear), len(due), len(ahead), len(event),
              len(unclear), len(shown), len(coming) - len(shown), FLAG_RELIST_DAYS, len(pages)))
    # Uncapped: a flag cut by a cap and then recorded would never come up at all.
    report.listing([flag.line for flag in shown], capped=False)


def list_sources(ctx, report, pages, audit):
    by_file, unresolved, cited_pages = cited_files(ctx.vault, pages)
    current = fingerprints_of(ctx.vault, sorted(by_file))
    recorded = audit.get("sources")
    if pages and any(page.sources for page in pages) and not current:
        report.probe("pages cite sources but none of them resolved to a file")
    if recorded is None:
        report.counts["sources_changed"] = "no baseline"
        print("SOURCES · no baseline yet, so nothing can be called changed (control: %d files cited "
              "or named by %d pages fingerprinted, %d cited items not resolved)" % (
                  len(current), cited_pages, unresolved))
        return
    changed, added, gone, same = compare_prints(current, recorded)
    lines = []
    for rel in changed + gone:
        names = sorted(by_file.get(rel, ()))
        lines.append("%s %s ← %d pages: %s%s" % (
            "CHANGED" if rel in current else "GONE", rel, len(names), ", ".join(names[:6]),
            " …" if len(names) > 6 else ""))
    report.counts["sources_changed"] = len(lines)
    print("SOURCES · cited or named files changed since the audit of %s: %d, naming %d pages; %d "
          "newly cited (control: %d files fingerprinted, %d unchanged, %d cited items not resolved)" % (
              audit.get("at"), len(lines), len({p for rel in changed for p in by_file[rel]}),
              len(added), len(current), same, unresolved))
    report.listing(lines)
    if current and recorded and not same and not changed:
        report.probe("none of the %d recorded fingerprints matches a file now" % len(recorded))


def rows_digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def page_state(ctx):
    try:
        with open(ctx.page_path, encoding="utf-8") as stream:
            front, _ = frontmatter_of(stream.read())
    except OSError:
        return "absent: generate writes it"
    recorded = (field_value(front, "register-rows-sha256") or "").strip("\"' ")
    return "in step with its data" if recorded == rows_digest(ctx.rows) else (
        "out of step with its data: generate brings it up to date")


def cmd_weekly(args):
    started = time.time()
    ctx = Context(args)
    report = Report(args.full)
    print("RULE REGISTER · weekly pass · %s · %s" % (
        ctx.today, "no data file" if ctx.absent else "%d rows" % len(ctx.rows)))
    pages = read_pages(ctx.vault)
    if ctx.problem:
        report.probe("could not check: " + ctx.problem)
        report.counts["wording_missed"] = "could not check"
    elif ctx.absent:
        print("WORDING · not applicable (no data file, as in a fresh public copy)")
        print("COVERAGE, OLDER RULINGS and COPIES · not applicable (no data file)")
    else:
        result = wording_pass(ctx)
        # Its reason does not change, so the weekly pass only counts such a row; --full lists it.
        print_wording(result, show_listed=args.full)
        if result.control_ok:
            report.counts["wording_missed"] = len(result.misses)
        else:
            report.failed = True
            report.counts["wording_missed"] = "could not check"
    audit = (ctx.data or {}).get("audit") or {}
    if ctx.data:
        print("PAGE · " + page_state(ctx))
        list_coverage(ctx, report, pages)
        list_rule_holding(ctx, report, pages, audit)
        list_older_rulings(ctx, report, audit)
        list_copies(ctx, report)
    if pages:
        list_flags(ctx, report, pages, audit, args.all_flags)
        if ctx.absent:
            print("  with no data file, no audit block records a listing, so these come up at every pass")
    else:
        print("FLAGS · not applicable (no wiki pages)")
    if ctx.data:
        list_sources(ctx, report, pages, audit)
    elif not ctx.problem:
        print("SOURCES · not applicable (no data file holds a baseline)")
    print("SUMMARY %s seconds=%.1f" % (" ".join(
        "%s=%s" % (key, str(value).replace(" ", "-")) for key, value in report.counts.items()),
        time.time() - started))
    return 2 if report.failed else 0


def cmd_record_audit(args):
    ctx = Context(args)
    if ctx.absent:
        print("record-audit: not applicable (no data file)")
        return 0
    if ctx.problem:
        return probe_failed(ctx.problem)
    pages = read_pages(ctx.vault)
    by_file, _, _ = cited_files(ctx.vault, pages)
    rule_files = rule_holding_files(ctx, pages) | set(readmes_of(ctx.vault))
    flags = flags_coming_up(pages, ctx.today)
    earlier = (ctx.data.get("audit") or {}).get("flags") or {}
    earlier_on = (ctx.data.get("audit") or {}).get("flags_at") or {}
    audit = {"at": ctx.today,
             "rule_files": fingerprints_of(ctx.vault, sorted(rule_files)),
             "sources": fingerprints_of(ctx.vault, sorted(by_file)),
             "rulings": dict(sorted(collections.Counter(
                 r["id"] for rs in rulings_by_home(ctx).values() for r in rs).items())),
             "flags": {flag.rel: flag.digest for flag in flags},
             "flags_at": {flag.rel: earlier_on[flag.rel]
                          if earlier.get(flag.rel) == flag.digest and not relist_due(earlier_on.get(flag.rel), ctx.today)
                          else ctx.today for flag in flags}}
    if not (audit["rule_files"] or audit["sources"]):
        return probe_failed("nothing to fingerprint, so no baseline is recorded")
    ctx.data["audit"] = audit
    write_atomic(ctx.data_path, json.dumps(ctx.data, ensure_ascii=False, indent=1) + "\n")
    print("record-audit %s: %d rule-holding files, %d cited or named files, %d dated rulings, %d flags "
          "recorded" % (ctx.today, len(audit["rule_files"]), len(audit["sources"]),
                        sum(audit["rulings"].values()), len(flags)))
    # Named, so a flag set or come due since the pass, recorded here and never listed, can be seen.
    fresh = sorted(flag.rel for flag in flags if earlier.get(flag.rel) != flag.digest)
    if fresh:
        print("  flags recorded for the first time, or with new text; each should be one the pass "
              "listed: " + ", ".join(fresh))
    return 0


# ---- the first rows, from the map --------------------------------------------------------------

def read_jsonl(path):
    with open(path, encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def sentence_slice(rule, first, last):
    """The exact text of sentences first..last of a rule row. Offsets may end inclusively."""
    text, sentences = rule.get("text") or "", rule.get("sentences") or []
    if not sentences:
        return text
    inclusive = sentences[-1][1] == len(text) - 1 and len(sentences[-1]) == 2
    return text[sentences[first][0]:sentences[last][1] + (1 if inclusive else 0)]


def status_of(rule, index, tracing):
    """A sentence's wording status: the tracing's refinement, else what the home's mark shows."""
    record = tracing.get((rule.get("id"), index))
    if record:
        return record.get("status") or "approved-untraced", record
    if rule.get("wording") == "approved-record":
        return "approved-record", {"record": rule.get("record")}
    if index in (rule.get("marks") or []) or rule.get("wording") == "approved-untraced":
        return "approved-untraced", None
    return "agent", None


def wording_fields(rule, first, last, tracing, text_override=None):
    """The row's wording status, and its approved wordings: runs of sentences with a record."""
    runs, current, kinds = [], None, set()
    for index in range(first, last + 1):
        status, record = status_of(rule, index, tracing)
        kinds.add(status)
        if status == "approved-record":
            if current and current["last"] == index - 1:
                current["last"] = index
            else:
                current = {"first": index, "last": index, "record": record}
                runs.append(current)
    status = ("approved-record" if "approved-record" in kinds else
              "approved-untraced" if "approved-untraced" in kinds else "agent")
    if text_override is not None and runs:
        approved = [{"text": text_override, "record": runs[0]["record"], "seam": True}]
    else:
        approved = [{"text": sentence_slice(rule, run["first"], run["last"]).strip(),
                     "record": run["record"]} for run in runs]
    return status, approved


def home_from(to, rules, vault_blocks=None):
    """A span's receiving home, from its `to` (SPEC section 3)."""
    if "data" in to:
        return {"file": to["data"], "entry": to.get("entry")}, "reading-only"
    if "new_page" in to:
        return {"file": to["new_page"], "section": to.get("section")}, None
    home = {"file": to.get("file"), "section": bare_heading(to.get("section")) or None}
    if not home["section"] and to.get("after"):
        anchor = normal(to["after"])
        for rule in rules.values():
            if rule.get("file") == home["file"] and anchor and anchor in normal(rule.get("text") or ""):
                home["section"] = bare_heading(rule.get("heading_path")) or None
                break
    return home, None


def origin_of(rule, first, last):
    """Where a span came from: the owner's mark on it with its dates, or nothing recorded yet."""
    marks = rule.get("marks") or []
    texts = rule.get("mark_text") or []
    inside = [i for i, mark in enumerate(marks) if first <= mark <= last]
    if not inside:
        return {"kind": "not recorded", "dates": []}
    phrases = sorted({str(texts[i]) for i in inside if isinstance(texts, list) and i < len(texts)})
    dates = sorted({date for phrase in phrases for date in dates_in(phrase)})
    return {"kind": "owner", "mark": phrases[:3], "dates": dates or list(rule.get("ruling_dates") or [])}


def skill_section_rows(vault):
    """One row per level-two section of each skill's SKILL.md. Its steps are read at their moment
    and never moved, so a row names the place and holds no text. The level is set by judgement,
    unmeasured: a section is the unit a skill's reader opens."""
    rows, seen = [], set()
    for rel in vault.walk(".claude/skills"):
        if os.path.basename(rel) != "SKILL.md":
            continue
        for level, heading in vault.headings(rel) or []:
            key = "%s § %s" % (rel, heading)
            if level == 2 and key not in seen:
                seen.add(key)
                rows.append({"id": key, "map_row": None, "home": {"file": rel, "section": heading},
                             "section_row": True, "text": "", "wording": "agent", "approved": [],
                             "origin": {"kind": "not recorded", "dates": []},
                             "moment": "skill-step", "kept_by": "text", "pointers": [], "carriers": []})
    return rows


def is_waiting(name):
    """A waiting text's row in the rule list (SPEC section 2), which has no home of its own."""
    return str(name).startswith("W-")


def waiting_carried(lines, rules):
    """{id(span): the waiting texts it carries}, as the map reads a carrier: a reword or merge that
    names the text in known_edit or group_with, or holds it whole in its new text. Only a text with
    no paste of its own counts: one the map keeps, or one a known edit delivers."""
    keeping = {span.get("row") for span in lines
               if is_waiting(span.get("row")) and span.get("action") == "keep"}
    wholes = {name: needle_of(rules[name].get("text") or "") for name in keeping if name in rules}
    carries = {}
    for span in lines:
        if span.get("proposal") or not (span.get("action") == "reword"
                                        or ("sources" in span and "row" not in span)):
            continue
        linked = span.get("group_with") if isinstance(span.get("group_with"), list) else []
        new = normal(span.get("new") or "")
        held = {name for name, text in wholes.items()
                if name in linked or name == span.get("known_edit") or (text and matches(text, new))}
        if span.get("action") == "reword" and is_waiting(span.get("known_edit")):
            held.add(span["known_edit"])
        if held:
            carries[id(span)] = sorted(held)
    return carries


def row_common(span, rule):
    fields = {key: span.get(key) for key in ("principle", "whose", "layer", "shape", "failure",
                                             "moment")}
    for key in ("addition_only", "disagree", "seam", "proposal"):
        if key in span:
            fields[key] = span[key]
    mechanism = span.get("shape") == "mechanism"
    fields["kept_by"] = span.get("kept_by") or (
        "hook" if span.get("moment") == "hook" else "script" if mechanism else "text")
    fields["carriers"] = span.get("carriers") or []
    fields["lifecycle_row"] = span.get("lifecycle_row")
    pointer = span.get("pointer")
    fields["pointers"] = [{"file": rule.get("file"), "text": pointer}] if pointer else []
    return fields


def cmd_seed(args):
    args.map = [path for item in args.map for path in item.split(",") if path]
    for path in [args.rules, args.tracing] + args.map:
        if not os.path.isfile(path):
            return probe_failed("seed input is missing: %s" % path)
    if args.out and os.path.exists(args.out):
        return probe_failed("%s already exists; a seed writes only where nothing is" % args.out)
    today = args.today or datetime.date.today().isoformat()
    rule_list = read_jsonl(args.rules)
    rules = {rule.get("id"): rule for rule in rule_list}
    tracing = {(t.get("row"), t.get("sentence")): t for t in read_jsonl(args.tracing)}
    lines = []
    for path in args.map:
        lines.extend(read_jsonl(path))
    if not rule_list or not lines:
        return probe_failed("the rule list or the map holds no rows")
    merges = {line["merge_id"]: line for line in lines if "merge_id" in line and "new" in line}
    rows, retired, placed, anomalies = [], 0, set(), []
    carries = waiting_carried(lines, rules)
    carried = {name for held in carries.values() for name in held}
    skipped_carried, proposed, compared = set(), [], set()

    def stay(rule, first, last, span):
        """A row that stays at its source with its words: a keep, a proposal, a seam-free reword.
        A waiting text has no source, so it stays at the home its row states."""
        status, approved = wording_fields(rule, first, last, tracing)
        row = {"id": "%s#%d-%d" % (rule["id"], first, last), "map_row": rule["id"],
               "home": {"file": rule.get("file") or rule.get("home_file"),
                        "section": bare_heading(rule.get("heading_path")) or None},
               "text": sentence_slice(rule, first, last).strip(), "wording": status,
               "approved": approved, "origin": origin_of(rule, first, last)}
        row.update(row_common(span, rule))
        return row

    def words_carried(span, new):
        """The approved waiting texts this span installs whole: the words and the approval are the
        W row's, and the old words' record never passes to them."""
        found = []
        for name in carries.get(id(span), []):
            waiting = rules.get(name) or {}
            text = (waiting.get("text") or "").strip()
            if waiting.get("wording") == "approved-record" and matches(needle_of(text), normal(new)):
                found.append({"text": text, "record": waiting.get("record"), "known_edit": name})
                compared.add(name)
        return found

    for span in lines:
        if "new" in span and "merge_id" in span:
            sources = span.get("sources") or []
            if span.get("proposal"):
                continue
            home, check = home_from(span.get("to") or {}, rules)
            row = {"id": span["merge_id"], "map_row": span["merge_id"], "home": home,
                   "text": span["new"].strip(), "wording": "agent", "approved": [],
                   "origin": {"kind": "not recorded", "dates": []},
                   "merged_from": [source.get("row") for source in sources]}
            first_source = rules.get(sources[0].get("row")) if sources else None
            row.update(row_common(span, first_source or {}))
            if carries.get(id(span)):
                row["carries"] = carries[id(span)]
                row["approved"] = words_carried(span, span["new"])
                row["wording"] = "approved-record" if row["approved"] else "agent"
            if check:
                row["check"] = check
                row["approved"] = []
            rows.append(row)
            continue
        name = span.get("row")
        rule = rules.get(name)
        if rule is None and "old" in span:   # a designer's own row (SPEC section 3, X-NEW)
            rule = {"id": name, "file": span.get("file"), "text": span["old"], "sentences": []}
            rules[name] = rule
        if rule is None:
            anomalies.append("%s: the map names a row the list does not hold" % name)
            continue
        # A waiting text the map words itself is filed by its span, though the list found no text.
        filed_words = span.get("new", "").strip() if span.get("action") == "file" else ""
        if rule.get("status") in ("gone", "not-found") and not filed_words:
            continue
        bounds = span.get("s") or [0, max(0, len(rule.get("sentences") or [0]) - 1)]
        first, last = bounds[0], bounds[1]
        if last >= max(1, len(rule.get("sentences") or [0])):
            anomalies.append("%s: span %s is outside the row's sentences" % (name, bounds))
            continue
        placed.add(name)
        action = span.get("action")
        if is_waiting(name) and action in ("keep", "file") and name in carried:
            skipped_carried.add(name)   # its words have their row at the span that carries them
            continue
        if is_waiting(name) and span.get("proposal") and action != "keep":
            proposed.append(name)       # not installed: no home to name, so no row yet
            continue
        if "merge_id" in span:
            merge = merges.get(span["merge_id"])
            if merge is None:
                anomalies.append("%s: its merge %s has no line" % (name, span["merge_id"]))
            elif merge.get("proposal"):
                rows.append(stay(rule, first, last, span))
            continue
        if action == "retire":
            retired += 1
        elif action == "keep" or span.get("proposal"):
            row = stay(rule, first, last, span)
            if row["home"]["file"]:
                rows.append(row)
            else:
                anomalies.append("%s: kept with no home to stay in and nothing carrying it" % name)
        elif action in ("move", "file"):
            home, check = home_from(span.get("to") or {}, rules)
            if not home.get("file"):
                anomalies.append("%s: a %s with no receiving file, kept at its source" % (name, action))
                rows.append(stay(rule, first, last, span))
                continue
            status, approved = wording_fields(rule, first, last, tracing)
            # A file span's own words are what installs: the map's text for a row with none, or
            # the row's text with only its placeholders filled.
            for wording in approved if filed_words else []:
                wording["text"] = filed_words
            row = {"id": "%s#%d-%d" % (name, first, last), "map_row": name, "home": home,
                   "from": {"file": rule.get("file"), "section": bare_heading(rule.get("heading_path")) or None},
                   "text": filed_words or sentence_slice(rule, first, last).strip(), "wording": status,
                   "approved": approved, "origin": origin_of(rule, first, last)}
            row.update(row_common(span, rule))
            if check:
                row["check"] = check
                row["approved"] = []
            rows.append(row)
        elif action == "reword":
            new = span.get("new", "").strip()
            status, approved = wording_fields(rule, first, last, tracing, text_override=new)
            known = span.get("known_edit")
            taken = words_carried(span, new)
            if known is not None:
                # A known edit installs a settled text (SPEC section 3 and the map's check): the
                # words its W row approves are what is checked. Where that row records no approval
                # of those very words nothing is, and the old words' record never passes to them,
                # so words the home marks as the owner's stay marked with no record claimed.
                waiting = rules.get(known) if is_waiting(known) else None
                if waiting is None:
                    anomalies.append("%s: its known edit %s is no waiting text in the list, kept at "
                                     "its source" % (name, known))
                    rows.append(stay(rule, first, last, span))
                    continue
                if not matches(needle_of(waiting.get("text") or ""), normal(new)):
                    anomalies.append("%s: its new text does not hold its known edit %s word for word, "
                                     "kept at its source" % (name, known))
                    rows.append(stay(rule, first, last, span))
                    continue
                approved, status = [], "approved-untraced" if status != "agent" else "agent"
            elif status != "agent" and not span.get("seam"):
                # A reword of owner-marked text installs only as a seam (SPEC section 3).
                anomalies.append("%s: a reword of owner-marked text with no proposal or seam mark, "
                                 "kept at its source" % name)
                rows.append(stay(rule, first, last, span))
                continue
            if taken:
                approved, status = approved + taken, "approved-record"
            home, check = (home_from(span["to"], rules) if span.get("to") else
                           ({"file": rule.get("file"),
                             "section": bare_heading(rule.get("heading_path")) or None}, None))
            row = {"id": "%s#%d-%d" % (name, first, last), "map_row": name, "home": home,
                   "text": new, "wording": status, "approved": approved,
                   "origin": origin_of(rule, first, last)}
            row.update(row_common(span, rule))
            if carries.get(id(span)):
                row["carries"] = carries[id(span)]
            if known is not None:
                row["known_edit"] = known
                if rules[known].get("approval_note"):
                    row["wording_note"] = rules[known]["approval_note"]
            if check:
                row["check"] = check
                row["approved"] = []
            rows.append(row)
        else:
            anomalies.append("%s: unknown action %r" % (name, action))
    # A link alone carries a text, so an approved one no carrier holds whole would go unchecked.
    for name in sorted(skipped_carried - compared):
        if rules[name].get("wording") == "approved-record":
            anomalies.append("%s: approved, and no row that carries it holds it word for word, so "
                             "nothing would check it" % name)
    # Approved words in a dated record stay there as its record. The check never reads such a file,
    # so the row is listed with that reason, keeping what it would compare, and fails no install.
    for row in rows:
        rel = (row.get("home") or {}).get("file") or ""
        if row.get("approved") and is_dated_record(rel):
            row["listed"], row["approved"] = row["approved"], []
            row["wording"] = LISTED
            row["wording_reason"] = ("its home, %s, is a dated record, which the wording check never "
                                     "reads, so its approved words stand there unchecked" % rel)
    sections = []
    if args.skill_sections:
        sections = skill_section_rows(Vault(vault_root(args)))
        if not sections:
            return probe_failed("--skill-sections found no section under %s" % vault_root(args))
        rows.extend(sections)
    for row in rows:
        row["text_sha256"] = hashlib.sha256(needle_of(row.get("text") or "").encode()).hexdigest()
    unplaced = sorted(r.get("id") for r in rule_list
                      if (r.get("kind") == "rule" or str(r.get("id", "")).startswith("W-"))
                      and r.get("id") not in placed and r.get("status") not in ("gone", "not-found"))
    # A row whose every span retired has no row left, yet an install's LIST may rightly name it.
    retired_rows = {span.get("row") for span in lines if span.get("action") == "retire"}
    document = {"schema_version": SCHEMA_VERSION, "trial": True,
                "page": {"created": today, "audited": today, "confidence": "medium"},
                "rule_holding_pages": [],
                "retired_rows": sorted(retired_rows - {row.get("map_row") for row in rows}),
                "rows": rows}
    summary = collections.Counter(row.get("wording") for row in rows)
    out = sys.stderr if not args.out else sys.stdout
    print("seed: %d rows from %d map lines and %d skill sections: %d approved with a record, %d "
          "approved untraced, %d %s, %d in the agent's wording; %d spans retired; %d waiting texts "
          "carried by another row; %d waiting texts proposed and not placed; %d rule rows unplaced; "
          "%d anomalies" % (
              len(rows), len(lines), len(sections), summary["approved-record"],
              summary["approved-untraced"], summary[LISTED], LISTED, summary["agent"], retired,
              len(skipped_carried), len(set(proposed)), len(unplaced), len(anomalies)), file=out)
    if proposed:
        print("  proposed, no row until each has a home: " + ", ".join(sorted(set(proposed))), file=out)
    for item in anomalies + ["unplaced: " + name for name in unplaced[:LIST_CAP]]:
        print("  " + item, file=out)
    text = json.dumps(document, ensure_ascii=False, indent=1) + "\n"
    if args.out:
        write_atomic(args.out, text, keep_mode=False)
        print("seed: wrote %s" % args.out)
    else:
        sys.stdout.write(text)
    return 1 if anomalies else 0


# ---- the rules already in their right home -----------------------------------------------------

def pointed_pages(ctx, pages):
    """Wiki pages a forward-facing file names, by path or link: the moment a page's rule is read."""
    rels = {page.rel for page in pages}
    by_name = {os.path.splitext(os.path.basename(rel))[0]: rel for rel in rels}
    found = set()
    for rel in forward_files(ctx):
        text = ctx.vault.raw(rel)
        if text is not None:
            found.update(path for path in WIKI_PATH.findall(text) if path in rels)
            found.update(by_name[name.strip()] for name in WIKILINK.findall(text)
                         if name.strip() in by_name)
    return found


def inventory_of(ctx, pages):
    """Every page and README the in-place listing reads, each with how it came in. Beyond the pages
    known to hold rules, a rule with no date mark may stand on a page a forward-facing file names,
    or on any page of the framework's own folders."""
    routes = rule_holding_routes(ctx, pages)
    for rel in readmes_of(ctx.vault):
        routes.setdefault(rel, "a README")
    for rel in sorted(pointed_pages(ctx, pages)):
        if not holds_no_rule(rel):
            routes.setdefault(rel, "named by a forward-facing file")
    for page in pages:
        if page.rel.startswith(FRAMEWORK_FOLDERS) and not holds_no_rule(page.rel):
            routes.setdefault(page.rel, "in the framework's folders")
    return routes


def cmd_in_place(args):
    ctx = Context(args)
    if ctx.problem:
        return probe_failed(ctx.problem)
    pages = read_pages(ctx.vault)
    routes = inventory_of(ctx, pages)
    named = {ctx.vault.canonical(rel) for rel in (ctx.data or {}).get("rule_holding_pages") or []}
    texts = collections.defaultdict(list)
    for row in ctx.rows:
        texts[ctx.vault.canonical((row.get("home") or {}).get("file") or "")].append(row.get("text") or "")
    kinds, rule_worded = collections.Counter(), 0
    for rel in sorted(routes):
        # A page or README is read whole. A skill's steps are listed by section and a script's rules
        # by the map's rows, so a row's home among those gives only its dated rulings.
        whole = rel.startswith("wiki/") or os.path.basename(rel) == "README.md" or rel in named
        for block in ctx.vault.blocks(rel):
            dated = ruling_marks(block.text)
            worded = RULE_WORD.search(block.text)
            rule_worded += 1 if worded else 0
            if (dated or whole) and not any(
                    matches(needle_of(text), block.text) for text in texts.get(rel, []) if text):
                kind = "dated" if dated else "rule word" if worded else "plain"
                kinds[kind] += 1
                print("CANDIDATE %s:%d § %s · %s · %s" % (rel, block.line, block.section or "-", kind,
                                                          excerpt(block.text, 240)))
    print("IN PLACE: %d candidates on the %d pages and READMEs of the inventory, for one helper to "
          "read: %d dated, %d with a rule word, %d plain (control: %d wiki pages read)" % (
              sum(kinds.values()), len(routes), kinds["dated"], kinds["rule word"], kinds["plain"],
              len(pages)))
    came_in = collections.Counter(routes.values())
    print("INVENTORY · how each came in: " + (", ".join(
        "%d %s" % (count, route) for route, count in sorted(came_in.items())) or "none"))
    records, left, left_worded = 0, collections.Counter(), collections.Counter()
    for page in pages:
        if page.rel in routes:
            continue
        if holds_no_rule(page.rel):
            records += 1
            continue
        folder = "/".join(page.rel.split("/")[:2])
        left[folder] += 1
        if any(RULE_WORD.search(block.text) for block in ctx.vault.blocks(page.rel)):
            left_worded[folder] += 1
    print("INVENTORY · left out of the %d wiki pages read: %d records and registries, and %d others: %s" % (
        len(pages), records, sum(left.values()), ", ".join(
            "%s %d (%d with a rule word)" % (folder, count, left_worded[folder])
            for folder, count in sorted(left.items())) or "none"))
    if not routes:
        return probe_failed("no rule-holding page or README was found")
    if pages and not (rule_worded or sum(left_worded.values())):
        return probe_failed("no page read holds a rule word, so the sorting of candidates is unproved")
    return 0


# ---- the weekly clean-up's listing -------------------------------------------------------------

def human(size):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return "%.1f %s" % (size, unit) if unit != "B" else "%d B" % size
        size /= 1024.0


def tree_stats(path, cutoff):
    """(bytes, newest modification time), no links followed, stopping at the first file past cutoff."""
    try:
        info = os.lstat(path)
    except OSError:
        return 0, 0.0
    size, newest = info.st_size, info.st_mtime
    if os.path.isdir(path) and not os.path.islink(path):
        for folder, subdirs, names in os.walk(path):
            for name in subdirs + names:
                try:
                    info = os.lstat(os.path.join(folder, name))
                except OSError:
                    continue
                size += info.st_size
                newest = max(newest, info.st_mtime)
                if newest >= cutoff:
                    return size, newest
    return size, newest


def holds_backup_or_package(path):
    """A folder holding a backup or a staged package, looked for two levels down."""
    if not os.path.isdir(path):
        return False
    try:
        top = os.listdir(path)
    except OSError:
        return False
    if HELD_NAMES & set(top) or ("new" in top and "base" in top):
        return True
    for name in top:
        inner = os.path.join(path, name)
        if os.path.isdir(inner):
            try:
                below = set(os.listdir(inner))
            except OSError:
                continue
            if HELD_NAMES & below or {"new", "base"} <= below or name == "install" and "record.jsonl" in below:
                return True
    return False


def open_entries(text):
    """A register's open entries: its Open section, or the whole page if it has no such section."""
    opened = text.find("\n## Open")
    if opened < 0:
        return text
    closed = text.find("\n## ", opened + 1)
    return text[opened:closed] if closed >= 0 else text[opened:]


def named_tokens(ctx, pages):
    """Every path-like word of what can keep a record: the wiki, the calendar, the open entries.

    The log and a closed register entry keep nothing: the log names every run ever made.
    """
    register, log = DATED_FILES[2], DATED_FILES[0]
    texts = [page.body + " " + str(page.flagged) + " " + " ".join(page.sources)
             for page in pages if page.rel not in (register, log)]
    entries = ctx.vault.raw(register)
    if entries is not None:
        texts.append(open_entries(entries))
    calendar = ctx.vault.raw("CALENDAR.md")
    if calendar is not None:
        texts.append(calendar)
    tokens = set()
    for text in texts:
        tokens.update(re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]*", text))
    grown = set()
    for token in tokens:
        token = token.rstrip("._-")
        grown.add(token)
        if token.startswith("run-"):
            pieces = token.split("-")
            for count in range(3, len(pieces)):
                grown.add("-".join(pieces[:count]))
    return grown, len(texts), calendar is not None


def cmd_cleanup(args):
    ctx = Context(args)
    root = os.path.realpath(args.store) if args.store else store_root()
    pages = read_pages(ctx.vault)
    tokens, read, has_calendar = named_tokens(ctx, pages)
    print("CLEAN-UP · %s · older than %d days, named by no wiki page or calendar line; it lists, and "
          "the session deletes only what the owner approves" % (ctx.today, args.days))
    stores = {name: os.path.join(root, name) for name in ("stages", "spawn-records", "handoffs", "backups")}
    for name, path in stores.items():
        if os.path.isdir(path):
            run = subprocess.run(["du", "-sk", path], capture_output=True, text=True)
            size = int(run.stdout.split()[0]) * 1024 if run.returncode == 0 and run.stdout else 0
            print("SIZE %s · %s" % (name, human(size)))
        else:
            print("SIZE %s · no such store" % name)
    items = []
    if os.path.isdir(stores["stages"]):
        for name in sorted(os.listdir(stores["stages"])):
            if name == ".DS_Store":
                continue
            kind = "batch store" if "batch" in name else "run folder"
            items.append((kind, name, [os.path.join(stores["stages"], name)], [name]))
    if os.path.isdir(stores["spawn-records"]):
        groups = collections.defaultdict(list)
        for name in os.listdir(stores["spawn-records"]):
            if name in WALK_SKIP or name == ".DS_Store":
                continue
            match = SPAWN_GROUP.match(name)
            groups[match.group(1) if match else os.path.splitext(name)[0]].append(
                os.path.join(stores["spawn-records"], name))
        items.extend(("helper records", group, sorted(paths), [group])
                     for group, paths in sorted(groups.items()))
    if os.path.isdir(stores["handoffs"]):
        for name in sorted(os.listdir(stores["handoffs"])):
            if name == ".DS_Store":
                continue
            stem = os.path.splitext(name)[0]
            items.append(("hand-off file", name, [os.path.join(stores["handoffs"], name)],
                          [name, stem]))
    if os.path.isdir(stores["backups"]):
        for name in sorted(os.listdir(stores["backups"])):
            if name == ".DS_Store":
                continue
            items.append(("install backup", name, [os.path.join(stores["backups"], name)], [name]))
    transcripts = None
    if args.no_transcripts:
        print("TRANSCRIPTS · not read in this run, by --no-transcripts")
    else:
        slug = re.sub(r"[^A-Za-z0-9]", "-", ctx.vault.root)
        transcripts = args.projects or os.path.join(os.path.expanduser("~"), ".claude", "projects", slug)
        if os.path.isdir(transcripts):
            for name in sorted(os.listdir(transcripts)):
                if name.endswith(".jsonl"):
                    stem = name[:-len(".jsonl")]
                    items.append(("session transcript", name, [os.path.join(transcripts, name)],
                                  [name, stem, stem[:8]]))
        else:
            print("TRANSCRIPTS · no such folder: %s" % transcripts)
    cutoff = time.time() - args.days * 86400
    listed, cited, recent, held = [], 0, 0, []
    for kind, name, paths, names in items:
        if any(never_read(os.path.basename(path)) for path in paths):
            continue
        if any(token in tokens for token in names):
            cited += 1
            continue
        size, newest = 0, 0.0
        for path in paths:
            part, when = tree_stats(path, cutoff)
            size, newest = size + part, max(newest, when)
            if newest >= cutoff:
                break
        if newest >= cutoff:
            recent += 1
        elif kind == "install backup" or any(holds_backup_or_package(path) for path in paths):
            held.append("HELD %s · %s · %s · holds a backup or a staged package: the session settles it" % (
                kind, name, human(size)))
        else:
            listed.append((kind, name, size, newest))
    report = Report(args.full)
    kinds = collections.Counter(item[0] for item in listed)
    print("OLD RECORDS · %d listed (%s: %s), %d named by a live record and kept, %d newer than %d days "
          "and not named, %d held (control: %d texts read%s)" % (
              len(listed), human(sum(item[2] for item in listed)),
              ", ".join("%s %d" % pair for pair in sorted(kinds.items())) or "none", cited, recent,
              args.days, len(held), read, ", the calendar among them" if has_calendar else ", NO CALENDAR"))
    report.listing(["LIST %s · %s · %s · last changed %s" % (
        kind, name, human(size), datetime.date.fromtimestamp(newest).isoformat())
        for kind, name, size, newest in listed] + held)
    if not pages:
        return probe_failed("no wiki page was read, so nothing can be called unnamed")
    if not has_calendar:
        return probe_failed("the calendar was not read, so nothing can be called unnamed")
    if listed and not cited:
        return probe_failed("none of the %d old records is named anywhere: the reading may be "
                            "broken, so this list deletes nothing safely" % len(listed))
    return 0


# ---- the generated page ------------------------------------------------------------------------

def wikilink(name):
    return "[" * 2 + name + "]" * 2


def cell(text):
    text = SPACES.sub(" ", str(text if text not in (None, "") else "-")).strip()
    return text.replace("[[", "[").replace("]]", "]").replace("|", "\\|")


def origin_cell(row):
    origin = row.get("origin") or {}
    dates = origin.get("dates") or []
    return "%s%s" % (origin.get("kind") or "not recorded", " " + ", ".join(dates[:3]) if dates else "")


def render_page(data, date):
    rows, meta = data.get("rows") or [], data.get("page") or {}
    created = meta.get("created") or date
    out = ["---", 'title: "Rule register"', "type: development",
           "confidence: %s" % (meta.get("confidence") or "medium"),
           "audited: %s" % (meta.get("audited") or date),
           "tags: [framework, rules, register, lifecycle]", "aliases: []",
           "created: %s" % created, "updated: %s" % date,
           'register-rows-sha256: "%s"' % rows_digest(rows), "---", "",
           "# Rule register", "",
           "One row per ruling: its one home, the moment it is read, whose rule it is, its layer, its "
           "shape, where it came from, how it is kept and its wording status. This page is generated "
           "from `%s` by `.claude/skills/weekly-audit/rule_register.py generate`; edit the data and "
           "generate again, never this page. The data holds the owner's wordings, so it never ships; "
           "the tool does." % DATA_REL, "",
           "## How the rows work", "",
           "- **Home and moment.** The file and section that hold the rule, and when it is read: `always-on`, `skill-step`, `template`, `hook` or `page-pointer`.",
           "- **Whose and layer.** `product`, `default` or `owner`; `core` or `user`, for the split between the public core and a user's own layer.",
           "- **Shape.** `guided` (a default, with room to depart from it for a stated reason, and few hard limits), `fixed` (a hard limit, with the failure that justifies it or the owner's decision it records) or `mechanism` (a hook or script, with its failure).",
           "- **Wording.** `approved-record`: a dated record of the owner's approval of those very words exists, and only these are checked word for word. `approved-untraced`: the home marks the text as the owner's and no record has been found; its text stays unchanged. `listed, not checked`: the approved words stand in a dated record, which the check never reads, so the row is listed with that reason and fails no install. `agent`: the agent's wording, everything else.",
           "- **A miss.** It comes to the owner with the stored wording, the home's text and the difference. The owner chooses: the stored wording goes back; the new text becomes the approved wording, the old one going once to " + wikilink("owner-rulings-history") + "; or it stays as a noted difference, stored on the row with its date and the owner's words.",
           "- **A skill section's row.** A skill's steps are already read at their moment, so they are listed by section: the row names the file and the section and holds no text, and the coverage check asks only that the section still stands.",
           "- **Its writer.** Only the lead of the session that changes a rule writes the data, in the same pass as the change; helpers propose rows. The weekly pass only lists, and its row is on " + wikilink("check-lifecycle") + ".",
           "- **When a rule changes.** On the owner's yes, in one pass: the home's text changes; every pointer and restatement is swept; the row's stored wording is replaced, so the register keeps only the current wording, and the replaced wording goes once to " + wikilink("owner-rulings-history") + "; holds made under the old rule are reopened; a lifecycle row is added or changed if the rule is recurring work. The wording check runs as one of that install's tests, listing the rows it placed: `wording-check --installed-only LIST`.",
           "- **The wording check's trial state.** The data's `trial` stays on through the first install: the check logs what it would have blocked and blocks nothing. The lead sets it off after that install; a miss on a text just placed, or a could-not-check, then fails an install.",
           ""]
    wording = collections.Counter(row.get("wording") for row in rows)
    layers = collections.defaultdict(collections.Counter)
    for row in rows:
        layers[(row.get("home") or {}).get("file") or "-"][row.get("layer") or "-"] += 1
    out += ["## Counts", "",
            "%d rows: %d approved with a record, %d approved with no record traced, %d %s, %d in the agent's wording." % (
                len(rows), wording["approved-record"], wording["approved-untraced"], wording[LISTED], LISTED,
                wording["agent"]), ""]
    out += ["## Files by layer", ""]
    if layers:
        out += ["| File | Core rows | User rows | Rows with no layer |", "|---|---|---|---|"]
        for rel, counts in sorted(layers.items()):
            out.append("| %s | %d | %d | %d |" % (cell(rel), counts["core"], counts["user"], counts["-"]))
    else:
        out.append("No rows yet.")
    out += ["", "## Rows by home", ""]
    if not rows:
        out += ["No rows yet. The first rows come from the map, by the tool's `seed` command.", ""]
    by_home = collections.defaultdict(list)
    for row in rows:
        by_home[(row.get("home") or {}).get("file") or "-"].append(row)
    for rel in sorted(by_home):
        out += ["### " + rel, "",
                "| Row | Section | Moment | Whose | Layer | Shape | Failure | Origin | Kept by | Wording | Pointers | Carriers | Lifecycle row | Text begins |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for row in by_home[rel]:
            home = row.get("home") or {}
            out.append("| " + " | ".join(cell(value) for value in (
                row.get("id"), home.get("section") or home.get("entry"), row.get("moment"),
                row.get("whose"), row.get("layer"), row.get("shape"), excerpt(row.get("failure"), 80),
                origin_cell(row), row.get("kept_by"), row.get("wording"),
                len(row.get("pointers") or []), len(row.get("carriers") or []),
                row.get("lifecycle_row"), excerpt(row.get("text"), 110))) + " |")
        out.append("")
    out += ["## Sources Used", "",
            "- " + wikilink("check-lifecycle") + ", for how a recurring check earns its row.",
            "- " + wikilink("capability-register") + ", whose shape this register follows: one data file, a generated page and its checks.",
            "", "## Related", "",
            "- " + wikilink("check-lifecycle"),
            "- " + wikilink("owner-rulings-history"),
            "- " + wikilink("capability-register"), ""]
    return "\n".join(out)


def cmd_generate(args):
    ctx = Context(args)
    if ctx.problem and ctx.data is None and os.path.exists(ctx.data_path):
        return probe_failed(ctx.problem)
    if not os.path.exists(ctx.data_path):
        print("generate: not applicable (no data file, as in a fresh public copy); no page written")
        return 0
    write_atomic(ctx.page_path, render_page(ctx.data, ctx.today))
    print("generate: wrote %s from %d rows" % (ctx.page_path, len(ctx.rows)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, function):
        command = sub.add_parser(name)
        command.add_argument("--vault")
        command.add_argument("--data")
        command.add_argument("--page")
        command.add_argument("--today")
        command.set_defaults(function=function)
        return command

    add("generate", cmd_generate)
    wording = add("wording-check", cmd_wording_check)
    wording.add_argument("--trial", action="store_true")
    wording.add_argument("--installed-only", metavar="LIST")
    weekly = add("weekly", cmd_weekly)
    weekly.add_argument("--full", action="store_true")
    weekly.add_argument("--all-flags", action="store_true")
    add("record-audit", cmd_record_audit)
    seed = add("seed", cmd_seed)
    seed.add_argument("--map", nargs="+", required=True, metavar="FILE")
    seed.add_argument("--rules", required=True)
    seed.add_argument("--tracing", required=True)
    seed.add_argument("--out")
    seed.add_argument("--skill-sections", action="store_true")
    add("in-place", cmd_in_place)
    cleanup = add("cleanup", cmd_cleanup)
    cleanup.add_argument("--store")
    cleanup.add_argument("--projects")
    cleanup.add_argument("--no-transcripts", action="store_true")
    cleanup.add_argument("--days", type=int, default=CLEANUP_DAYS)
    cleanup.add_argument("--full", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    return args.function(args)


if __name__ == "__main__":
    sys.exit(main())
