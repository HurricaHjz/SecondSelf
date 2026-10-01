#!/usr/bin/env python3
"""Print an anchored merge plan; no patch or ledger writes.

Usage: merge_plan.py --vault DIR --ledger FILE [--ledger CLAIMS_FILE ...]
       [--lanes LA,LB] [--quarantine JSON_LIST] [--allow-malformed FILE:LINE ...]
       [--union-dir EXISTING_SCRATCH_DIRECTORY]
       merge_plan.py --vault DIR --resolved DIFF

Claims carry name, type, kind, target, facts, source/from, diff, base and diff_hash.
Hashes are sha256 prefixes of 16 hex digits (or the complete sha256 for diff_hash).
The first ledger binds the run; separate files need that run explicitly or their
own matching run_open. Runless events inherit only their own file's run_open.
File order proves sequence within a ledger; strict timestamps prove it across
files. Every expected lane's latest opening and latest close must precede its
verification. A later close invalidates earlier verification until another verify.
All nine score names are required, with distinct quarantine references per object.
--allow-malformed settles only the real FILE and LINE explicitly named by the head.
The expected base hash stays tied to the bytes used to validate the diff; drift
during planning is manual or an error, never a replacement expected hash.
Exit 0 prints the plan; exit 2 prints PROBE FAILED and suppresses apply commands.
Classes: quarantined objects are removed first; conflict > manual > tier-raised
> apply-union > apply. Only link additions under Appears in or Related can union;
whole lines are de-duplicated after whitespace collapse only: punctuation, case
and target/gloss boundaries are preserved, so different glosses survive. Prose under
different headings still conflicts. --union-dir is the sole write exception: one
new diff per union target in the head's existing scratch directory outside the
vault, never an overwrite of different bytes. Missing union scratch exits 2.
A confidence lift always names the required full-page read, including a
lift introduced by a resolved diff. The head applies with patch at zero fuzz.
"""
import argparse
import difflib
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import unicodedata

sys.dont_write_bytecode = True
HASH_LENGTH = 16  # The prefix length used by source_hash and the de-dup probe.
TIERS = {tier: rank for rank, tier in enumerate(('very-low', 'low', 'medium', 'high', 'authoritative'))}  # Confidence ordinal; compiled pages cap at high.
SCORES = ('fab', 'plant', 'cov', 'tier', 'struct', 'integ', 'lang', 'anom', 'claims')
DIRS = {'entity': 'entities', 'tool': 'tools', 'concept': 'concepts', 'model': 'models', 'benchmark': 'benchmarks', 'source': 'sources'}
LINK = re.compile(r'\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]')
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)$')


class ProbeError(ValueError):
    pass


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


def frontmatter(text):
    lines = text.splitlines()
    result = {}
    if not lines or lines[0].strip() != '---':
        return result
    closed = False
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            closed = True; break
        m = re.match(r'([\w-]+):\s*(.*)$', line)
        if not m:
            continue
        key, value = m[1], m[2]
        if key == 'aliases':
            if value.strip().startswith('['):
                inner = value.strip()[1:].rsplit(']', 1)[0]
                result[key] = [scalar(x.strip()) for x in re.findall(r'''"[^"]*"|'[^']*'|[^,]+''', inner)]
            elif value.strip():
                result[key] = [scalar(value)]
            else:
                result[key] = []
                for follow in lines[i + 1:]:
                    item = re.match(r'\s*-\s+(.*)$', follow)
                    if not item: break
                    result[key].append(scalar(item[1]))
        else:
            result[key] = scalar(value)
    if not closed:
        raise ProbeError('frontmatter does not close')
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
    if not match or match[1] not in (None, lane): raise ProbeError('verify needs all nine score names for ' + lane)
    values = dict(zip(SCORES, match.groups()[1:]))
    if any(v == '-' for k, v in values.items() if k not in ('plant', 'claims')):
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
            if values['claims'] is None or values['plant'] is None:
                quarantined.update(c['_id'] for c in member)
                raise ProbeError('unscored plant or claims: ' + lane)
            if values['claims'] != len(dropped): raise ProbeError('claims count differs from distinct quarantine objects: ' + lane)
            quarantined.update(dropped)
            if values['plant']:
                quarantined.update(c['_id'] for c in member)
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
        if c.get('kind') == 'create' and (not newmeta or not re.search(r'^## Related\s*$', changed, re.M)):
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
        candidates = [link_additions(x) for x in members]
        if any(c is None for c in candidates): return 'conflict'
        if any(x['problems'] for x in members): return 'manual'
        # Confidence edits accompanying otherwise link-only changes require the
        # full-page read first. No union artefact ever changes confidence.
        if any(x['lift'] for x in members): return 'tier-raised'
        if any(c[1] for c in candidates): return 'conflict'
        return 'apply-union'
    if any(x['problems'] for x in members): return 'manual'
    paths = {str(x['diff']) for x in members}
    if len(paths) != 1: return 'manual'
    return 'tier-raised' if any(x['lift'] for x in members) else 'apply'


