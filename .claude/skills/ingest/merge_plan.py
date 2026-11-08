#!/usr/bin/env python3
"""Print an anchored merge plan; no patch or ledger writes.

Usage: merge_plan.py --vault DIR --ledger FILE [--ledger CLAIMS_FILE ...]
       [--lanes LA,LB] [--quarantine JSON_LIST] [--allow-malformed FILE:LINE ...]
       [--union-dir EXISTING_SCRATCH_DIRECTORY]
       merge_plan.py --vault DIR --resolved DIFF [--resolved DIFF ...]
       [--after-read BASE:DIFF_HASH ...]

Claims carry name, type, kind, target, facts, source/from, diff, base and diff_hash.
Hashes are sha256 prefixes of 16 hex digits (or the complete sha256 for diff_hash).
The first ledger binds the run; separate files need that run explicitly or their
own matching run_open. Runless events inherit only their own file's run_open.
File order proves sequence within a ledger; strict timestamps prove it across
files. Every expected lane's latest opening and latest close must precede its
verification. A later close invalidates earlier verification until another verify.
All eight score names are required, with distinct quarantine references per object.
--allow-malformed settles only the real FILE and LINE explicitly named by the head.
The expected base hash stays tied to the bytes used to validate the diff; drift
during planning is manual or an error, never a replacement expected hash.
Exit 0 prints the plan; exit 2 prints PROBE FAILED and suppresses apply commands.
Classes: quarantined objects are removed first; conflict > manual > tier-raised
> apply-union > apply. A multi-lane target unions only when every member adds list
items (lines beginning "- ") under Appears in, Related, Key Points or Conflicts /
Open Questions, and touches the frontmatter at most by re-dating updated:/audited:
or by appending to a single-line sources:/aliases: list. Complete items are
de-duplicated after whitespace collapse only when their section, parser blocks
and position amongst base lines agree. Every continuation line counts;
punctuation, case and target/gloss boundaries remain distinct. A removed or edited body
line, prose outside a list item, a heading, or any other frontmatter change keeps
the target in conflict. Every block boundary is markdown-it-py's (CommonMark) over
the page body; frontmatter closes at the first column-zero --- or ... line on
its own, never an indented delimiter. An unclosed block exits 2. An addition counts
only when the parser reads it, in its member's proposal, as a one-line top-level
list item holding a block of its own, in a section headed by one of those four
headings (a section runs to the next heading of the same or higher level; the
innermost one decides). Before ordinary classification a target is manual, with
the construct and line, when the parser shows an addition inside a fence, an
indented code block or an HTML block, an addition's list item taking in an
existing line, or an existing line changing its blocks (a Setext heading, a
swallowing fence). The page guard remains only for what CommonMark cannot place:
Obsidian comment (%%) and maths block ($$) markers in the body or a member's
added body lines. Frontmatter is excluded; strict list refusals are local to the
union target, not the catalogue. List items requiring the raw decoding fallback
also require a hand read. A union appends each addition after the last item of
the list its member put it in, or where its member put it when it starts a list
of its own, then parses the composed page. Every added line must survive its
permitted merge or have a verified complete same-context duplicate. An addition or an existing line that
leaves the blocks its member's proposal gave it, or an addition under another
heading, makes it manual. Without markdown-it-py (or its dependency mdurl) the
planner prints PROBE FAILED and exits 2; a version other than the accepted pin
is named in a note, and test_merge_plan.sh is the acceptance test.
The head reads every composed union diff before applying it
(compile-lane bullets from different sources sit side by side there, so a near
duplicate is the head's call, never the planner's). --union-dir is the sole write exception: one
new diff per union target in the head's existing scratch directory outside the
vault, never an overwrite of different bytes. Missing union scratch exits 2.
A confidence lift always names the required full-page read, including a
lift introduced by a resolved diff. Held output names a second --resolved command
with --after-read BASE:DIFF_HASH: the head's read acknowledgement is bound to the
validated page and exact diff. Repeat that pair for each acknowledged resolution.
Every resolution in a batch is validated and rechecked before any commands print.
The head applies with patch at zero fuzz.
"""
import argparse
import difflib
from datetime import datetime
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import unicodedata

sys.dont_write_bytecode = True
try:  # The only imports outside the standard library: markdown-it-py and its one dependency.
    import mdurl  # noqa: F401 -- imported by name so a missing mdurl reports itself
    import markdown_it
    from markdown_it import MarkdownIt
    PARSER_ERROR = None
except ImportError as error:  # Never a silent fallback to line scanning: main() exits 2.
    markdown_it, MarkdownIt, PARSER_ERROR = None, None, error
PARSER_PIN = '4.2.0'  # The version the critic probe sets in test_merge_plan.sh were accepted on (capability register).
HASH_LENGTH = 16  # The prefix length used by source_hash and the de-dup probe.
TIERS = {tier: rank for rank, tier in enumerate(('very-low', 'low', 'medium', 'high', 'authoritative'))}  # Confidence ordinal; compiled pages cap at high.
SCORES = ('fab', 'cov', 'tier', 'struct', 'integ', 'lang', 'anom', 'claims')
DIRS = {'entity': 'entities', 'tool': 'tools', 'concept': 'concepts', 'model': 'models', 'benchmark': 'benchmarks', 'source': 'sources'}
LINK = re.compile(r'\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]')
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)$')


class ProbeError(ValueError):
    pass


class UnionRefusal(ProbeError):
    """A local hand-read decision, not a failed plan or a competing edit."""


def digest(data, length=HASH_LENGTH):
    return hashlib.sha256(data).hexdigest()[:length]


def json_type(value):
    return {dict: 'object', list: 'list', str: 'string', bool: 'boolean', int: 'number', float: 'number', type(None): 'null'}.get(type(value), type(value).__name__)


