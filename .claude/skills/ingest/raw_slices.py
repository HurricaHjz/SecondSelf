#!/usr/bin/env python3
"""Print structural raw passages and claim locator passages; never write files.

Usage: raw_slices.py --raw FILE --page FILE --lane ID --ledger JSONL [--ledger JSONL ...]
       raw_slices.py --trace OUTPUT --item /absolute/raw.md:FIRST[-LAST] [--item ...]
The head persists stdout. The skeleton is independent of claims. Missing claims,
ambiguous source attribution, partial claims, conversion flags, hash drift or absent
structure take the whole-read fallback. Empty claim objects exit 2; partial claims
count as unresolved. Conversion aliases collapse to one identity per source before
ambiguity is checked. Every fabrication candidate still requires a whole read.
Trace requires complete outputs, full source identities and every numbered line;
an uncovered shadow item is LOSS (exit 1), a covered item VARIANCE (exit 0).
Broken input or incomplete evidence prints PROBE FAILED and exits 2. No network.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HASH_LENGTH = 16  # The source_hash prefix consumed by the existing de-dup probe.
LINK = re.compile(r'\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]')
FLOAT = re.compile(r'^(?:#{1,6}\s*)?[*_ ]*(table|fig(?:ure)?\.?)\s*(\d+[a-z]?)\b', re.I)
REFERENCES = re.compile(r'\b(tables?|fig(?:ures?)?\.?|sections?|§)\s+(\d+(?:\.\d+)*[a-z]?(?:\s*(?:,|and|&)\s*\d+(?:\.\d+)*[a-z]?)*)(?!\w)', re.I)
SKELETON = {'abstract', 'introduction', 'conclusion', 'conclusions', 'discussion', 'limitations'}
PLAIN = SKELETON | {'aim', 'data', 'methods', 'method', 'methodology', 'results', 'references', 'appendix'}


class ProbeError(ValueError):
    pass


def read(path):
    return Path(path).read_text(encoding='utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()[:HASH_LENGTH]


def metadata(text):
    lines = text.splitlines()
    meta = {}
    if lines and lines[0].strip() == '---':
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                return meta, '\n'.join(lines[i + 1:])
            m = re.match(r'([\w-]+):\s*(.*)', line)
            if m:
                meta[m[1]] = m[2].split(' #', 1)[0].strip().strip('\'"')
        raise ProbeError('source page frontmatter does not close')
    return meta, text


def title_key(text):
    return re.sub(r'^\d+(?:\.\d+)*[.)]?\s+', '', text).strip().strip('*_').casefold()


class Raw:
    def __init__(self, text):
        self.lines = text.splitlines(keepends=True)
        self.headings = []
        self.underlines = set()
        fenced = False
        for i, line in enumerate(self.lines):
            s = line.strip()
            if s.startswith(('```', '~~~')):
                fenced = not fenced
                continue
            if fenced:
                continue
            h = re.match(r'^(#{1,6})\s+(.+?)\s*#*$', s)
            if h:
                self.headings.append((i, len(h[1]), h[2]))
            elif s and i + 1 < len(self.lines) and re.fullmatch(r'(?:={2,}|-{2,})', self.lines[i + 1].strip()):
                self.headings.append((i, 1 if self.lines[i + 1].lstrip().startswith('=') else 2, s))
                self.underlines.add(i + 1)
            elif title_key(s) in PLAIN and (i == 0 or not self.lines[i - 1].strip()):
                self.headings.append((i, 2, s.strip('*_')))
            elif re.fullmatch(r'\d+(?:\.\d+)*\s+[A-Z][^.!?]+', s) and (i == 0 or not self.lines[i - 1].strip()):
                self.headings.append((i, 2, s))
        self.heading_lines = {h[0] for h in self.headings} | self.underlines
        self.captions = [(i, m[1].lower(), m[2].lower()) for i, s in enumerate(self.lines) if (m := FLOAT.match(s))]

    def section(self, h):
        start, level, _ = h
        stop = next((i for i, lev, _ in self.headings if i > start and lev <= level), len(self.lines))
        return set(range(start, stop))

    def paragraph(self, i):
        lo = hi = i
        while lo > 0 and self.lines[lo - 1].strip() and lo - 1 not in self.heading_lines:
            lo -= 1
        while hi + 1 < len(self.lines) and self.lines[hi + 1].strip() and hi + 1 not in self.heading_lines:
            hi += 1
        return set(range(lo, hi + 1))

    def float_range(self, i, kind):
        """Caption and neighbouring converted blocks, including plain rows above it.

        Blank lines do not bound a table. The adjacent non-heading paragraphs are
        deliberately retained even where conversion has lost the table syntax.
        """
        found = self.paragraph(i)
        for step, edge in [(-1, min(found)), (1, max(found))]:
            j = edge + step
            while 0 <= j < len(self.lines) and not self.lines[j].strip():
                j += step
            if 0 <= j < len(self.lines) and j not in self.heading_lines:
                if kind.startswith('table') or '|' in self.lines[j] or self.lines[j].lstrip().startswith('!['):
                    found |= self.paragraph(j)
        return found

    def skeleton(self):
        second = self.headings[1][0] if len(self.headings) > 1 else len(self.lines)
        found = set(range(second)) | self.heading_lines
        for h in self.headings:
            if title_key(h[2]) in SKELETON:
                found |= self.section(h)
        for i, kind, _ in self.captions:
            found |= self.float_range(i, kind)
        return found

    def resolve(self, locator):
        """Quotation, section, then float ladder. Return lines and unresolved references."""
        locator = str(locator).strip()
        if not locator:
            return set(), ['empty locator']
        quotes = re.findall(r'["“](.+?)["”]|‘(.+?)’', locator)
        candidates = [a or b for a, b in quotes]
        if not candidates and not REFERENCES.search(locator) and not any(title_key(h[2]) == locator.casefold() for h in self.headings):
            candidates = [locator]
        for quote in candidates:
            if quote and quote in ''.join(self.lines):
                offset = ''.join(self.lines).index(quote)
                first = ''.join(self.lines)[:offset].count('\n')
                last = first + quote.count('\n')
                return set().union(*(self.paragraph(i) for i in range(first, last + 1))), []
        found, missing = set(), []
        refs = list(REFERENCES.finditer(locator))
        for ref in refs:
            kind = ref[1].lower()
            numbers = re.findall(r'\d+(?:\.\d+)*[a-z]?', ref[2], re.I)
            for number in numbers:
                if kind.startswith('section') or kind == '§':
                    hits = [h for h in self.headings if re.match(r'^' + re.escape(number) + r'(?:[.)]?\s|$)', h[2], re.I)]
                    block = set().union(*(self.section(h) for h in hits)) if hits else set()
                else:
                    hits = [(i, k) for i, k, n in self.captions if n == number.lower() and k.startswith('table' if kind.startswith('table') else 'fig')]
                    block = set().union(*(self.float_range(i, k) for i, k in hits)) if hits else set()
                found |= block
                if not block:
                    missing.append(kind + ' ' + number)
        for h in self.headings:
            name = title_key(h[2])
            if name and re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', locator.casefold()):
                found |= self.section(h)
        return found, missing or ([] if found else [locator])


def source_identity(value):
    """One identity for an original and its conversion, retaining every directory."""
    value = os.path.normpath(os.path.expanduser(str(value)))
    if Path(value).suffix.lower() in {'.pdf', '.docx', '.html', '.htm'}:
        value = str(Path(value).with_suffix('.md'))
    return os.path.realpath(value) if os.path.isabs(value) else value


def path_matches(name, target):
    """A source identity may be absolute or a path suffix; conversions change suffix only."""
    name, target = source_identity(name), source_identity(target)
    if os.path.isabs(name):
        return name == target
    return target == name or target.endswith(os.sep + name)


def source_answer(name, target, known):
    if not path_matches(name, target):
        return False
    identities = {source_identity(k) for k in known if path_matches(name, k)}
    # A shorter spelling of the same identity is not another raw. Incomparable
    # matching suffixes are ambiguous, at every path depth, not only basenames.
    fullest = {k for k in identities if not any(k != q and path_matches(k, q) for q in identities)}
    return len(fullest) == 1 and all(path_matches(k, target) or path_matches(target, k) for k in fullest)


def claim_problems(claim, source, origin):
    """Partial objects cannot supply locator evidence; an empty object is invalid."""
    if not claim:
        raise ProbeError('empty claim object')
    problems = []
    if not isinstance(claim.get('name'), str) or not claim['name'].strip():
        problems.append('missing claim name')
    if not any(isinstance(value, str) and value.strip() for value in (source, origin)):
        problems.append('missing source identity')
    facts = claim.get('facts', [])
    if not isinstance(facts, list):
        raise ProbeError('facts must be a list')
    if not facts:
        problems.append('missing fact locator')
    for i, fact in enumerate(facts, 1):
        locator = fact.get('locator') if isinstance(fact, dict) else None
        if not isinstance(locator, str) or not locator.strip():
            problems.append(f'missing locator for fact {i}')
    return problems


def own_page(value, page):
    targets = LINK.findall(str(value))
    if not targets:
        targets = [str(value).strip()]
    return any(path_matches(t if t.endswith('.md') else t + '.md', str(page)) for t in targets)


def lane_claims(events, lane, raw, page, source=None):
    known = [str(e['source']) for e in events if e.get('source')]
    for e in events:
        if e.get('event') == 'run_open':
            known += [str(x['file']) for x in e.get('inbox', []) if isinstance(x, dict) and x.get('file')]
    known.append(str(raw))
    out = []
    for e in events:
        if e.get('event') != 'checkpoint' or e.get('stage') != 'claims_emitted' or e.get('lane') != lane:
            continue
        claims = e.get('claims')
        if not isinstance(claims, list) or any(not isinstance(c, dict) for c in claims):
            raise ProbeError('claims must be a list of objects')
        for c in claims:
            src, origin = c.get('source', e.get('source')), c.get('from', e.get('from'))
            problems = claim_problems(c, src, origin)
            if not (isinstance(src, str) and src.strip()):
                src = None
            if not (isinstance(origin, str) and origin.strip()):
                origin = None
            if origin and not own_page(origin, page):
                continue
            if src:
                if not path_matches(src, raw) and not (source and path_matches(src, source)):
                    continue
                if not source_answer(src, raw, known) and (not origin or os.path.dirname(str(src)) not in ('', '.')):
                    continue
            elif not origin and not problems:
                continue
            out.append(dict(c, _problems=problems))
    return out


def read_events(paths):
    events, malformed = [], []
    for path in paths:
        text = read(path)
        if not text.strip():
            raise ProbeError('empty ledger: ' + str(path))
        for i, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError('event is not an object')
                events.append(event)
            except ValueError:
                malformed.append(f'{Path(path).resolve()}:{i}')
    if not events:
        raise ProbeError('ledger holds no events')
    runs = {e.get('run') for e in events if e.get('run')}
    if len(runs) > 1:
        raise ProbeError('events name different runs')
    return events, malformed


def ranges(numbers):
    result = []
    for i in sorted(numbers):
        if result and i == result[-1][1] + 1:
            result[-1][1] = i
        else:
            result.append([i, i])
    return result


def planted():
    raw = Raw('# Title\n\n## Aim\nA known phrase.\n\n## Data\nRow A 12\nRow B 23\n\nTable 1: data\n\n## End\nEnd.\n')
    if raw.resolve('"A known phrase."')[1] or not raw.resolve('Table 9')[1]:
        raise ProbeError('locator controls failed')
    if not {6, 7} <= raw.resolve('Table 1')[0] or not raw.resolve('Aim')[0]:
        raise ProbeError('structure controls failed')
    if not raw.resolve(raw.headings[0][2])[0]:
        raise ProbeError('first heading control failed')
    one, other = '/slices-control/one/paper.md', '/slices-control/other/one/paper.md'
    pair = [one, str(Path(one).with_suffix('.pdf'))]
    competing = pair + [other, str(Path(other).with_suffix('.pdf'))]
    if not source_answer('one/paper.md', one, pair) or source_answer('one/paper.md', one, competing):
        raise ProbeError('conversion identity controls failed')


def slices(args):
    if not all((args.raw, args.page, args.lane, args.ledger)):
        raise ProbeError('slicing needs --raw, --page, --lane and --ledger')
    raw_path, page_path = Path(args.raw).resolve(), Path(args.page).resolve()
    data = raw_path.read_bytes()
    if not data.strip():
        raise ProbeError('empty raw')
    raw = Raw(data.decode('utf-8'))
    page_text = read(page_path)
    if not page_text.strip():
        raise ProbeError('empty source page')
    meta, body = metadata(page_text)
    events, malformed = read_events(args.ledger)
    claims = lane_claims(events, args.lane, raw_path, page_path, args.source)
    reason = ''
    if not claims:
        reason = 'no ledger claims'
    elif any(c['_problems'] for c in claims):
        reason = 'partial claim'
    elif len(raw.headings) < 2:
        reason = 'no heading below title'
    if re.search(r'convert|conversion|truncat|ocr|suspect', meta.get('flagged', ''), re.I):
        reason = 'conversion suspect'
    if meta.get('source_hash') and meta['source_hash'] != digest(data):
        reason = 'source_hash mismatch'
    if malformed:
        reason = 'malformed ledger'
    print(f'raw slices · lane {args.lane} · raw {raw_path} · page {page_path} · claims {len(claims)}')
    print('identity: ' + json.dumps({'raw': str(raw_path), 'lines': len(raw.lines), 'sha256': digest(data)}, ensure_ascii=False))
    skeleton, selected, unresolved = raw.skeleton(), set(), []
    for i, c in enumerate(claims):
        if c['_problems']:
            unresolved.append(f'claim {i + 1} {c.get("name", "unnamed")}: ' + ', '.join(c['_problems']))
            continue
        facts = c.get('facts', [])
        if not isinstance(facts, list):
            raise ProbeError('facts must be a list')
        for fact in facts:
            locator = fact.get('locator', '') if isinstance(fact, dict) else str(fact)
            lines, missing = raw.resolve(locator)
            selected |= lines
            if missing:
                unresolved.append(f'claim {i + 1} {c.get("name", "unnamed")} {locator}: ' + ', '.join(missing))
    for ref in REFERENCES.finditer(body):
        lines, missing = raw.resolve(ref[0])
        selected |= lines
        if missing:
            unresolved.append('page ' + ref[0] + ': ' + ', '.join(missing))
    if reason:
        print('full: ' + reason)
    else:
        for label, indices in [('skeleton', skeleton), ('locator', selected - skeleton)]:
            print('## ' + label.capitalize())
            for lo, hi in ranges(indices):
                print(f'=== L{lo + 1}-L{hi + 1} · {label}')
                for i in range(lo, hi + 1):
                    print(f'{i + 1}: {raw.lines[i].rstrip(chr(10)).rstrip(chr(13))}')
    for item in unresolved:
        print('UNRESOLVED ' + item)
    for item in malformed:
        print('MALFORMED ' + item)
    size = lambda indices: sum(len(raw.lines[i].encode('utf-8')) for i in indices)
    print(f'raw: sha256 {digest(data)} · {len(data)} bytes · page source_hash {meta.get("source_hash", "absent")}')
    print(f'bytes: skeleton {size(skeleton)} · slices {size(selected - skeleton)} · passages {len(data) if reason else size(skeleton | selected)} of {len(data)}')
    print(f'summary: claims {len(claims)} · unresolved {len(unresolved)} · full {"yes" if reason else "no"}')
    print('controls: quotation found · absent table unresolved · first heading resolved · rows above caption retained · conversion pairs kept distinct')
    if malformed:
        raise ProbeError('malformed ledger: whole read required; settle the evidence before verification')
    return 0


def parse_outputs(text):
    """Parse complete framed outputs. A claimed interval alone never proves coverage."""
    records, current, pending = [], None, None
    for line in text.splitlines():
        if pending:
            expected, last = pending
            m = re.match(r'(\d+): (.*)$', line)
            if not m or int(m[1]) != expected:
                raise ProbeError(f'incomplete numbered passage: expected line {expected}')
            if expected in current['covered']:
                raise ProbeError('duplicate numbered raw line')
            current['covered'].add(expected)
            pending = (expected + 1, last) if expected < last else None
            continue
        if line.startswith('raw slices · '):
            if current is not None and not current['closed']:
                raise ProbeError('output missing closing controls line')
            current = {'covered': set(), 'closed': False, 'full': False, 'footer': False, 'summary': False, 'bytes': False}
            records.append(current)
        elif current is None:
            if line.strip():
                raise ProbeError('text outside a raw output')
        elif current['closed']:
            if line.strip():
                raise ProbeError('trailing text after controls')
        elif line.startswith('identity: '):
            if 'identity' in current:
                raise ProbeError('duplicate output identity')
            value = json.loads(line[len('identity: '):])
            if not isinstance(value, dict) or not isinstance(value.get('raw'), str) or not os.path.isabs(value['raw']) or type(value.get('lines')) is not int or value['lines'] < 1 or not re.fullmatch(r'[0-9a-f]{16}', value.get('sha256', '')):
                raise ProbeError('invalid output identity')
            current['identity'] = value
        elif m := re.fullmatch(r'=== L(\d+)-L(\d+) · (skeleton|locator)', line):
            lo, hi = int(m[1]), int(m[2])
            if current['footer'] or current['full'] or 'identity' not in current or not 1 <= lo <= hi <= current['identity']['lines']:
                raise ProbeError('invalid passage bounds or order')
            pending = lo, hi
        elif line.startswith('full: '):
            if current['covered'] or not line[6:].strip():
                raise ProbeError('invalid whole-read fallback')
            current['full'] = True
        elif line.startswith('raw: sha256 '):
            current['footer'] = True
        elif line.startswith('bytes: '):
            current['bytes'] = True
        elif line.startswith('summary: '):
            current['summary'] = True
        elif line.startswith('controls: '):
            if not all((current.get('identity'), current['footer'], current['bytes'], current['summary'])) or not (current['full'] or current['covered']):
                raise ProbeError('output has no complete footer or passages')
            current['closed'] = True
        elif not (line.startswith(('## ', 'UNRESOLVED ')) or not line.strip()):
            raise ProbeError('unexpected line in raw output')
    if pending or not records or not all(r['closed'] for r in records):
        raise ProbeError('incomplete output or missing controls line')
    paths = [r['identity']['raw'] for r in records]
    if len(paths) != len(set(paths)):
        raise ProbeError('duplicate raw output identity')
    return records


def classify_item(records, path, first, last):
    hits = [r for r in records if path_matches(path, r['identity']['raw'])]
    if len(hits) != 1:
        raise ProbeError('trace source absent or ambiguous: ' + path)
    r = hits[0]
    if not 1 <= first <= last <= r['identity']['lines']:
        raise ProbeError('trace item outside raw line bounds')
    return 'VARIANCE' if r['full'] or set(range(first, last + 1)) <= r['covered'] else 'LOSS'


def trace(path, items):
    if not items:
        raise ProbeError('trace needs at least one --item')
    records = parse_outputs(read(path))
    control = [{'identity': {'raw': '/control/one/paper.md', 'lines': 9}, 'covered': {1, 2}, 'full': False},
               {'identity': {'raw': '/control/two/paper.md', 'lines': 9}, 'covered': set(), 'full': True}]
    if classify_item(control, '/control/one/paper.md', 3, 3) != 'LOSS' or classify_item(control, '/control/one/paper.md', 1, 2) != 'VARIANCE':
        raise ProbeError('trace controls failed')
    loss = 0
    for item in items:
        m = re.fullmatch(r'(.+):(\d+)(?:-(\d+))?', item)
        if not m:
            raise ProbeError('item wants RAW:FIRST[-LAST]')
        result = classify_item(records, m[1], int(m[2]), int(m[3] or m[2]))
        loss += result == 'LOSS'
        print(result + ' ' + item)
    print(f'summary: items {len(items)} · loss {loss} · variance {len(items) - loss}')
    print('controls: outside LOSS · inside VARIANCE · same basename retains full identity')
    return 1 if loss else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('raw', 'page', 'lane', 'source', 'trace'):
        ap.add_argument('--' + name)
    ap.add_argument('--ledger', action='append', default=[])
    ap.add_argument('--item', action='append', default=[])
    args = ap.parse_args(argv)
    try:
        planted()
        return trace(args.trace, args.item) if args.trace else slices(args)
    except (OSError, ValueError, TypeError, KeyError) as e:
        print('PROBE FAILED: ' + str(e))
        return 2


if __name__ == '__main__':
    sys.exit(main())