def link_additions(member):
    """Return (section/link additions, confidence edit), or None for a non-union.

    The old hunk position identifies its heading in the current page, whose exact
    base and context inspect_claim checks. Offsets never establish disjointness.
    """
    parsed = member.get('parsed')
    if parsed is None or parsed['old'] is None:
        return None
    source = member['text'].splitlines(keepends=True)
    additions, confidence_edit = [], False
    for offset, _, _, _, body in parsed['hunks']:
        position = offset
        heading = ''
        for prior in source[:position]:
            if prior.startswith('#'): heading = prior.strip()
        for line in body:
            tag, content = line[0], line[1:]
            if tag == ' ':
                if content.startswith('#'): heading = content.strip()
                position += 1; continue
            if re.match(r'^confidence:\s*', content):
                confidence_edit = True
                position += tag == '-'
                continue
            if tag == '-': return None
            if not re.fullmatch(r'- \[\[[^\]\n]+\]\](?:[^\n]*)\n?', content):
                return None
            if heading not in ('## Appears in', '## Related'):
                return None
            additions.append((heading, content))
    return (additions, confidence_edit) if additions else None


def normalise_link_line(line):
    """Collapse whitespace only; names, punctuation, case and glosses stay distinct."""
    return ' '.join(line.split())


def compose_union(members):
    """Compose one diff against the current page. Repeated section headings fail closed."""
    original = members[0]['text']
    lines = original.splitlines(keepends=True)
    additions = {}
    for member in members:
        if member['text'] != original or member['problems']:
            raise ProbeError('union re-base failed: member base or context differs')
        candidate = link_additions(member)
        if candidate is None or candidate[1]:
            raise ProbeError('union contains a prose or confidence edit')
        for heading, line in candidate[0]:
            additions.setdefault(heading, []).append(line)
    inserts = []
    for heading, links in additions.items():
        starts = [i for i, line in enumerate(lines) if line.strip() == heading]
        if len(starts) != 1:
            raise ProbeError('union re-base failed: link heading missing or repeated')
        start = starts[0]
        end = next((i for i in range(start + 1, len(lines)) if re.match(r'^#{1,2}\s', lines[i])), len(lines))
        seen = {normalise_link_line(line) for line in lines[start + 1:end] if line.startswith('- ')}
        kept = []
        for line in links:
            key = normalise_link_line(line)
            if key not in seen:
                seen.add(key); kept.append(line if line.endswith('\n') else line + '\n')
        at = end
        while at > start + 1 and not lines[at - 1].strip(): at -= 1
        inserts.append((at, kept))
    for at, kept in sorted(inserts, reverse=True): lines[at:at] = kept
    changed = ''.join(lines)
    target = members[0]['target']
    patch = ''.join(difflib.unified_diff(original.splitlines(keepends=True), changed.splitlines(keepends=True), fromfile=str(target), tofile=str(target)))
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


def planted():
    if normalise('A B-c!') != normalise('abc') or normalise('abc') == normalise('abd'):
        raise ProbeError('canonicalisation control failed')
    a = {'claim': {'lane': 'A'}, 'problems': [], 'lift': False, 'diff': 'd'}
    b = dict(a, claim={'lane': 'B'}, lift=True)
    if classify([a]) != 'apply' or classify([a, b]) != 'conflict': raise ProbeError('classification controls failed')
    if scalar('"high"') != 'high' or scalar("'medium'") != 'medium': raise ProbeError('quoted confidence controls failed')
    if normalise_link_line('effect > 0') == normalise_link_line('effect < 0') or normalise_link_line('effect  > 0 \t') != normalise_link_line('effect > 0'):
        raise ProbeError('link whitespace controls failed')
    c = {'_id': 'one', 'name': 'M'}
    if reference_ids([{'name':'M'}], [c]) != {'one'}: raise ProbeError('quarantine control failed')
    try: reference_ids([{'name':'M'}, {'name':'M'}], [c])
    except ProbeError: pass
    else: raise ProbeError('duplicate quarantine control failed')