def normalise(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', str(text)).casefold() if c.isalnum())


def scalar(value):
    # Confidence uses the same quoted-scalar rules as other frontmatter values.
    value = value.strip()
    m = re.fullmatch(r'''(["'])(.*?)\1(?:\s+#.*)?''', value)
    return m[2] if m else value.split(' #', 1)[0].strip()


YAML_ESCAPES = {'0': '\0', 'a': '\a', 'b': '\b', 't': '\t', '\t': '\t', 'n': '\n', 'v': '\v', 'f': '\f', 'r': '\r', 'e': '\x1b', ' ': ' ', '"': '"', '/': '/', '\\': '\\', 'N': '\x85', '_': '\xa0', 'L': '\N{LINE SEPARATOR}', 'P': '\N{PARAGRAPH SEPARATOR}'}
YAML_HEX = {'x': 2, 'u': 4, 'U': 8}  # Hex digits after \x, \u and \U (YAML 1.2, section 5.7).


def yaml_escapes(inner):
    """Decode a one-line YAML 1.2 double-quoted body, or None when YAML rejects it.

    JSON decodes first and keeps its reading; this adds the escapes JSON lacks, so
    "\\x41", "\\u0041" and A share one identity (CR-PLANNER A07). An unknown escape,
    an unescaped quote or a raw non-printable character returns None.
    """
    out, position = [], 0
    while position < len(inner):
        ch = inner[position]
        if ch == '"' or (ch != '\t' and (ord(ch) < 0x20 or (0x7f <= ord(ch) <= 0x9f and ch != '\x85') or 0xd800 <= ord(ch) <= 0xdfff or ord(ch) in (0xfffe, 0xffff))):
            return None
        if ch != '\\':
            out.append(ch); position += 1; continue
        code = inner[position + 1:position + 2]
        if code and code in YAML_ESCAPES:
            out.append(YAML_ESCAPES[code]); position += 2; continue
        width = YAML_HEX.get(code)
        digits = inner[position + 2:position + 2 + width] if width else ''
        if not width or not re.fullmatch('[0-9A-Fa-f]{' + str(width) + '}', digits) or int(digits, 16) > 0x10ffff:
            return None
        out.append(chr(int(digits, 16))); position += 2 + width
    return ''.join(out)


def alias_scalar(value, strict=False):
    """Shared block/flow decoding; only catalogue reads may use raw fallback."""
    value = value.strip()
    match = re.fullmatch(r'''(["'])(.*?)\1(?:\s+#.*)?''', value)
    if not match:
        if strict and value.startswith('"'):
            raise ProbeError('undecodable quoted list item ' + value + ' needs raw fallback')
        return scalar(value)
    if match[1] == "'": return match[2].replace("''", "'")
    try:
        decoded = json.loads(value[:match.end(2) + 1])
    except ValueError as error:
        decoded = yaml_escapes(match[2])
        if decoded is None:
            if strict:
                raise ProbeError('undecodable quoted list item ' + value + ' needs raw fallback') from error
            return match[2]
    # A union item decoding to a control or separator (Python's \N{...} read as YAML
    # NEL, say) is a hand read, never a silent union (CR-PLANNER A06).
    if strict and any(unicodedata.category(ch) in ('Cc', 'Zl', 'Zp') for ch in decoded):
        raise ProbeError('quoted list item ' + value + ' decodes to a control or line-separator character')
    return decoded


def flow_list_parts(value):
    """Separate an outer list from its comment without consuming quoted brackets.

    The fallback preserves the shipped catalogue's partial-list tolerance. The
    strict union reader separately validates the extracted scalar contents.
    """
    value = value.strip()
    position, depth, item_start = 1, 1, True
    quoted = re.compile(r'''"(?:[^"\\]|\\.)*"|'(?:[^']|'')*' ''', re.X)
    while position < len(value):
        ch = value[position]
        if item_start and ch in ('"', "'"):
            match = quoted.match(value, position)
            if not match: break
            position = match.end(); item_start = False; continue
        if ch == '[':
            depth += 1; item_start = True
        elif ch == ']':
            depth -= 1
            if depth == 0: return value[1:position], value[position + 1:].strip()
            item_start = False
        elif ch == ',': item_start = True
        elif not ch.isspace(): item_start = False
        position += 1
    return value[1:].rsplit(']', 1)[0], ''


class Metadata(dict):
    """Known values plus explicit (key, line, form) refusals; never a clean partial read."""
    def __init__(self):
        super().__init__()
        self.uncertain = []


def block_scalar(lines, index, end, indent, header):
    """Read literal/folded text, indentation and chomping (YAML 1.2, section 8.1).

    The sequence's dash column is the parent indentation. The first non-empty
    content line supplies the implicit indentation; an explicit digit is relative
    to that parent. Empty lines before the next item belong to this scalar.
    """
    match = re.fullmatch(r'([|>])([1-9]?[+-]?|[+-][1-9]?)(?:[ \t]+#.*)?[ \t]*', header)
    if not match:
        return None, index + 1, (index + 1, 'unsupported block scalar header')
    indicator, flags = match.groups()
    width = next((indent + int(ch) for ch in flags if ch.isdigit()), None)
    implicit = width is None
    stop = index + 1
    while stop < end:
        row = lines[stop]
        if row.strip(' ') and len(row) - len(row.lstrip(' ')) <= indent: break
        stop += 1
    raw = lines[index + 1:stop]
    if width is None:
        width = next((len(row) - len(row.lstrip(' ')) for row in raw if row.strip(' ')), max([indent + 1] + [len(row) for row in raw]))
    content = []
    for number, row in enumerate(raw, index + 2):
        spaces = len(row) - len(row.lstrip(' '))
        if (row.strip(' ') and spaces < width) or (implicit and not any(content) and not row.strip(' ') and spaces > width):
            return None, stop, (number, 'scalar continuation with unsupported indentation')
        content.append(row[width:] if len(row) >= width else '')
    if indicator == '|':
        value = ''.join(row + '\n' for row in content)
    else:
        value, position = '', 0
        while position < len(content):
            row = content[position]
            if not row:
                value += '\n'; position += 1; continue
            following = position + 1
            while following < len(content) and not content[following]: following += 1
            blanks = following - position - 1
            value += row
            if following == len(content):
                value += '\n' * (blanks + 1)
            elif not row.startswith((' ', '\t')) and not content[following].startswith((' ', '\t')):
                value += '\n' * blanks if blanks else ' '
            else:
                value += '\n' * (blanks + 1)
            position = following
    if '-' in flags: value = value.rstrip('\n')
    elif '+' not in flags: value = value.rstrip('\n') + ('\n' if any(content) else '')
    return value, stop, None


def block_sequence(lines, start, end, key, decode, uncertain):
    """Collect every supported item to the next root key or frontmatter close.

    Blank/comment lines never terminate a sequence. An unimplemented item or
    continuation records uncertainty and scanning continues, retaining later
    known identities as well. Aliases and sources use this same reader.
    """
    values, indent, position = [], None, start
    quoted = re.compile(r'''("(?:[^"\\]|\\.)*"|'(?:[^']|'')*')(?:[ \t]+#.*)?[ \t]*$''')
    while position < end:
        row = lines[position]
        if not row.strip() or row.lstrip().startswith('#'):
            position += 1; continue
        if row and not row[0].isspace() and not re.match(r'-(?:\s|$)', row):
            if re.match(r'''(?:[\w-]+|"[^"]+"|'[^']+'):\s*''', row): break
        item = re.fullmatch(r'( *)-(?:[ \t]+(.*))?', row)
        if not item:
            uncertain(key, position, 'scalar continuation or nested mapping not implemented')
            position += 1; continue
        column, value = len(item[1]), (item[2] or '').strip()
        if indent is None: indent = column
        if column != indent:
            uncertain(key, position, 'nested sequence or inconsistent item indentation')
            position += 1; continue
        if value.startswith(('|', '>')):
            decoded, stop, problem = block_scalar(lines, position, end, indent, value)
            if problem: uncertain(key, problem[0] - 1, problem[1])
            else: values.append(decoded)
            position = stop; continue
        form = None
        if not value or value.startswith('#'): form = 'empty scalar item'
        elif value.startswith('&'): form = 'anchor'
        elif value.startswith('*'): form = 'alias reference'
        elif value.startswith('!'): form = 'tag'
        elif value.startswith(('{', '? ')): form = 'nested mapping in an item'
        elif value.startswith(('[', '- ')): form = 'nested sequence in an item'
        elif value.startswith(('"', "'")):
            if not quoted.fullmatch(value): form = 'multi-line quoted scalar or unsupported quoted suffix'
        else:
            value = re.split(r'[ \t]+#', value, maxsplit=1)[0].rstrip()
            if re.search(r':(?:\s|$)', value): form = 'nested mapping in an item'
            # YAML implicit typing is outside the string identity subset. Refuse
            # it explicitly rather than normalising a guessed string identity.
            elif re.fullmatch(r'(?i:null|true|false|yes|no|on|off)|~|[-+.]?[0-9].*|[-+]?\.(?i:inf|nan)', value):
                form = 'implicit non-string scalar'
            elif value.startswith(('@', '`', '%')): form = 'unsupported scalar indicator'
        if form: uncertain(key, position, form)
        else: values.append(decode(value, position, key))
        position += 1
    return values


def frontmatter(text, strict_aliases=False, location='page'):
    lines = text.splitlines()
    result = Metadata()
    def decode_alias(value, index, key):
        try: return alias_scalar(value, strict=strict_aliases)
        except ProbeError as error:
            raise UnionRefusal(f'union list refused: {key} at {location} line {index + 1} · {error}') from error
    def uncertain(key, index, form):
        result.uncertain.append((key, index + 1, form))
        if strict_aliases:
            raise UnionRefusal(f'union list refused: {key} identity UNCERTAIN at {location} line {index + 1} · {form}')
    end = frontmatter_end(text)
    if end < 0:
        return result
    for i, line in enumerate(lines[1:end], 1):
        m = re.match(r'([\w-]+):\s*(.*)$', line)
        if not m:
            continue
        key, value = m[1], m[2]
        if key in ('aliases', 'sources'):
            if value.startswith(('&', '!', '*')):
                form = {'&': 'anchor', '!': 'tag', '*': 'alias reference'}[value[0]]
                uncertain(key, i, form + ' on sequence header')
                result[key] = block_sequence(lines, i + 1, end, key, decode_alias, uncertain)
            elif value.strip().startswith('['):
                # Catalogue compatibility follows the shipped lenient read.
                # Only the target's union eligibility uses strict validation.
                inner, _ = flow_list_parts(value)
                result[key] = [decode_alias(item, i, key) for item in list_items(inner, strict=False)]
            elif value.strip() and not value.lstrip().startswith('#'):
                result[key] = [decode_alias(value, i, key)]
            else:
                result[key] = block_sequence(lines, i + 1, end, key, decode_alias, uncertain)
        else:
            result[key] = scalar(value)
    return result


def header_path(value, vault):
    value = value.split('\t', 1)[0].strip()
    if value.startswith('"'):
        try: value = json.loads(value)
        except ValueError: raise ProbeError('invalid quoted diff path')
    if value == '/dev/null':
        return None
    if value.startswith(('a/', 'b/')):
        value = value[2:]
    path = (vault / value).resolve() if not os.path.isabs(value) else Path(value).resolve()
    if not path.is_relative_to(vault) or not path.is_relative_to(vault / 'wiki') or path.suffix != '.md':
        raise ProbeError('diff path is outside wiki Markdown pages')
    return path


def parse_diff(text, vault, target=None):
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines) and lines[i].startswith(('diff --git ', 'index ')):
        i += 1
    if i + 1 >= len(lines) or not lines[i].startswith('--- ') or not lines[i + 1].startswith('+++ '):
        raise ProbeError('no unified ---/+++ header pair')
    old, new = header_path(lines[i][4:].rstrip('\r\n'), vault), header_path(lines[i + 1][4:].rstrip('\r\n'), vault)
    if new is None or (old is not None and old != new) or (target is not None and new != target):
        raise ProbeError('diff headers name a different page')
    i += 2
    hunks, changes = [], 0
    old_end = new_end = 0
    while i < len(lines):
        if not ''.join(lines[i:]).strip(): break
        match = HUNK.fullmatch(lines[i].rstrip('\r\n'))
        if not match: raise ProbeError('invalid hunk header or extra file')
        start, count = int(match[1]), int(match[2] or 1)
        nstart, ncount = int(match[3]), int(match[4] or 1)
        offset = start if count == 0 else start - 1
        noffset = nstart if ncount == 0 else nstart - 1
        if offset < old_end or noffset < new_end or min(offset, noffset) < 0:
            raise ProbeError('overlapping or invalid hunk coordinates')
        body, used, nused = [], 0, 0
        i += 1
        while i < len(lines) and (used < count or nused < ncount):
            line = lines[i]
            if line.startswith('\\ No newline at end of file'):
                if not body: raise ProbeError('orphan no-newline marker')
                body[-1] = body[-1].rstrip('\n'); i += 1; continue
            if not line or line[0] not in ' +-': raise ProbeError('incomplete hunk body')
            tag = line[0]
            used += tag in ' -'; nused += tag in ' +'; changes += tag in '+-'
            if used > count or nused > ncount: raise ProbeError('hunk line counts do not match')
            body.append(line); i += 1
        if i < len(lines) and lines[i].startswith('\\ No newline at end of file'):
            if not body: raise ProbeError('orphan no-newline marker')
            body[-1] = body[-1].rstrip('\n'); i += 1
        if used != count or nused != ncount: raise ProbeError('incomplete hunk')
        hunks.append((offset, count, noffset, ncount, body))
        old_end, new_end = offset + count, noffset + ncount
    if not hunks or not changes: raise ProbeError('diff contains no changes')
    if old is None and any(offset or count for offset, count, _, _, _ in hunks):
        raise ProbeError('create diff consumes old lines')
    return {'old': old, 'new': new, 'hunks': hunks}


def diff_problem(data, vault, target=None):
    try:
        parse_diff(data.decode('utf-8') if isinstance(data, bytes) else data, vault, target)
        return None
    except (ValueError, TypeError) as e:
        return str(e)


def apply_memory(text, diff):
    """Exact old coordinates and context, with no fuzz, offsets or filesystem writes."""
    source, output, cursor = text.splitlines(keepends=True), [], 0
    for offset, count, noffset, ncount, body in diff['hunks']:
        old = [x[1:] for x in body if x[0] in ' -']
        new = [x[1:] for x in body if x[0] in ' +']
        if offset > len(source) or source[offset:offset + count] != old:
            raise ProbeError('diff context does not match the current page')
        output += source[cursor:offset]
        if len(output) != noffset:
            raise ProbeError('new hunk coordinate does not match')
        output += new; cursor = offset + count
    return ''.join(output + source[cursor:])


def timestamp(event):
    try:
        value = datetime.fromisoformat(str(event.get('ts', '')).replace('Z', '+00:00'))
        return value if value.tzinfo is not None else None
    except ValueError:
        return None


def before(a, b):
    ta, tb = timestamp(a), timestamp(b)
    if a['_file'] == b['_file']:
        return a['_line'] < b['_line'] and not (ta and tb and ta > tb)
    return ta is not None and tb is not None and ta < tb


def read_events(paths, approvals):
    events, problems, settled = [], [], set()
    allowed = set()
    for token in approvals:
        name, sep, number = token.rpartition(':')
        if not sep or not number.isdigit() or int(number) < 1:
            raise ProbeError('--allow-malformed wants FILE:LINE')
        allowed.add((str(Path(name).expanduser().resolve()), int(number)))
    expected = None
    for path in paths:
        real = str(Path(path).expanduser().resolve())
        data = Path(real).read_text(encoding='utf-8')
        if not data.strip(): raise ProbeError('empty ledger: ' + real)
        rows = []
        for number, line in enumerate(data.splitlines(), 1):
            if not line.strip(): continue
            try:
                e = json.loads(line)
                if not isinstance(e, dict) or not isinstance(e.get('event'), str):
                    raise ValueError('event is not an object with an event name')
                if any(k.startswith('_') for k in e): raise ValueError('reserved metadata key')
            except ValueError:
                key = real, number
                print(f'MALFORMED {real}:{number}' + (' · settled by --allow-malformed' if key in allowed else ' · unsettled'))
                if key in allowed: settled.add(key)
                else: problems.append(f'unsettled malformed line {real}:{number}')
                continue
            e['_file'], e['_line'] = real, number
            rows.append(e)
        if not rows: raise ProbeError('ledger holds no parseable events: ' + real)
        opens = [e for e in rows if e['event'] == 'run_open']
        if expected is None:
            if len(opens) != 1 or not opens[0].get('run'):
                raise ProbeError('first ledger needs exactly one named run_open')
            expected = opens[0]['run']
        if len(opens) > 1 or any(e.get('run') != expected for e in opens):
            problems.append('foreign or repeated run_open: ' + real)
        bound = opens[0].get('run') if len(opens) == 1 else None
        for e in rows:
            run = e.get('run', bound)
            if run != expected:
                problems.append(f'foreign or unbound event {real}:{e["_line"]}')
                continue
            if 'run' not in e and opens and e['_line'] < opens[0]['_line']:
                problems.append(f'runless event precedes run_open {real}:{e["_line"]}')
                continue
            events.append(e)
    for name, number in sorted(allowed - settled):
        print(f'note: --allow-malformed {name}:{number} settles nothing')
    return events, problems


def claims_from(events):
    result = []
    for e in events:
        if e['event'] != 'checkpoint' or e.get('stage') != 'claims_emitted': continue
        values = e.get('claims')
        if not isinstance(values, list): raise ProbeError('claims must be a list, got ' + json_type(values))
        if not isinstance(e.get('lane'), str) or not e['lane']: raise ProbeError('claim checkpoint has no lane')
        for i, c in enumerate(values, 1):
            if not isinstance(c, dict) or not isinstance(c.get('name'), str) or not c['name'].strip():
                raise ProbeError('claim member must be an object with a name')
            item = dict(c)
            item.update(lane=e['lane'], _event=e, _id=f'{e["_file"]}:{e["_line"]}:{i}')
            for key in ('source', 'from'):
                item.setdefault(key, e.get(key, ''))
            result.append(item)
    return result


def reference_ids(refs, claims):
    if not isinstance(refs, list): raise ProbeError('quarantine must be a list, got ' + json_type(refs))
    ids = set()
    for ref in refs:
        if isinstance(ref, str): ref = {'name': ref}
        if not isinstance(ref, dict) or not ref or not any(k in ref for k in ('id', 'claim_id', 'name')):
            raise ProbeError('quarantine reference needs claim_id or name with qualifiers')
        if set(ref) - {'id', 'claim_id', 'name', 'lane', 'source', 'from'}:
            raise ProbeError('unknown quarantine selector field')
        hits = [c for c in claims if all(str(c.get('_id' if k in ('id', 'claim_id') else k, '')) == str(v) for k, v in ref.items())]
        if len(hits) != 1: raise ProbeError('quarantine reference is absent or ambiguous: ' + json.dumps(ref))
        identity = hits[0]['_id']
        if identity in ids: raise ProbeError('claim object named twice in quarantine: ' + identity)
        ids.add(identity)
    return ids


def score_values(event, lane):
    text = event.get('scores')
    if not isinstance(text, str): raise ProbeError('verify has no scores line for ' + lane)
    pattern = r'^(?:(\S+)\s+)?scores: ' + ' '.join(k + r' (\d+|-)' for k in SCORES) + r'$'
    match = re.fullmatch(pattern, text.strip())
    if not match or match[1] not in (None, lane): raise ProbeError('verify needs all eight score names for ' + lane)
    values = dict(zip(SCORES, match.groups()[1:]))
    if any(v == '-' for k, v in values.items() if k != 'claims'):
        raise ProbeError('verify has an unscored dimension for ' + lane)
    return {k: None if v == '-' else int(v) for k, v in values.items()}


def evidence(events, claims, lanes):
    expected = set(lanes) | {c['lane'] for c in claims} | {e.get('lane') for e in events if e['event'] == 'lane_open' and (e.get('role') == 'compile' or not e.get('role') and e.get('definition') == 'wiki-compile')}
    expected.discard(None)
    problems, quarantined, incomplete = [], set(), []
    for lane in sorted(expected):
        own = [e for e in events if e.get('lane') == lane]
        opens = [e for e in own if e['event'] == 'lane_open']
        closes = [e for e in own if e['event'] == 'lane_close']
        verifies = [e for e in own if e['event'] == 'verify']
        latest = [o for o in opens if all(o is p or before(p, o) for p in opens)]
        if len(latest) != 1:
            problems.append('missing or unordered lane_open: ' + lane); incomplete.append(lane); continue
        opened = latest[0]
        completions = [c for c in closes if all(c is p or before(p, c) for p in closes)]
        if len(completions) != 1 or not before(opened, completions[0]):
            incomplete.append(lane); continue
        valid = [v for v in verifies if before(completions[0], v)]
        if not valid:
            incomplete.append(lane); continue
        last = [v for v in valid if all(v is w or before(w, v) for w in valid)]
        if len(last) != 1:
            problems.append('unordered verify events: ' + lane); continue
        verification = last[0]
        if any(not any(before(c, v) and any(before(o, c) for o in opens) for c in closes) for v in verifies):
            problems.append('premature verify event: ' + lane)
        member = [c for c in claims if c['lane'] == lane]
        for c in member:
            checkpoint = c['_event']
            if not before(checkpoint, verification) or not any(before(checkpoint, closed) and before(closed, verification) for closed in completions):
                problems.append('claim ordering cannot establish coverage before close and verify: ' + c['_id'])
        try:
            values = score_values(verification, lane)
            refs = verification.get('quarantined', verification.get('quarantine', []))
            dropped = reference_ids(refs, member)
            if values['claims'] is None:
                quarantined.update(c['_id'] for c in member)
                raise ProbeError('unscored claims: ' + lane)
            if values['claims'] != len(dropped): raise ProbeError('claims count differs from distinct quarantine objects: ' + lane)
            quarantined.update(dropped)
        except ProbeError as e:
            problems.append(str(e))
    if incomplete:
        problems.append('compile lanes with no verify event after their latest lane_close: ' + ' '.join(incomplete))
    return problems, quarantined


class Catalogue:
    def __init__(self, vault):
        self.vault, self.parents, self.pages, self.names = vault, {}, {}, {}
        for path in sorted((vault / 'wiki').rglob('*.md')):
            text = path.read_text(encoding='utf-8')
            meta = frontmatter(text)
            key = normalise(path.stem)
            self.add(key)
            for alias in meta.get('aliases', []): self.join(key, normalise(alias))
            self.pages[path.resolve()] = (key, text, meta)
            self.names.setdefault(key, path.stem)

    def add(self, key):
        if key: self.parents.setdefault(key, key)

    def find(self, key):
        self.add(key)
        if self.parents[key] != key: self.parents[key] = self.find(self.parents[key])
        return self.parents[key]

    def join(self, a, b):
        if a and b: self.parents[self.find(b)] = self.find(a)

    def targets(self, key):
        return [p for p, (k, _, _) in self.pages.items() if self.find(k) == self.find(key)]


def catalogue_uncertainty(cat):
    """Alias refusals travel with each page's metadata, beside its known identities."""
    return {path: issues for path, (_, _, meta) in cat.pages.items()
            if (issues := [(line, form) for key, line, form in meta.uncertain if key == 'aliases'])}


def guard_catalogue_identities(cat, members, paths):
    """Uncertain pages cannot union; new identities cannot bypass unread aliases.

    An alias append might touch any uncertain catalogue page. Body-only unions
    on unrelated, known pages do not need that wider collision check. The
    catalogue's identity graph stays independent of this eligibility guard.
    """
    uncertain = catalogue_uncertainty(cat)
    affected = [path for path in paths if path in uncertain]
    for member in members:
        old = {normalise(a) for a in frontmatter(member['text']).get('aliases', [])}
        old.add(normalise(member['target'].stem))
        new = frontmatter(member['changed'] or '').get('aliases', []) + member['claim'].get('aliases', [])
        if any(normalise(a) not in old for a in new):
            affected = list(uncertain)
            break
    if affected:
        path = affected[0]
        line, form = uncertain[path][0]
        raise UnionRefusal(f'union list refused: aliases identity UNCERTAIN at {path.relative_to(cat.vault)} page line {line} · {form}')


def claim_name(c):
    target = c.get('target', '')
    links = LINK.findall(str(target))
    if links: return Path(links[0]).stem
    if isinstance(target, str) and target.endswith('.md') and ' ' not in target:
        return Path(target).stem
    return c['name']


def inspect_claim(c, target, cat):
    problems, parsed, changed = [], None, None
    text = cat.pages[target][1] if target in cat.pages else ''
    exists = target.exists()
    oldtier = frontmatter(text).get('confidence', '')
    lift = TIERS.get(str(c.get('confidence', '')).strip('\'"'), -1) > TIERS.get(oldtier, -1) if exists else False
    if c.get('kind') not in ('create', 'update'): problems.append('claim kind is not create or update')
    if c.get('kind') == 'create' and exists: problems.append('create target now exists')
    if c.get('kind') == 'update' and (not exists or c.get('base') != digest(text.encode('utf-8'))): problems.append('base missing or moved')
    path = c.get('diff')
    try:
        if not isinstance(path, str) or not path: raise ProbeError('missing diff')
        path = Path(path).expanduser()
        if not path.is_absolute(): path = Path(c['_event']['_file']).parent / path
        data = path.read_bytes()
        wanted = c.get('diff_hash')
        if not isinstance(wanted, str) or not re.fullmatch(r'(?:[0-9a-f]{16}|[0-9a-f]{64})', wanted) or digest(data, len(wanted)) != wanted:
            problems.append('diff hash missing or changed')
        parsed = parse_diff(data.decode('utf-8'), cat.vault, target)
        if (c.get('kind') == 'create') != (parsed['old'] is None): problems.append('diff kind differs from claim')
        if parsed['old'] is None and exists: raise ProbeError('create target now exists')
        changed = apply_memory(text, parsed)
        newmeta = frontmatter(changed)
        lift |= exists and TIERS.get(newmeta.get('confidence', ''), -1) > TIERS.get(oldtier, -1)
        if c.get('kind') == 'create' and (not newmeta or '## Related' not in page_view(changed).titles()):
            problems.append('create lacks frontmatter or Related section; head checks the full schema')
    except (OSError, ValueError, TypeError) as e:
        problems.append('not a usable unified diff: ' + str(e))
    expected_base = digest(text.encode('utf-8')) if target in cat.pages else None
    return {'claim': c, 'target': target, 'problems': problems, 'lift': lift, 'parsed': parsed, 'text': text, 'changed': changed, 'diff': path, 'expected_base': expected_base}


def base_problem(target, expected):
    """Compare disk with the validated base; never replace the expected hash."""
    if expected is None:
        return 'create target appeared during planning' if target.exists() or target.is_symlink() else None
    try:
        observed = digest(target.read_bytes())
    except OSError as e:
        return 'base unreadable during planning: ' + str(e)
    if observed != expected:
        return f'base moved during planning: expected {expected}, observed {observed}'
    return None


def classify(members):
    lanes = {x['claim']['lane'] for x in members}
    if len(lanes) > 1:
        candidates = [list_additions(x) for x in members]
        if any(c is None for c in candidates): return 'conflict'
        if any(x['problems'] for x in members): return 'manual'
        # Confidence edits accompanying otherwise union-eligible changes require the
        # full-page read first. No union artefact ever changes confidence.
        if any(x['lift'] for x in members): return 'tier-raised'
        if any(c[1] for c in candidates): return 'conflict'
        return 'apply-union'
    if any(x['problems'] for x in members): return 'manual'
    paths = {str(x['diff']) for x in members}
    if len(paths) != 1: return 'manual'
    return 'tier-raised' if any(x['lift'] for x in members) else 'apply'


UNION_HEADINGS = ('## Appears in', '## Related', '## Key Points', '## Conflicts / Open Questions')
STAMP_KEYS = ('updated', 'audited')
LIST_KEYS = ('sources', 'aliases')
FM_LIST = re.compile(r'^(sources|aliases): \[(.*)\]\s*$')