def plan(args):
    vault = Path(args.vault).expanduser().resolve()
    if not (vault / 'wiki').is_dir(): raise ProbeError('vault has no wiki directory')
    if args.resolved:
        for path in args.resolved:
            parsed = parse_diff(Path(path).read_text(encoding='utf-8'), vault)
            old = parsed['new'].read_text(encoding='utf-8') if parsed['old'] else ''
            new = apply_memory(old, parsed)
            lift = bool(parsed['old']) and TIERS.get(frontmatter(new).get('confidence'), -1) > TIERS.get(frontmatter(old).get('confidence'), -1)
            print(('confidence lift: read the page in full before applying · ' if lift else 'no confidence lift: read the diff, then apply · ') + str(parsed['new']))
        print('controls: quoted high parsed · non-raising medium parsed · valid apply and conflict classified')
        return 0
    if not args.ledger: raise ProbeError('plan needs at least one --ledger')
    if args.union_dir:
        scratch = Path(args.union_dir).expanduser().resolve()
        if not scratch.is_dir() or scratch.is_relative_to(vault):
            raise ProbeError('--union-dir must be an existing scratch directory outside the vault')
    events, problems = read_events(args.ledger, args.allow_malformed)
    claims = claims_from(events)
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
        if c.get('kind') == 'create' and isinstance(c.get('diff'), str):
            try:
                path = Path(c['diff']).expanduser()
                if not path.is_absolute(): path = Path(c['_event']['_file']).parent / path
                parsed = parse_diff(path.read_text(encoding='utf-8'), vault)
                if parsed['old'] is None:
                    for alias in frontmatter(apply_memory('', parsed)).get('aliases', []): cat.join(key, normalise(alias))
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
        disposition = classify(members)
        union_patch = None
        if disposition == 'apply-union':
            try:
                union_patch = compose_union(members)
            except ProbeError as e:
                disposition = 'manual'
                members[0]['problems'].append(str(e))
            if union_patch and not args.union_dir:
                problems.append('--union-dir is required for union artefacts')
        counts[disposition] += 1
        print(disposition + ' ' + name + ' · lanes ' + ' '.join(dict.fromkeys(c['lane'] for c in live)) + f' · objects {len(live)}')
        for c in all_members:
            print('  claim ' + c['_id'] + (' · quarantined' if c['_id'] in dropped else ' · retained'))
        if any(x['lift'] for x in members):
            next_class = 'conflict' if len({c['lane'] for c in live}) > 1 else 'apply'
            print('  confidence lift: read the page in full · then ' + (next_class if disposition == 'tier-raised' else disposition))
        for why in dict.fromkeys(p for member in members for p in member['problems']): print('  reason: ' + why)
        if not paths:
            aliases = [a for member in members if member['changed'] for a in frontmatter(member['changed']).get('aliases', [])]
            print('  create names and aliases: ' + json.dumps([c['name'] for c in live] + [a for c in live for a in c.get('aliases', [])] + aliases, ensure_ascii=False))
        if disposition in ('apply', 'apply-union'):
            applications.append((target, union_patch, members))
    print('summary: targets ' + str(len(groups)) + ' · ' + ' · '.join(f'{k} {v}' for k, v in counts.items()) + f' · claims {len(claims)} · quarantined objects {len(dropped)}')
    print('controls: normalisation matched and separated · apply and conflict classified · duplicate quarantine rejected · quoted confidence parsed')
    if problems:
        raise ProbeError('; '.join(dict.fromkeys(problems)))
    ready = []
    for target, union_patch, members in applications:
        diff = emit_union(args.union_dir, target, union_patch, vault) if union_patch else Path(members[0]['diff']).resolve()
        if union_patch: print('union diff: ' + str(diff) + ' · base ' + digest(members[0]['text'].encode('utf-8')) + ' · diff_hash ' + digest(union_patch.encode('utf-8')))
        ready.append((target, diff, members[0]['expected_base']))
    # Validate every queued target before printing any patch command. The head
    # still compares this same expected hash immediately before the real apply.
    for target, _, expected in ready:
        drift = base_problem(target, expected)
        if drift: raise ProbeError(str(target) + ': ' + drift)
    for target, diff, expected in ready:
        print('base recheck immediately before real patch: ' + (expected if expected is not None else 'target absent'))
        print(patch_command(vault, target, diff, diff.parent / 'apply.rej'))
        print('after dry-run and base recheck: ' + patch_command(vault, target, diff, diff.parent / 'apply.rej', False))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vault', default=str(Path(__file__).resolve().parents[3]))
    ap.add_argument('--union-dir', help='existing head-named scratch directory outside the vault; the sole write exception')
    for name in ('ledger', 'lanes', 'quarantine', 'allow-malformed', 'resolved'):
        ap.add_argument('--' + name, action='append', default=[])
    args = ap.parse_args(argv)
    try:
        planted()
        return plan(args)
    except (OSError, ValueError, TypeError, KeyError) as e:
        print('PROBE FAILED: ' + str(e))
        return 2


if __name__ == '__main__':
    sys.exit(main())