def frontmatter_end(text):
    """First column-zero --- or ... line after the opener; -1 only without an opener.

    Indented delimiters belong to YAML values. Metadata and body offsets share
    this boundary, and an unclosed block is a broken premise, never body text.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---': return -1
    for i in range(1, len(lines)):
        if lines[i].rstrip(' \t') in ('---', '...'): return i
    raise ProbeError('frontmatter does not close')


def list_value(item):
    """Decode the supported scalar subset without changing its source spelling."""
    if item.startswith('"'):
        if not re.fullmatch(r'"(?:[^"\\\r\n]|\\.)*"', item):
            raise ProbeError('unterminated or malformed double-quoted frontmatter item')
        return alias_scalar(item, strict=True)
    if item.startswith("'"):
        if not re.fullmatch(r"'(?:[^']|'')*'", item):
            raise ProbeError('unterminated or malformed single-quoted frontmatter item')
        return alias_scalar(item)
    if not item or item[0] in '!&*{}[]#|>@`%"\'' or re.search(r'[\[\]{},\r\n]|:\s|(?:^|\s)#', item):
        raise ProbeError('unsupported plain frontmatter list item')
    return item


def list_values(inner):
    """Independent flow-list validation: JSON first, otherwise a scalar grammar.

    The fallback accepts plain strings and YAML single quotes (including doubled
    quotes). Collections and comments fail closed; double-quoted values must
    decode without the catalogue's raw-inner fallback.
    It does not call the splitter used to collect and merge the source tokens.
    """
    try:
        values = json.loads('[' + inner + ']')
        if all(isinstance(item, str) for item in values): return values
    except ValueError:
        pass
    token = re.compile(r'''\s*("(?:[^"\\\r\n]|\\.)*"|'(?:[^']|'')*'|[^,\[\]{}"'\s][^,\[\]{}]*?)\s*(,|$)''')
    values, position = [], 0
    while inner[position:].strip():
        match = token.match(inner, position)
        if not match: raise ProbeError('frontmatter list does not match the scalar grammar')
        values.append(list_value(match[1]))
        position = match.end()
        if match[2] and not inner[position:].strip():
            raise ProbeError('frontmatter list has an empty trailing item')
    return values


def list_items(inner, strict=True):
    """Split outside quotes, respecting JSON escapes and YAML doubled single quotes.

    Only a quote starting an item opens quoting: an apostrophe in a plain name is
    literal. Strict union reads also validate syntax and decoded values; catalogue
    reads retain the shipped tolerance for trailing commas and partial lists.
    """
    items, buf, quote, position = [], '', None, 0
    while position < len(inner):
        ch = inner[position]
        if quote:
            buf += ch
            if quote == '"' and ch == '\\':
                position += 1
                if position >= len(inner):
                    if strict: raise ProbeError('unterminated quote in a frontmatter list')
                    break
                buf += inner[position]
            elif ch == quote:
                if quote == "'" and inner[position + 1:position + 2] == "'":
                    buf += "'"; position += 1
                else:
                    quote = None
        elif ch in ('"', "'") and not buf.strip():
            quote = ch; buf += ch
        elif ch == ',':
            items.append(buf.strip()); buf = ''
        else:
            buf += ch
        position += 1
    if quote and strict: raise ProbeError('unterminated quote in a frontmatter list')
    if buf.strip(): items.append(buf.strip())
    if not strict: return [item for item in items if item]
    if list_values(inner) != [list_value(item) for item in items]:
        raise ProbeError('frontmatter list splitter disagrees with independent validation')
    return items


def valid_stamp(value):
    """A calendar date in ISO form; anything else disqualifies the stamp (CR-PLANNER P22)."""
    try:
        datetime.strptime(value, '%Y-%m-%d'); return True
    except ValueError:
        return False


CODE_KINDS = {'fence': 'fence', 'code_block': 'indented code block', 'html_block': 'HTML block'}
KIND_NAMES = dict(CODE_KINDS, heading='heading', paragraph='paragraph', bullet_list='bullet list', ordered_list='ordered list', list_item='list item', blockquote='blockquote', hr='thematic break')
LINE_SEPARATORS = '\x0b\x0c\x1c\x1d\x1e\x85\N{LINE SEPARATOR}\N{PARAGRAPH SEPARATOR}'  # str.splitlines breaks on these; CommonMark does not.
RESIDUE = (('%%', 'Obsidian comment'), ('$$', 'maths block'))  # Round five's patterns, for what CommonMark cannot place.
RESIDUE_NOTE = 'not CommonMark, so the parser cannot place it'
MARKDOWN = MarkdownIt('commonmark') if MarkdownIt else None


def is_blank(line):
    """CommonMark's blank line: spaces and tabs only (a no-break space is text)."""
    return not line.rstrip('\r\n').strip(' \t')


def quoted(line):
    return repr(line.rstrip('\r\n'))


class Block:
    __slots__ = ('kind', 'start', 'end', 'parent', 'depth', 'level', 'markup', 'title')

    def __init__(self, kind, start, end, parent, depth, level, markup):
        self.kind, self.start, self.end, self.parent = kind, start, end, parent
        self.depth, self.level, self.markup, self.title = depth, level, markup, ''


class Page:
    """A page as markdown-it-py reads it: frontmatter by frontmatter_end, body by the parser.

    The one reader of Markdown blocks (page_view caches it per text). Every block
    keeps the parser's line range [start, end) shifted into the file's own line
    numbers by the frontmatter's line count, with its parent, children and depth:
    headings with their level, lists and list items with their nesting, fences,
    indented code, HTML blocks, blockquotes, paragraphs and thematic breaks.
    chains[line] lists the blocks that hold a line, outermost first; a line the
    parser gives no block (a link reference definition) has only its containers.
    sections[heading] = (first line, end, own end): a section runs from its
    top-level heading to the next top-level heading of the same or higher level,
    and its own text stops at the next top-level heading of any level. No line
    scanning decides a block.
    """

    def __init__(self, text):
        if MARKDOWN is None:
            raise ProbeError('markdown-it-py not importable (' + str(PARSER_ERROR) + ')')
        self.lines = text.splitlines(keepends=True)
        self.offset = frontmatter_end(text) + 1
        # str.splitlines also ends a line at characters CommonMark keeps inside one;
        # union paths refuse such a body (line_safe), since the numbering would differ.
        self.separator = next(((index, ch) for index in range(self.offset, len(self.lines)) for ch in self.lines[index] if ch in LINE_SEPARATORS), None)
        count = len(self.lines) - self.offset
        try:
            tokens = MARKDOWN.parse(''.join(self.lines[self.offset:]))
        except Exception as error:  # A parser failure on one page is that page's hand read.
            raise UnionRefusal('union placement refused: markdown-it-py could not read this page (' + type(error).__name__ + ')') from error
        self.blocks, self.children, stack = [], [], []
        for token in tokens:
            if token.nesting < 0:
                stack.pop(); continue
            if token.type == 'inline':
                if stack and self.blocks[stack[-1]].kind == 'heading': self.blocks[stack[-1]].title = token.content.strip()
                continue
            kind = token.type[:-len('_open')] if token.nesting > 0 else token.type
            if not token.map or not 0 <= token.map[0] < token.map[1] <= count:
                raise UnionRefusal('union placement refused: the parser gave a ' + kind + ' block no usable line range')
            parent = stack[-1] if stack else None
            level = int(token.tag[1:]) if kind == 'heading' else 0
            self.blocks.append(Block(kind, token.map[0] + self.offset, token.map[1] + self.offset, parent, token.level, level, token.markup))
            self.children.append([])
            if parent is not None: self.children[parent].append(len(self.blocks) - 1)
            if token.nesting > 0: stack.append(len(self.blocks) - 1)
        if stack:
            raise UnionRefusal('union placement refused: the parser left a block open')
        self.chains = [[] for _ in self.lines]
        for index, block in enumerate(self.blocks):
            for line in range(block.start, block.end): self.chains[line].append(index)
        self.headings = [index for index, block in enumerate(self.blocks) if block.kind == 'heading' and block.depth == 0]
        self.sections = {}
        for position, index in enumerate(self.headings):
            later, level = self.headings[position + 1:], self.blocks[index].level
            end = next((self.blocks[n].start for n in later if self.blocks[n].level <= level), len(self.lines))
            self.sections[index] = (self.blocks[index].end, end, self.blocks[later[0]].start if later else len(self.lines))

    def title(self, index):
        """A heading block as canonical ATX text: its level, then the parser's content."""
        block = self.blocks[index]
        return '#' * block.level + (' ' + block.title if block.title else '')

    def titles(self):
        return [self.title(index) for index in self.headings]

    def section_of(self, line):
        """The innermost section holding a body line, by its heading block; None above the first heading.

        The innermost section is the nearest top-level heading above the line, of any
        level, so an addition under a ### sub-heading of Key Points belongs to the
        sub-heading, never to Key Points (CR-PLANNER P04, P05).
        """
        holding = [index for index, (start, end, _) in self.sections.items() if start <= line < end]
        return max(holding, key=lambda index: self.blocks[index].start, default=None)

    def own_end(self, heading):
        """Where a section's own text stops: the next top-level heading of any level."""
        return self.sections[heading][2]

    def last_content(self, start, end):
        """One past the last non-blank line of a parser range [start, end), or start when all are blank.

        List and list-item ranges run on over the blank lines after them; the item's
        content ends at its last line that is not blank as CommonMark defines blank.
        """
        return next((index + 1 for index in range(end - 1, start - 1, -1) if not is_blank(self.lines[index])), start)

    def item_starts(self, start, end):
        """First lines of the top-level list items starting in [start, end)."""
        return [block.start for block in self.blocks if block.kind == 'list_item' and block.depth == 1 and start <= block.start < end]

    def shapes(self, ids, shared):
        """Each shared non-blank body line's blocks, outermost first, as (kind, level, shared lines held)."""
        holds = [frozenset(ids[index] for index in range(block.start, block.end) if ids[index] in shared and not is_blank(self.lines[index])) for block in self.blocks]
        return {ids[index]: tuple((self.blocks[n].kind, self.blocks[n].level, holds[n]) for n in self.chains[index]) for index in range(self.offset, len(self.lines)) if ids[index] in shared and not is_blank(self.lines[index])}


@functools.lru_cache(maxsize=512)
def page_view(text):
    """The parsed page, shared by every read of the same text within one run."""
    return Page(text)


def line_safe(view, where):
    """Refuse a union path whose body splitlines and the parser would number differently."""
    if view.separator:
        index, ch = view.separator
        raise UnionRefusal(f'union placement refused: line separator U+{ord(ch):04X} at {where} line {index + 1} · the parser and the diff would number lines differently')


def residue_constructs(line):
    """The page guard's residue: round five's markers for what CommonMark cannot place."""
    return [name for marker, name in RESIDUE if marker in line]


def union_list_items(inner, location):
    try: return list_items(inner)
    except ProbeError as error:
        raise UnionRefusal('union list refused: ' + location + ' · ' + str(error)) from error


def guard_union(member):
    """The page guard's residue and the strict frontmatter reads; frontmatter stays out of the scan.

    Obsidian comments and maths blocks are not CommonMark, so the parser cannot
    place them: %% or $$ anywhere in the body or in a member's added body lines is
    a hand read. The parser places every other construct (placement below).
    """
    text = member.get('text', '')
    source, fm_end = text.splitlines(), frontmatter_end(text)
    for index in range(fm_end + 1, len(source)):
        constructs = residue_constructs(source[index])
        if constructs:
            raise UnionRefusal(f'union page guard: {constructs[0]} at page line {index + 1} · {RESIDUE_NOTE}')
    frontmatter(text, strict_aliases=True)
    # Validate the contents of existing single-line lists, preserving row
    # comments. Untouched multiline values are not single-line list merges.
    # A refusal cannot abort another target or an ordinary single update.
    for index in range(1, fm_end):
        row = re.fullmatch(r'^(sources|aliases):\s*(\[.*)', source[index])
        if row and ']' in row[2]:
            location = f'{row[1]} at page line {index + 1}'
            inner, suffix = flow_list_parts(row[2])
            if suffix and not suffix.startswith('#'):
                raise UnionRefusal('union list refused: ' + location + ' · text after closing bracket')
            union_list_items(inner, location)
    parsed = member.get('parsed')
    if not parsed: return
    lane = member.get('claim', {}).get('lane', 'unnamed')
    changed = member.get('changed')
    if changed is not None:
        frontmatter(changed, strict_aliases=True, location='member ' + str(lane))
    for offset, _, new_offset, _, body in parsed['hunks']:
        old_position, new_position = offset, new_offset
        for line in body:
            tag, content = line[0], line[1:]
            if tag == '+' and (fm_end < 0 or old_position > fm_end):
                constructs = residue_constructs(content)
                if constructs:
                    raise UnionRefusal(f'union page guard: {constructs[0]} at member {lane} added line {new_position + 1} · {RESIDUE_NOTE}')
            old_position += tag in ' -'
            new_position += tag in ' +'


def proposal(member):
    """The member's page as its own hunks state it (zero-context hunks included).

    Returns the text and, per line, ('E', base line) for a line of the current page
    or ('A', line) for an added line, so the parser's two readings can be compared.
    """
    source = member['text'].splitlines(keepends=True)
    lines, ids, cursor = [], [], 0
    for offset, count, _, _, body in member['parsed']['hunks']:
        for index in range(cursor, min(offset, len(source))):
            lines.append(source[index]); ids.append(('E', index))
        old = offset
        for line in body:
            if line[0] in ' +':
                ids.append(('E', old) if line[0] == ' ' else ('A', len(lines)))
                lines.append(line[1:])
            old += line[0] in ' -'
        cursor = offset + count
    for index in range(cursor, len(source)):
        lines.append(source[index]); ids.append(('E', index))
    return ''.join(lines), ids


def hunks_apply(text, parsed):
    """Whether every hunk's old lines match the page exactly: apply_memory's test, applying nothing."""
    source, produced, cursor = text.splitlines(keepends=True), 0, 0
    for offset, count, noffset, _, body in parsed['hunks']:
        produced += max(0, min(offset, len(source)) - cursor)
        if offset > len(source) or source[offset:offset + count] != [line[1:] for line in body if line[0] in ' -'] or produced != noffset:
            return False
        produced += sum(line[0] in ' +' for line in body)
        cursor = offset + count
    return True


def outline(shape):
    return ' > '.join(f'{KIND_NAMES.get(kind, kind)} of {len(held)} line{"s" if len(held) != 1 else ""}' for kind, _, held in shape) or 'no block'


def construct(block):
    return 'Setext heading' if block.kind == 'heading' and block.markup in ('=', '-') else KIND_NAMES.get(block.kind, block.kind)


def changed_block(lane, view, ids, index, was, now):
    """Name the construct and the added line behind an existing line's changed blocks."""
    line, chain = quoted(view.lines[index]), [view.blocks[n] for n in view.chains[index]]
    for block in chain:
        added = [i for i in range(block.start, block.end) if ids[i][0] == 'A']
        if construct(block) == 'Setext heading' and added:
            if added[0] == block.start:
                return f'union placement refused: Setext heading at member {lane} added line {block.start + 1} {quoted(view.lines[block.start])} takes existing line {index + 1} {line} as its underline'
            return f'union placement refused: Setext heading at member {lane} added line {added[-1] + 1} {quoted(view.lines[added[-1]])} turns existing line {index + 1} {line} into a heading'
    opened = [block for block in chain if ids[block.start][0] == 'A']
    if opened:
        # The unit that took the line in: the added list item, else the innermost added block.
        block = next((block for block in reversed(opened) if block.kind == 'list_item'), opened[-1])
        return f'union placement refused: {construct(block)} at member {lane} added line {block.start + 1} {quoted(view.lines[block.start])} takes existing line {index + 1} {line} into its {"item" if block.kind == "list_item" else construct(block)}'
    depth = next((d for d, (a, b) in enumerate(zip(was, now)) if a != b), min(len(was), len(now)))
    kinds = [shape[depth][0] for shape in (was, now) if depth < len(shape)]
    special = [kind for kind in kinds if kind in CODE_KINDS or kind == 'heading']
    kind = special[0] if special else (kinds[-1] if kinds else 'paragraph')
    added = [i for i in range(view.offset, len(ids)) if ids[i][0] == 'A']
    culprit = max((i for i in added if i < index), default=added[0] if added else None)
    where = f'member {lane} added line {culprit + 1}' if culprit is not None else f'member {lane}'
    return f'union placement refused: {KIND_NAMES.get(kind, kind)} at {where} · existing line {index + 1} {line} changes its blocks ({outline(was)} -> {outline(now)})'


def placement(member):
    """Refuse, before ordinary classification, what the parser shows an addition changing.

    Reads the current page and the member's proposal with the parser. An added line
    inside a fence, an indented code block or an HTML block (critic rounds 1 to 4),
    and an existing line whose blocks change (an added item taking in a nested
    child, a continuation or a lazy line, S10c and A03; a Setext underline, R17; a
    swallowing fence or HTML block) make the target a hand read, never a union.
    Returns the proposal's text, line identities and parsed page.
    """
    text, ids = proposal(member)
    base, view = page_view(member['text']), page_view(text)
    lane = member.get('claim', {}).get('lane', 'unnamed')
    line_safe(base, 'page')
    line_safe(view, f'member {lane} proposed')
    for index in range(view.offset, len(view.lines)):
        if ids[index][0] != 'A': continue
        for n in view.chains[index]:
            block = view.blocks[n]
            if block.kind in CODE_KINDS:
                opener = ('added' if ids[block.start][0] == 'A' else 'existing') + f' line {block.start + 1}'
                raise UnionRefusal(f'union placement refused: {CODE_KINDS[block.kind]} at member {lane} added line {index + 1} · the parser reads {quoted(view.lines[index])} inside the {CODE_KINDS[block.kind]} of lines {block.start + 1}-{block.end}, opened by {opener}')
    existing = {ident for ident in ids if ident[0] == 'E'}
    before = base.shapes([('E', index) for index in range(len(base.lines))], existing)
    after = view.shapes(ids, existing)
    changed = [index for index in range(view.offset, len(view.lines)) if ids[index] in before and before[ids[index]] != after.get(ids[index])]
    if changed:
        # Name first an existing line that an added block took in (the S10c class).
        taken = next((index for index in changed if any(ids[view.blocks[n].start][0] == 'A' for n in view.chains[index])), changed[0])
        raise UnionRefusal(changed_block(lane, view, ids, taken, before[ids[taken]], after.get(ids[taken], ())))
    return text, ids, view


def joined_list(view, ids, at, base_count):
    """Where an added top-level list item sits in its member's proposal.

    ('list', first base line of the list) when it joins a list holding existing
    lines; ('at', base line) naming the line before which it starts a list of its
    own; None when the parser does not read the line as a top-level list item of
    its own holding a block on that line. An item holding only a link reference
    definition has no block and would define a label for the whole page.
    """
    item = next((n for n in view.chains[at] if view.blocks[n].kind == 'list_item' and view.blocks[n].start == at and view.blocks[n].depth == 1), None)
    if item is None: return None
    block = view.blocks[item]
    if [index for index in range(block.start, block.end) if not is_blank(view.lines[index])] != [at]: return None
    if not any(view.blocks[child].start == at for child in view.children[item]): return None
    holder = view.blocks[block.parent]
    existing = [ids[index][1] for index in range(holder.start, holder.end) if ids[index][0] == 'E' and not is_blank(view.lines[index])]
    if existing: return ('list', min(existing))
    return ('at', next((ids[index][1] for index in range(at + 1, len(ids)) if ids[index][0] == 'E'), base_count))


def list_additions(member):
    """Return (list-item additions, confidence edit, frontmatter merges), or None for a non-union.

    The parser reads the member's proposal as its hunks state it: a moved base has
    already failed inspection, so its otherwise eligible re-base is manual, while
    valid hunks agree exactly with the current page. Offsets never establish
    disjointness. Each body addition must be a list item of its own, as the parser
    reads it, under a UNION_HEADINGS heading; it records the list it joins, or where
    it starts its own, for compose_union. Frontmatter may only re-date a stamp key
    or append items to a single-line sources:/aliases: list (a superset of the
    page's own list); every other change returns None. Placement refusals come first.
    """
    parsed = member.get('parsed')
    # Competing creates already conflict; they have no current page to union.
    if parsed is not None and parsed['old'] is None: return None
    guard_union(member)
    if parsed is None or parsed['old'] is None:
        return None
    source = member['text'].splitlines(keepends=True)
    fm_end = frontmatter_end(member['text'])

    def body_removal():
        for offset, _, _, _, body in parsed['hunks']:
            position = offset
            for line in body:
                if line[0] == '-' and not (fm_end > 0 and position < fm_end): return True
                position += line[0] in ' -'
        return False
    # An edited or removed body line is conflict by the ordinary rule below; a
    # diff that does not apply is manual through its inspection problems.
    if hunks_apply(member['text'], parsed) and not body_removal():
        _, ids, view = placement(member)
    else:
        text, ids = proposal(member)
        view = page_view(text)
    additions, confidence_edit = [], False
    stamps, lists, removed = {}, {}, {}
    here = cursor = 0
    for offset, count, new_offset, _, body in parsed['hunks']:
        position = offset
        new_position = new_offset
        here += min(offset, len(source)) - min(cursor, len(source))
        for line in body:
            tag, content = line[0], line[1:]
            new_position += tag in ' +'
            at = here
            here += tag in ' +'
            if not 0 <= position <= len(source): return None
            # A removed line sits at its old position; an added line is inserted before it, so an
            # addition at the closing --- (position == fm_end) still belongs to the frontmatter.
            in_frontmatter = fm_end > 0 and (position < fm_end if tag == '-' else position <= fm_end)
            if tag == ' ':
                position += 1; continue
            if in_frontmatter and re.match(r'^confidence:\s*', content):
                confidence_edit = True
                position += tag == '-'
                continue
            if in_frontmatter:
                key = content.split(':', 1)[0].strip()
                if key in STAMP_KEYS and re.match(r'^(updated|audited): \d{4}-\d{2}-\d{2}\s*$', content):
                    value = content.split(':', 1)[1].strip()
                    if not valid_stamp(value): return None
                    if tag == '-': removed[key] = content
                    else: stamps[key] = value
                    position += tag == '-'; continue
                match = FM_LIST.match(content)
                if match and match[1] in LIST_KEYS:
                    lane = member.get('claim', {}).get('lane', 'unnamed')
                    location = f'member {lane} line {new_position}' if tag == '+' else f'page line {position + 1}'
                    items = union_list_items(match[2], match[1] + ' at ' + location)
                    if tag == '-': removed[match[1]] = items
                    else: lists[match[1]] = items
                    position += tag == '-'; continue
                return None
            if tag == '-': return None
            if not content.startswith('- ') or content.strip() == '-':
                return None
            # The parser's reading of the member's own proposal decides the list
            # item and its section; a thematic break such as "- - -" is no item.
            place = joined_list(view, ids, at, len(source))
            section = view.section_of(at)
            heading = view.title(section) if section is not None else ''
            if place is None or heading not in UNION_HEADINGS:
                return None
            additions.append((heading, content, place, at))
        cursor = offset + count
    for key, old in removed.items():
        if key in STAMP_KEYS:
            if key not in stamps: return None
        elif key not in lists or not set(old) <= set(lists[key]):
            return None
    merges = {}
    for key, items in lists.items():
        old = removed.get(key)
        if old is None: return None  # a list added from nothing is not an append
        merges[key] = [x for x in items if x not in old]
    if not additions and not stamps and not merges:
        return None
    return (additions, confidence_edit, {'stamps': stamps, 'lists': merges})


def normalise_link_line(line):
    """Collapse whitespace only; names, punctuation, case and glosses stay distinct."""
    return ' '.join(line.split())


def item_span(view, at):
    """The complete top-level item starting here, excluding trailing blank lines."""
    item = next((view.blocks[n] for n in view.chains[at] if view.blocks[n].kind == 'list_item' and view.blocks[n].depth == 1 and view.blocks[n].start == at), None)
    return (at, view.last_content(at, item.end)) if item is not None else None


def same_context_duplicate(left, left_ids, at, right, right_ids, other):
    """Complete items with the same blocks, section and position amongst base lines.

    Whitespace collapse is the existing text equivalence, applied to every line,
    never just the first. The parser still distinguishes nesting and continuation
    blocks. Excluding the two items themselves lets an adjacent repeat match its
    existing occurrence, but never one across another anchor or section boundary.
    """
    a, b = item_span(left, at), item_span(right, other)
    if a is None or b is None: return False
    if tuple(map(normalise_link_line, left.lines[a[0]:a[1]])) != tuple(map(normalise_link_line, right.lines[b[0]:b[1]])): return False
    ignored = {ident for ids, span in ((left_ids, a), (right_ids, b)) for ident in ids[span[0]:span[1]] if ident[0] == 'E'}
    def context(view, ids, span):
        start, end = span
        shared = {ident for ident in ids if ident[0] == 'E'} - ignored
        heading = view.section_of(start)
        section = ids[view.blocks[heading].start] if heading is not None else None
        previous = next((i for i in range(start - 1, -1, -1) if ids[i] in shared), -1)
        following = next((i for i in range(end, len(ids)) if ids[i] in shared), len(ids))
        # New anchors matter too: equal text following different additions in
        # the same base gap is still a distinct occurrence in its proposal.
        added_before = tuple(normalise_link_line(view.lines[i]) for i in range(previous + 1, start) if ids[i][0] == 'A')
        added_after = tuple(normalise_link_line(view.lines[i]) for i in range(end, following) if ids[i][0] == 'A')
        blocks = tuple((view.blocks[n].kind, view.blocks[n].level, frozenset(ids[i] for i in range(view.blocks[n].start, view.blocks[n].end) if ids[i] in shared and not is_blank(view.lines[i]))) for n in view.chains[start])
        return section, ids[previous] if previous >= 0 else None, ids[following] if following < len(ids) else None, added_before, added_after, blocks
    return context(left, left_ids, a) == context(right, right_ids, b)


def check_composed(changed, origin, members, views, kept, duplicates=None):
    """The composed-page oracle: parse the union and compare it with every member's proposal.

    For each member, every current-page line and EVERY added body line must
    sit in the blocks its proposal gave it (the same list, the same item, the same
    kinds, counted over shared identities), and each addition under the same
    heading. A missing addition needs a verified complete same-context duplicate;
    the caller's kept list cannot exempt it. Frontmatter additions must survive
    their permitted stamp/list merge. Any deviation is a hand read.
    """
    view = page_view(changed)
    duplicates = duplicates or {}
    where = {ident: index for index, ident in enumerate(origin)}
    base = page_view(members[0]['text'])
    base_ids = [('E', index) for index in range(len(base.lines))]
    def representative(ident):
        return duplicates.get(ident, ident)
    def remap(shape):
        return tuple((kind, level, frozenset(map(representative, held))) for kind, level, held in shape)
    for number, (member, (proposed, ids)) in enumerate(zip(members, views)):
        lane = member.get('claim', {}).get('lane', 'unnamed')
        own = {ident for index, ident in enumerate(ids) if ident[0] == 'A' and index >= proposed.offset}
        for ident in sorted(own):
            mine = ident[2]
            rep = representative(ident)
            if ident not in where:
                if rep == ident or rep not in where:
                    raise ProbeError(f'union placement refused: member {lane} added line {mine + 1} {quoted(proposed.lines[mine])} was dropped without an exact same-context duplicate')
                other_view, other_ids = (base, base_ids) if rep[0] == 'E' else views[rep[1]]
                other = rep[1] if rep[0] == 'E' else rep[2]
                if not same_context_duplicate(proposed, ids, mine, other_view, other_ids, other):
                    raise ProbeError(f'union placement refused: member {lane} added line {mine + 1} {quoted(proposed.lines[mine])} was dropped against line {other + 1} {quoted(other_view.lines[other])} in a different context')
            if normalise_link_line(proposed.lines[mine]) != normalise_link_line(view.lines[where[rep]]):
                raise ProbeError(f'union placement refused: member {lane} added line {mine + 1} {quoted(proposed.lines[mine])} changed text at composed page line {where[rep] + 1} {quoted(view.lines[where[rep]])}')
        # Metadata lines are intentionally folded rather than copied. Check each
        # added line against the composed value, including lines with no body item.
        for index, ident in enumerate(ids[:proposed.offset]):
            if ident[0] != 'A': continue
            row = proposed.lines[index].rstrip('\r\n')
            key, _, value = row.partition(':')
            actual = [line.rstrip('\r\n').partition(':')[2].strip() for line in view.lines[1:view.offset - 1] if line.startswith(key + ':')]
            survives = len(actual) == 1
            if survives and key in STAMP_KEYS:
                survives = valid_stamp(actual[0]) and actual[0] >= value.strip()
            elif survives and key in LIST_KEYS:
                match = FM_LIST.fullmatch(row)
                actual_match = FM_LIST.fullmatch(key + ': ' + actual[0])
                survives = bool(match and actual_match) and set(list_values(match[2])) <= set(list_values(actual_match[2]))
            else:
                survives = False
            if not survives:
                raise ProbeError(f'union placement refused: member {lane} added frontmatter line {index + 1} {quoted(row)} did not survive its stamp/list merge')
        shared = {ident for ident in ids if ident[0] == 'E'} | own
        wanted, found = proposed.shapes(ids, shared), view.shapes(origin, set(map(representative, shared)))
        for ident in sorted(wanted, key=lambda ident: where.get(representative(ident), -1)):
            rep = representative(ident)
            if found.get(rep) != remap(wanted[ident]):
                index = where.get(rep, 0)
                subject = f'member {lane} added line {ident[2] + 1}' if ident[0] == 'A' else f'existing line {ident[1] + 1}'
                raise ProbeError(f'union placement refused: composed page line {index + 1} {quoted(view.lines[index])} · {subject} leaves the blocks its member proposal gave it ({outline(wanted[ident])} -> {outline(found.get(rep, ()))})')
        for ident in sorted(own, key=lambda ident: where[representative(ident)]):
            index, mine = where[representative(ident)], ids.index(ident)
            heading, intended = view.section_of(index), proposed.section_of(mine)
            if heading is None or intended is None or origin[view.blocks[heading].start] != ids[proposed.blocks[intended].start]:
                raise ProbeError(f'union placement refused: composed page line {index + 1} {quoted(view.lines[index])} · member {lane} added line {ident[2] + 1} lands under a different heading')


def compose_union(members):
    """Compose one diff against the current page, then parse the composed page.

    Each kept addition goes after the last item of the list its member put it in,
    or before the line its member put it before when it starts a list of its own.
    Repeated section headings fail closed; check_composed is the oracle.
    """
    original = members[0]['text']
    lines = original.splitlines(keepends=True)
    origin = [('E', index) for index in range(len(lines))]
    additions, stamps, merges, views = {}, {}, {}, []
    for number, member in enumerate(members):
        if member['text'] != original or member['problems']:
            raise ProbeError('union re-base failed: member base or context differs')
        candidate = list_additions(member)
        if candidate is None or candidate[1]:
            raise ProbeError('union contains a prose or confidence edit')
        text, ids = proposal(member)
        views.append((page_view(text), [('A', number, index) if ident[0] == 'A' else ident for index, ident in enumerate(ids)]))
        for heading, line, place, at in candidate[0]:
            additions.setdefault(heading, []).append((line, place, ('A', number, at)))
        for key, value in candidate[2]['stamps'].items():
            stamps[key] = max(stamps.get(key, ''), value)
        for key, items in candidate[2]['lists'].items():
            merged = merges.setdefault(key, [])
            merged += [x for x in items if x not in merged]
    if not additions and not merges:
        raise ProbeError('union re-base has no new lines; head checks existing lines and merged evidence')
    fm_end = frontmatter_end(original)
    if (stamps or merges) and fm_end < 0:
        raise ProbeError('union re-base failed: frontmatter missing for a stamp or list merge')
    for key, items in merges.items():
        rows = [i for i in range(1, fm_end) if FM_LIST.match(lines[i]) and FM_LIST.match(lines[i])[1] == key]
        if len(rows) != 1:
            raise ProbeError('union re-base failed: ' + key + ' list missing or repeated')
        current = list_items(FM_LIST.match(lines[rows[0]])[2])
        merged = current + [x for x in items if x not in current]
        lines[rows[0]] = key + ': [' + ', '.join(merged) + ']\n'
        if list_values(FM_LIST.match(lines[rows[0]])[2]) != [list_value(item) for item in merged]:
            raise ProbeError('union re-base failed: ' + key + ' list does not round-trip')
    # Replace existing stamp rows first, then insert the missing ones, re-reading the
    # frontmatter bound after every insertion (CR-PLANNER HIGH 3: a shifted row was duplicated).
    for key, value in stamps.items():
        rows = [i for i in range(1, fm_end) if lines[i].startswith(key + ':')]
        if len(rows) > 1:
            raise ProbeError('union re-base failed: ' + key + ' repeated')
        if rows:
            current = lines[rows[0]].split(':', 1)[1].strip()
            lines[rows[0]] = key + ': ' + (max(current, value) if valid_stamp(current) else value) + '\n'
    for key, value in stamps.items():
        fm_end = frontmatter_end(''.join(lines))
        if any(lines[i].startswith(key + ':') for i in range(1, fm_end)): continue
        anchor = [i for i in range(1, fm_end) if lines[i].startswith('confidence:')]
        if len(anchor) != 1:
            raise ProbeError('union re-base failed: no confidence line to place ' + key)
        lines.insert(anchor[0] + 1, key + ': ' + value + '\n')
        origin.insert(anchor[0] + 1, ('F', key))
    base, inserts, kept, duplicates = page_view(original), {}, [], {}
    base_ids = [('E', index) for index in range(len(base.lines))]
    for heading, entries in additions.items():
        starts = [index for index in base.headings if base.title(index) == heading]
        if len(starts) != 1:
            raise ProbeError('union re-base failed: list heading missing or repeated')
        start, end = base.blocks[starts[0]].end, base.own_end(starts[0])
        # Each candidate keeps its complete parser item and its original position;
        # first-line equality across a section is never evidence of duplication.
        seen = [(base, base_ids, index, ('E', index)) for index in base.item_starts(start, end) if base.lines[index].startswith('- ')]
        for line, place, ident in entries:
            proposed, ids = views[ident[1]]
            duplicate = next((other_ident for other_view, other_ids, other, other_ident in seen if same_context_duplicate(proposed, ids, ident[2], other_view, other_ids, other)), None)
            if duplicate is not None:
                duplicates[ident] = duplicate
                continue
            seen.append((proposed, ids, ident[2], ident))
            if place[0] == 'list':
                holder = base.blocks[next(n for n in base.chains[place[1]] if base.blocks[n].depth == 0)]
                at = base.last_content(holder.start, holder.end)
            else:
                at = place[1]
            inserts.setdefault(at, []).append((line if line.endswith('\n') else line + '\n', ident))
    for at in sorted(inserts, reverse=True):
        # Current-page line numbers map through origin, which stamp rows shifted.
        where = origin.index(('E', at)) if at < len(base.lines) else len(lines)
        # An EOF line may lack a final newline. Give the appended
        # items their own line and represent the old EOF exactly in the diff.
        if where and not lines[where - 1].endswith('\n'): lines[where - 1] += '\n'
        lines[where:where] = [line for line, _ in inserts[at]]
        origin[where:where] = [ident for _, ident in inserts[at]]
        kept += [ident for _, ident in inserts[at]]
    changed = ''.join(lines)
    check_composed(changed, origin, members, views, kept, duplicates)
    target = members[0]['target']
    diff_lines = difflib.unified_diff(original.splitlines(keepends=True), changed.splitlines(keepends=True), fromfile=str(target), tofile=str(target))
    patch = ''.join(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n' for line in diff_lines)
    if not patch:
        raise ProbeError('union re-base has no new lines; head checks existing lines and merged evidence')
    return patch


def emit_union(directory, target, patch, vault):
    """The sole write exception: exclusive creation inside explicitly named scratch.

    Existing identical bytes are reusable; different bytes are never overwritten.
    The content hash gives deterministic, collision-resistant artefact names.
    """
    scratch = Path(directory).expanduser().resolve()
    if not scratch.is_dir() or scratch.is_relative_to(vault):
        raise ProbeError('--union-dir must be an existing scratch directory outside the vault')
    filename = normalise(target.stem) + '-' + digest(patch.encode('utf-8')) + '.diff'
    path = scratch / filename
    if path.is_symlink(): raise ProbeError('union artefact is a symlink')
    try:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(patch)
    except FileExistsError:
        if path.read_text(encoding='utf-8') != patch:
            raise ProbeError('union artefact already exists with different bytes')
    return path


def patch_command(vault, target, diff, reject, dry=True):
    # Explicit target prevents header spelling differences changing patch's target.
    # F0 derives from exact-context anchoring; -N is only a replay probe, never proof.
    flags = ['patch', '-F0', '-N', '--no-backup-if-mismatch', '-r', str(reject)]
    if dry: flags.append('--dry-run')
    flags += [str(target), str(diff)]
    return shlex.join(flags)


def check_read_receipt(receipt, expected, diff_hash):
    """Bind the explicit full-page read acknowledgement to the held bytes."""
    base, sep, held_hash = receipt.partition(':')
    pattern = r'[0-9a-f]{' + str(HASH_LENGTH) + '}'
    if not sep or not re.fullmatch(pattern, held_hash) or (base != 'absent' and not re.fullmatch(pattern, base)):
        raise ProbeError('--after-read wants the printed BASE:DIFF_HASH pair')
    if held_hash != diff_hash:
        raise ProbeError('resolved diff hash is not the held artefact: expected ' + held_hash + ', observed ' + diff_hash)
    observed = expected if expected is not None else 'absent'
    if base != observed:
        raise ProbeError('resolved base is not the held page: expected ' + base + ', observed ' + observed)


def read_release(vault, target, path, expected, diff_hash, kind):
    receipt = (expected if expected is not None else 'absent') + ':' + diff_hash
    command = shlex.join(['merge_plan.py', '--vault', str(vault), '--resolved', str(path), '--after-read', receipt])
    return 'held until the full-page read: ' + str(target) + ' · ' + kind + ' diff ' + str(path) + ' · then: ' + command


def resolved_plan(args, vault):
    """Prepare the whole batch, then recheck bytes before printing any commands."""
    if args.after_read and len(args.after_read) != len(args.resolved):
        raise ProbeError('pair every --resolved with its own --after-read BASE:DIFF_HASH')
    ready, output = [], []
    for index, name in enumerate(args.resolved):
        path = Path(name).expanduser().resolve()
        data = path.read_bytes()
        parsed = parse_diff(data.decode('utf-8'), vault)
        target = parsed['new']
        old_bytes = target.read_bytes() if parsed['old'] else b''
        old = old_bytes.decode('utf-8')
        expected = digest(old_bytes) if parsed['old'] else None
        diff_hash = digest(data)
        if args.after_read: check_read_receipt(args.after_read[index], expected, diff_hash)
        # Content-addressed union names also detect replacement without an
        # acknowledgement, preserving the ordinary --resolved artefact path.
        named_hash = re.fullmatch(re.escape(normalise(target.stem)) + r'-([0-9a-f]{' + str(HASH_LENGTH) + r'})\.diff', path.name)
        if named_hash and named_hash[1] != diff_hash:
            raise ProbeError('resolved diff hash differs from the held union artefact name')
        new = apply_memory(old, parsed)
        lift = bool(parsed['old']) and TIERS.get(frontmatter(new).get('confidence'), -1) > TIERS.get(frontmatter(old).get('confidence'), -1)
        if lift and not args.after_read:
            output.append('confidence lift: read the page in full before applying · ' + str(target))
            output.append(read_release(vault, target, path, expected, diff_hash, 'resolved'))
        else:
            output.append(('confidence lift: full-page read acknowledged · ' if lift else 'no confidence lift: read the diff, then apply · ') + str(target))
            output.append('base recheck immediately before real patch: ' + (expected if expected is not None else 'target absent'))
            output.append(patch_command(vault, target, path, path.parent / 'apply.rej'))
            output.append('after dry-run and base recheck: ' + patch_command(vault, target, path, path.parent / 'apply.rej', False))
        ready.append((target, path, expected, data))
    output.append('controls: quoted high parsed · non-raising medium parsed · valid apply and conflict classified · held diff identity checked')
    # No output containing commands precedes these checks. The expected hash
    # comes from the initial bytes, never from this last disk observation.
    for target, path, expected, data in ready:
        drift = base_problem(target, expected)
        if drift: raise ProbeError(str(target) + ': ' + drift)
        if path.read_bytes() != data: raise ProbeError('resolved diff hash changed during planning: ' + str(path))
    print('\n'.join(output))
    return 0


def _control_hunks(diff):
    """Hunks of a fixture diff for planted(): the parse_diff body without the header path rule."""
    lines = diff.splitlines(keepends=True)[2:]
    hunks, i = [], 0
    while i < len(lines):
        match = HUNK.fullmatch(lines[i].rstrip('\n'))
        if not match: raise ProbeError('control diff hunk header')
        start, count = int(match[1]), int(match[2] or 1)
        nstart, ncount = int(match[3]), int(match[4] or 1)
        offset = start if count == 0 else start - 1
        noffset = nstart if ncount == 0 else nstart - 1
        body, used, nused = [], 0, 0
        i += 1
        while i < len(lines) and (used < count or nused < ncount):
            tag = lines[i][0]
            used += tag in ' -'; nused += tag in ' +'
            body.append(lines[i]); i += 1
        hunks.append((offset, count, noffset, ncount, body))
    return hunks


def planted():
    if normalise('A B-c!') != normalise('abc') or normalise('abc') == normalise('abd'):
        raise ProbeError('canonicalisation control failed')
    a = {'claim': {'lane': 'A'}, 'problems': [], 'lift': False, 'diff': 'd'}
    b = dict(a, claim={'lane': 'B'}, lift=True)
    if classify([a]) != 'apply' or classify([a, b]) != 'conflict': raise ProbeError('classification controls failed')
    if scalar('"high"') != 'high' or scalar("'medium'") != 'medium': raise ProbeError('quoted confidence controls failed')
    if normalise_link_line('effect > 0') == normalise_link_line('effect < 0') or normalise_link_line('effect  > 0 \t') != normalise_link_line('effect > 0'):
        raise ProbeError('link whitespace controls failed')
    x, y = ('- ' + '[' * 2 + name + ']' * 2 + '\n' for name in ('x', 'y'))
    page = '---\ntitle: T\nconfidence: medium\naudited: 2026-01-01\nsources: [a.md]\n---\n## Key Points\n- old\n\n## Related\n' + x
    def member(new, text=page):
        diff = ''.join(difflib.unified_diff(text.splitlines(keepends=True), new.splitlines(keepends=True), fromfile='a/wiki/x.md', tofile='b/wiki/x.md'))
        return {'text': text, 'changed': new, 'parsed': {'old': 'x', 'new': 'x', 'hunks': _control_hunks(diff)}, 'problems': [], 'lift': False}
    bullet = member(page.replace('- old\n', '- old\n- new bullet\n'))
    prose = member(page.replace('- old\n', '- old\nNew prose.\n'))
    stamped = member(page.replace('audited: 2026-01-01', 'audited: 2026-02-02').replace(x, x + y))
    grown = member(page.replace('sources: [a.md]', 'sources: [a.md, b.md]').replace(x, x + y))
    shrunk = member(page.replace('sources: [a.md]', 'sources: [b.md]').replace(x, x + y))
    removed = member(page.replace('- old\n', ''))
    if list_additions(bullet) is None or list_additions(prose) is not None: raise ProbeError('list-item union controls failed')
    if list_additions(stamped) is None or list_additions(stamped)[2]['stamps'] != {'audited': '2026-02-02'}: raise ProbeError('stamp union control failed')
    if list_additions(grown) is None or list_additions(grown)[2]['lists'] != {'sources': ['b.md']} or list_additions(shrunk) is not None: raise ProbeError('sources union controls failed')
    if list_additions(removed) is not None: raise ProbeError('removed-line control failed')
    nested = page.replace('- old\n', '- parent\n  - child\n')
    try: list_additions(member(nested.replace('  - child\n', '- added\n  - child\n'), nested))
    except UnionRefusal: pass
    else: raise ProbeError('nested re-parenting refusal control failed')
    if list_additions(member(nested.replace('  - child\n', '  - child\n- added\n'), nested)) is None:
        raise ProbeError('complete nested block acceptance control failed')
    undecodable = '"A\\qB"'
    if alias_scalar(undecodable) != 'A\\qB': raise ProbeError('catalogue fallback control failed')
    try: union_list_items(undecodable, 'control')
    except UnionRefusal: pass
    else: raise ProbeError('undecodable union item refusal control failed')
    if list_value('"A\\u0020B"') != 'A B' or list_value("'A\\qB'") != 'A\\qB':
        raise ProbeError('decodable and literal escape controls failed')
    if alias_scalar('"\\x41"') != 'A' or alias_scalar('"\\u0041"') != 'A' or alias_scalar('"\\U00000041"') != 'A':
        raise ProbeError('YAML escape identity controls failed')
    try: list_value('"\\N{DEGREE SIGN}"')
    except ProbeError: pass
    else: raise ProbeError('control-character union item refusal control failed')
    for marker, family in (('- %%', 'Obsidian comment'), ('- $$', 'maths block')):
        if residue_constructs(marker) != [family] or residue_constructs('- ordinary > 0'):
            raise ProbeError('union page guard controls failed: ' + family)
        guarded = page.replace('- old\n', '- old\n' + marker + '\n')
        try: list_additions(member(guarded + '- added\n', guarded))
        except UnionRefusal: pass
        else: raise ProbeError('union page guard refusal control failed: ' + family)
        if list_additions(bullet) is None: raise ProbeError('union page guard clean control failed: ' + family)
    fenced = page.replace('- old\n', '- old\n\n```\n- example\n```\n')
    for family, text, new in (
            ('fence', fenced, fenced.replace('- example\n', '- example\n- inserted\n')),
            ('Setext heading', page.replace('- old\n', '- old\n\nText\n'), page.replace('- old\n', '- old\n\nText\n===\n')),
            ('HTML block', page.replace('- old\n', '- old\n\n<div>\n'), page.replace('- old\n', '- old\n\n<div>\n- inserted\n')),
            ('list item', nested, nested.replace('  - child\n', '- added\n  - child\n'))):
        try: list_additions(member(new, text))
        except UnionRefusal as error:
            if family not in str(error): raise ProbeError('placement refusal names the wrong construct: ' + family)
        else: raise ProbeError('placement refusal control failed: ' + family)
    if list_additions(member(fenced.replace('- old\n', '- old\n- real\n'), fenced)) is None:
        raise ProbeError('placed fence acceptance control failed')
    pseudo = page.replace('- old\n', '- old\n\n**Rejected:**\n- r\n')
    joined = dict(member(pseudo.replace('- old\n', '- old\n- b\n'), pseudo), claim={'lane': 'A'})
    text, ids = proposal(joined)
    views = [(page_view(text), [('A', 0, i) if ident[0] == 'A' else ident for i, ident in enumerate(ids)])]
    at, rows = next(i for i, ident in enumerate(ids) if ident[0] == 'A'), pseudo.splitlines(keepends=True)
    for index, expect in ((rows.index('- old\n') + 1, True), (rows.index('- r\n') + 1, False)):
        origin = [('E', i) for i in range(index)] + [('A', 0, at)] + [('E', i) for i in range(index, len(rows))]
        try: check_composed(''.join(rows[:index] + ['- b\n'] + rows[index:]), origin, [joined], views, [('A', 0, at)]); accepted = True
        except ProbeError: accepted = False
        if accepted != expect: raise ProbeError('composed-page oracle controls failed')
    block_alias = frontmatter('---\naliases:\n  - "A\\u0020B"\n---\n')['aliases']
    flow_alias = frontmatter('---\naliases: ["A B",]\n---\n')['aliases']
    if block_alias != ['A B'] or block_alias != flow_alias:
        raise ProbeError('lenient block/flow alias controls failed')
    if flow_list_parts('["A ] # B"] # [comment]') != ('"A ] # B"', '# [comment]'):
        raise ProbeError('flow list/comment boundary control failed')
    try: union_list_items('"A B",', 'control')
    except UnionRefusal: pass
    else: raise ProbeError('strict union list control failed')
    escaped = ['First "shared, tail"', 'Second "shared, tail"']
    encoded = [json.dumps(item) for item in escaped]
    if list_items(', '.join(encoded)) != encoded or list_values(', '.join(encoded)) != escaped:
        raise ProbeError('escaped frontmatter list controls failed')
    if list_items("O'Brien, 'O''Brien, quoted'") != ["O'Brien", "'O''Brien, quoted'"]:
        raise ProbeError('apostrophe frontmatter controls failed')
    try: list_items('plain, "unfinished')
    except ProbeError: pass
    else: raise ProbeError('unterminated frontmatter control failed')
    for marker in ('~~~', '````'):
        if [(block.kind, block.start, block.end) for block in page_view(marker + '\n```\n- example\n```\n' + marker + '\n').blocks] != [('fence', 0, 5)]:
            raise ProbeError('mixed fence controls failed')
    if [(block.kind, block.end) for block in page_view('```\n- example\n').blocks] != [('fence', 2)] or [block.kind for block in page_view('```\n```\n- real\n').blocks] != ['fence', 'bullet_list', 'list_item', 'paragraph']:
        raise ProbeError('fence boundary controls failed')
    if page_view('   ### Child\n').titles() != ['### Child'] or page_view('    ### Code\n').titles() or page_view('Title\n---\n').titles() != ['## Title']:
        raise ProbeError('heading controls failed')
    # The install test's premise: a bare fence after an item ending in backticks opens a
    # new fence to the end, and the parser shows that swallowing as a line range.
    if [(block.kind, block.start, block.end) for block in page_view('- a ```\n```\n- b\n').blocks if block.depth == 0] != [('bullet_list', 0, 1), ('fence', 1, 3)]:
        raise ProbeError('parser premise failed: a swallowing fence is not visible as a line range')
    nesting = page_view('## A\n### B\nx\n## C\ny\n')
    a_heading, b_heading, c_heading = nesting.headings
    if nesting.sections[a_heading] != (1, 3, 1) or nesting.section_of(2) != b_heading or nesting.section_of(4) != c_heading or nesting.section_of(0) is not None:
        raise ProbeError('section controls failed')
    if list_additions(member(page.replace('- old\n', '- old\n- [ref]: https://example.org\n'))) is not None or list_additions(member(page.replace('- old\n', '- old\n- [ref] text\n'))) is None:
        raise ProbeError('reference definition item controls failed')
    try: line_safe(page_view('text\x0cmore\n'), 'control')
    except UnionRefusal: pass
    else: raise ProbeError('line separator refusal control failed')
    line_safe(page_view('text more\n'), 'control')
    expected, held_hash = digest(b'base'), digest(b'union')
    check_read_receipt(expected + ':' + held_hash, expected, held_hash)
    for observed_base, observed_diff in ((digest(b'moved'), held_hash), (expected, digest(b'member'))):
        try: check_read_receipt(expected + ':' + held_hash, observed_base, observed_diff)
        except ProbeError: pass
        else: raise ProbeError('held read identity controls failed')
    c = {'_id': 'one', 'name': 'M'}
    if reference_ids([{'name':'M'}], [c]) != {'one'}: raise ProbeError('quarantine control failed')
    try: reference_ids([{'name':'M'}, {'name':'M'}], [c])
    except ProbeError: pass
    else: raise ProbeError('duplicate quarantine control failed')


def plan(args):
    vault = Path(args.vault).expanduser().resolve()
    if not (vault / 'wiki').is_dir(): raise ProbeError('vault has no wiki directory')
    if args.resolved:
        return resolved_plan(args, vault)
    if args.after_read: raise ProbeError('--after-read requires --resolved')
    if not args.ledger: raise ProbeError('plan needs at least one --ledger')
    if args.union_dir:
        scratch = Path(args.union_dir).expanduser().resolve()
        if not scratch.is_dir() or scratch.is_relative_to(vault):
            raise ProbeError('--union-dir must be an existing scratch directory outside the vault')
    version = getattr(markdown_it, '__version__', 'absent')
    if version != PARSER_PIN:
        print('note: markdown-it-py ' + version + ' is not the accepted ' + PARSER_PIN + '; test_merge_plan.sh is the acceptance test for the union rule')
    events, problems = read_events(args.ledger, args.allow_malformed)
    claims = claims_from(events)
    for e in events:
        if e.get('event') == 'verify' and str(e.get('shape', '')).casefold() == 'fail':
            print('note: ' + str(e.get('lane')) + ' · the verifier recorded a claims-shape evidence failure; every claim object is validated here individually')
    issues, dropped = evidence(events, claims, [x for value in args.lanes for x in value.split(',') if x])
    problems += issues
    for file in args.quarantine:
        ids = reference_ids(json.loads(Path(file).read_text(encoding='utf-8')), claims)
        if ids & dropped: raise ProbeError('claim object named twice across quarantine evidence')
        dropped |= ids
    cat = Catalogue(vault)
    for c in claims:
        key = normalise(claim_name(c)); c['_key'] = key
        if not key: raise ProbeError('claim has no canonical name')
        cat.add(key)
        aliases = c.get('aliases', [])
        if not isinstance(aliases, list): raise ProbeError('claim aliases must be a list')
        for alias in aliases: cat.join(key, normalise(alias))
        if isinstance(c.get('diff'), str):
            try:
                path = Path(c['diff']).expanduser()
                if not path.is_absolute(): path = Path(c['_event']['_file']).parent / path
                text = path.read_text(encoding='utf-8')
                parsed = parse_diff(text, vault)
                if parsed['old'] is None:
                    for alias in frontmatter(apply_memory('', parsed)).get('aliases', []): cat.join(key, normalise(alias))
                else:
                    # Read aliases from the changed frontmatter, never from a
                    # similarly spelt example in the body or a code fence.
                    previous = cat.pages.get(parsed['old'])
                    if previous:
                        changed = apply_memory(previous[1], parsed)
                        for alias in frontmatter(changed).get('aliases', []): cat.join(key, normalise(alias))
            except (OSError, ValueError): pass  # inspect_claim records the unusable diff as manual.
    groups = {}
    for c in claims: groups.setdefault(cat.find(c['_key']), []).append(c)
    counts = dict.fromkeys(('apply', 'apply-union', 'conflict', 'manual', 'tier-raised', 'quarantined'), 0)
    applications = []
    for key, all_members in groups.items():
        live = [c for c in all_members if c['_id'] not in dropped]
        paths = cat.targets(key)
        name = paths[0].stem if paths else claim_name(all_members[0])
        if not live:
            counts['quarantined'] += 1; print('quarantined ' + name); continue
        target = paths[0] if paths else vault / 'wiki' / DIRS.get(live[0].get('type'), 'concepts') / (claim_name(live[0]) + '.md')
        if not target.resolve().is_relative_to(vault / 'wiki'): raise ProbeError('claim target escapes wiki')
        members = [inspect_claim(c, target, cat) for c in live]
        drift = base_problem(target, members[0]['expected_base'])
        if drift:
            for member in members: member['problems'].append(drift)
        if len(paths) > 1:
            for member in members: member['problems'].append('multiple existing pages share this canonical name')
        try:
            if len({c['lane'] for c in live}) > 1:
                guard_catalogue_identities(cat, members, paths)
            disposition = classify(members)
        except UnionRefusal as error:
            disposition = 'manual'
            members[0]['problems'].append(str(error))
        union_patch = None
        multi = len({c['lane'] for c in live}) > 1
        # A claim-field lift on a union-eligible multi-lane target composes its union
        # too: the head reads the page in full first, and the union never lifts a tier.
        unionable = multi and disposition == 'tier-raised' and not any(x['problems'] for x in members) and all(
            (cand := list_additions(x)) is not None and not cand[1] for x in members)
        if disposition == 'apply-union' or unionable:
            try:
                union_patch = compose_union(members)
            except ProbeError as e:
                # A held target keeps its class, since the full-page read comes first either way.
                if disposition == 'apply-union':
                    disposition = 'manual'
                members[0]['problems'].append(str(e))
            if union_patch and not args.union_dir:
                problems.append('--union-dir is required for union artefacts')
        counts[disposition] += 1
        print(disposition + ' ' + name + ' · lanes ' + ' '.join(dict.fromkeys(c['lane'] for c in live)) + f' · objects {len(live)}')
        for c in all_members:
            print('  claim ' + c['_id'] + (' · quarantined' if c['_id'] in dropped else ' · retained'))
        if any(x['lift'] for x in members):
            next_class = 'apply-union' if union_patch else ('conflict' if multi else 'apply')
            print('  confidence lift: read the page in full · then ' + (next_class if disposition == 'tier-raised' else disposition))
        for why in dict.fromkeys(p for member in members for p in member['problems']): print('  reason: ' + why)
        if not paths:
            aliases = [a for member in members if member['changed'] for a in frontmatter(member['changed']).get('aliases', [])]
            print('  create names and aliases: ' + json.dumps([c['name'] for c in live] + [a for c in live for a in c.get('aliases', [])] + aliases, ensure_ascii=False))
        if disposition in ('apply', 'apply-union') or (disposition == 'tier-raised' and union_patch):
            applications.append((target, union_patch, members, disposition == 'tier-raised'))
    print('summary: targets ' + str(len(groups)) + ' · ' + ' · '.join(f'{k} {v}' for k, v in counts.items()) + f' · claims {len(claims)} · quarantined objects {len(dropped)}')
    print('controls: normalisation matched and separated · apply and conflict classified · duplicate quarantine rejected · quoted confidence parsed')
    if problems:
        raise ProbeError('; '.join(dict.fromkeys(problems)))
    ready = []
    for target, union_patch, members, after_read in applications:
        diff = emit_union(args.union_dir, target, union_patch, vault) if union_patch else Path(members[0]['diff']).resolve()
        union_hash = digest(union_patch.encode('utf-8')) if union_patch else None
        if union_patch: print('union diff: ' + str(diff) + ' · base ' + digest(members[0]['text'].encode('utf-8')) + ' · diff_hash ' + union_hash + (' · after the full-page read' if after_read else ''))
        ready.append((target, diff, members[0]['expected_base'], after_read, union_hash))
    # Validate every queued target before printing any patch command. The head
    # still compares this same expected hash immediately before the real apply.
    for target, diff, expected, _, union_hash in ready:
        drift = base_problem(target, expected)
        if drift: raise ProbeError(str(target) + ': ' + drift)
        if union_hash is not None and digest(diff.read_bytes()) != union_hash:
            raise ProbeError('union diff hash changed during planning: ' + str(diff))
    for target, diff, expected, after_read, union_hash in ready:
        if after_read:
            # No apply command for a held target: the head reads the page in full, then runs
            # --resolved on the union artefact, which prints the commands (CR-PLANNER MEDIUM 2).
            print(read_release(vault, target, diff, expected, union_hash, 'union'))
            continue
        print('base recheck immediately before real patch: ' + (expected if expected is not None else 'target absent'))
        print(patch_command(vault, target, diff, diff.parent / 'apply.rej'))
        print('after dry-run and base recheck: ' + patch_command(vault, target, diff, diff.parent / 'apply.rej', False))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vault', default=str(Path(__file__).resolve().parents[3]))
    ap.add_argument('--union-dir', help='existing head-named scratch directory outside the vault; the sole write exception')
    ap.add_argument('--after-read', action='append', default=[], help='acknowledge the full-page read using the held BASE:DIFF_HASH pair; one per --resolved')
    for name in ('ledger', 'lanes', 'quarantine', 'allow-malformed', 'resolved'):
        ap.add_argument('--' + name, action='append', default=[])
    args = ap.parse_args(argv)
    if PARSER_ERROR is not None:
        print('PROBE FAILED: markdown-it-py not importable (' + str(PARSER_ERROR) + ')')
        return 2
    try:
        planted()
        return plan(args)
    except (OSError, ValueError, TypeError, KeyError) as e:
        print('PROBE FAILED: ' + str(e))
        return 2


if __name__ == '__main__':
    sys.exit(main())
