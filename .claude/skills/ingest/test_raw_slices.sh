#!/bin/sh
# Standard-library fixtures; every file is below mktemp and removed on exit.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TMP_CASE=$(mktemp -d "${TMPDIR:-/tmp}/raw-slices-suite.XXXXXX")
trap 'chmod -R u+w "$TMP_CASE"; rm -rf "$TMP_CASE"' EXIT HUP INT TERM
python3 -B - "$HERE" "$TMP_CASE" "${1:-$HERE/raw_slices.py}" <<'PY_RAW_SUITE'
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

here, root, script = map(Path, sys.argv[1:])
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('slicer', script)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
passed = failed = 0

def check(leg, condition, detail=''):
    global passed, failed
    if condition:
        passed += 1; print('ok ' + leg + (' · ' + detail if detail else ''))
    else:
        failed += 1; print('FAIL ' + leg + (' · ' + detail if detail else ''))

raw = root / 'one' / 'paper.md'; raw.parent.mkdir()
raw.write_text('# Title\n\n## Introduction\nOpening.\n\n## Methods\nKept quotation.\n\n## Results\n\nOutside fact.\n\n## Conclusion\nEnd.\nFinal.\n')
page = root / 'page.md'; page.write_text('---\nsource_hash: ' + m.digest(raw.read_bytes()) + '\n---\n# Source\n')
ledger = root / 'ledger.jsonl'
claim = {'name':'Model', 'source':str(raw), 'from':'[' * 2 + 'page' + ']' * 2, 'facts':[{'fact':'Kept', 'locator':'"Kept quotation."'}]}
events = [{'event':'run_open','run':'fixture','inbox':[{'file':str(raw)}]}, {'event':'checkpoint','stage':'claims_emitted','run':'fixture','lane':'LA','source':str(raw),'claims':[claim]}]

def save(rows):
    ledger.write_text(''.join(json.dumps(e) + '\n' for e in rows))

def run(rows=None, extras=(), raw_file=raw, page_file=page):
    if rows is not None: save(rows)
    cmd = [sys.executable, '-B', str(script), '--raw', str(raw_file), '--page', str(page_file), '--lane', 'LA', '--ledger', str(ledger), *extras]
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.stderr: print(p.stderr, end='')
    return p.returncode, p.stdout

def leg(ident, rows, expected, text, **kw):
    rc, out = run(rows, **kw)
    check(ident, rc == expected and text in out, f'raw_slices.py --raw RAW --page PAGE --lane LA --ledger LEDGER · exit {rc}' + ('' if rc == expected and text in out else '\n' + out))
    return out

clean = leg('R01 quote clean', events, 0, 'unresolved 0 · full no')
check('R02 same-run controls', 'controls: quotation found' in clean)
missing = copy.deepcopy(events); missing[1]['claims'][0]['facts'][0]['locator'] = 'Table 9'
leg('R03 missing table', missing, 0, 'UNRESOLVED claim 1')
leg('R04 missing table count', missing, 0, 'unresolved 1')
none = copy.deepcopy(events); none[1]['claims'] = []
leg('R05 no claims', none, 0, 'full: no ledger claims')
flagged = root / 'flagged.md'; flagged.write_text('---\nflagged: conversion suspect\n---\n# Source\n')
leg('R06 conversion suspect', events, 0, 'full: conversion suspect', page_file=flagged)
leg('R07 missing raw', events, 2, 'PROBE FAILED:', raw_file=root / 'absent.md')
empty = root / 'empty.md'; empty.write_text('')
leg('R08 empty raw', events, 2, 'PROBE FAILED: empty raw', raw_file=empty)
leg('R09 missing page', events, 2, 'PROBE FAILED:', page_file=root / 'absent.md')
leg('R10 empty page', events, 2, 'PROBE FAILED: empty source page', page_file=empty)
flat = root / 'flat.md'; flat.write_text('# Title\nNo headings.\n')
flat_events = copy.deepcopy(events); flat_events[1]['source'] = str(flat); flat_events[1]['claims'][0]['source'] = str(flat)
plain_page = root / 'plain.md'; plain_page.write_text('# Source\n')
flat_events[1]['claims'][0]['from'] = 'plain'
leg('R11 absent structure', flat_events, 0, 'full: no heading below title', raw_file=flat, page_file=plain_page)
drift = root / 'drift.md'; drift.write_text('---\nsource_hash: ' + '0' * 16 + '\n---\n# Source\n')
leg('R12 hash drift', events, 0, 'full: source_hash mismatch', page_file=drift)

for title in ['Aim', 'Data', 'Methods', 'R']:
    r = m.Raw('# T\n\n## ' + title + '\nDetail.\nSecond.\n\n## End\nEnd.\n')
    found, miss = r.resolve(title)
    check('R13-' + title + ' CR-153B-7 title', {2, 3, 4} <= found and not miss)
r = m.Raw('# T\n\n## Results\nTable 1: results\n\nA 10\nB 20\n\n## End\nEnd.\n')
check('R14 CR-153B-7 rows below caption', {5, 6} <= r.resolve('Table 1')[0])
check('R15 CR-153B-7 plural absent reference', r.resolve('Tables 1 and 9')[1] == ['tables 9'])
check('R16 CR-153B-7 plural present control', not r.resolve('Tables 1 and 1')[1])
for name, rows in [('plain', 'A 10\nB 20'), ('pipe', '| A | 10 |\n| B | 20 |')]:
    r = m.Raw('# T\n\n## Results\n' + rows + '\n\nTable 1: results\n\n## End\nEnd.\n')
    check('R17-' + name + ' CR-153C-N6 rows above caption', {3, 4} <= r.resolve('Table 1')[0])
r = m.Raw('# T\n\n## Results\nNothing.\n\n## End\nEnd.\n')
check('R18 CR-153C-N6 absent table control', not r.resolve('Table 1')[0] and bool(r.resolve('Table 1')[1]))
refpage = root / 'page-ref.md'; refpage.write_text('## Summary\nTables 1 and 9.\n')
out = leg('R19 source page references', events, 0, 'UNRESOLVED page Tables 1 and 9', page_file=refpage)

other = root / 'two' / 'paper.md'; other.parent.mkdir(); other.write_text(raw.read_text())
amb = copy.deepcopy(events); amb[0]['inbox'].append({'file':str(other)})
amb[1]['source'] = 'paper.md'; amb[1]['claims'][0]['source'] = 'paper.md'
amb[1]['claims'][0]['from'] = '[' * 2 + 'two-page|page' + ']' * 2
leg('R20 CR-153C-N4 display text is foreign', amb, 0, 'full: no ledger claims')
amb[1]['claims'][0]['from'] = '[' * 2 + 'two-page#page' + ']' * 2
leg('R21 CR-153C-N4 anchor is foreign', amb, 0, 'full: no ledger claims')
amb[1]['claims'][0]['from'] = '[' * 2 + 'two-page' + ']' * 2
leg('R22 CR-153C-N4 foreign control', amb, 0, 'full: no ledger claims')
amb[1]['claims'][0]['from'] = '[' * 2 + 'page' + ']' * 2
leg('R23 CR-153C-N4 own target', amb, 0, 'claims 1 · unresolved 0 · full no')
foreign = copy.deepcopy(events); foreign[1]['source'] = str(other); foreign[1]['claims'][0]['source'] = str(other)
leg('R24 CR-153C-N4 absolute foreign source', foreign, 0, 'full: no ledger claims')
suffix = copy.deepcopy(events); suffix[0]['inbox'].append({'file':str(root / 'other' / 'one' / 'paper.md')})
suffix[1]['source'] = 'one/paper.md'; suffix[1]['claims'][0]['source'] = 'one/paper.md'
leg('R25 CR-153C-N4 ambiguous path suffix', suffix, 0, 'full: no ledger claims')
suffix[0]['inbox'].pop()
leg('R26 CR-153C-N4 unique path suffix', suffix, 0, 'full no')
bare = copy.deepcopy(amb); bare[1]['claims'][0].pop('from')
leg('R27 ambiguous basename without page', bare, 0, 'full: no ledger claims')

# Conversion aliases collapse within each source before suffix ambiguity is checked.
second = root / 'other' / 'one' / 'paper.md'
second.parent.mkdir(parents=True); second.write_text(raw.read_text())
paired = copy.deepcopy(events)
paired[0]['inbox'] = [{'file': str(p)} for p in (raw, raw.with_suffix('.pdf'), second, second.with_suffix('.pdf'))]
paired[1]['source'] = 'one/paper.md'; paired[1]['claims'][0].pop('source')
leg('F1a two conversion pairs remain ambiguous', paired, 0, 'claims 0 · unresolved 0 · full yes')
unique_pair = copy.deepcopy(paired); unique_pair[0]['inbox'] = paired[0]['inbox'][:2]
leg('F1b unique conversion pair slices', unique_pair, 0, 'claims 1 · unresolved 0 · full no')
two_md = copy.deepcopy(paired); two_md[0]['inbox'] = [{'file': str(raw)}, {'file': str(second)}]
leg('F1c two Markdown identities remain ambiguous', two_md, 0, 'claims 0 · unresolved 0 · full yes')
reversed_pairs = copy.deepcopy(paired); reversed_pairs[0]['inbox'].reverse()
leg('F1d conversion identity order does not change ambiguity', reversed_pairs, 0, 'full: no ledger claims')

empty_claim = copy.deepcopy(events); empty_claim[1]['claims'] = [{}]
leg('F5a empty claim object rejected', empty_claim, 2, 'PROBE FAILED: empty claim object')
for ident, partial in [('name-only', {'name': 'Model'}), ('empty-facts', {'name': 'Model', 'facts': []}), ('missing-locator', {'name': 'Model', 'facts': [{'fact': 'Kept'}]}), ('blank-locator', {'name': 'Model', 'facts': [{'locator': '  '}]})]:
    partial_events = copy.deepcopy(events); partial_events[1]['claims'] = [partial]
    out = leg('F5b-' + ident + ' partial claim unresolved', partial_events, 0, 'claims 1 · unresolved 1 · full yes')
    check('F5c-' + ident + ' partial claim whole-read reason', 'full: partial claim' in out and 'UNRESOLVED claim 1' in out)
source_less = copy.deepcopy(events); source_less[1].pop('source')
source_less[1]['claims'][0].pop('source'); source_less[1]['claims'][0].pop('from')
leg('F5d missing source unresolved with whole read', source_less, 0, 'claims 1 · unresolved 1 · full yes')
leg('F5e complete claim still slices', events, 0, 'claims 1 · unresolved 0 · full no')
leg('F5f empty claim list still falls back', none, 0, 'claims 0 · unresolved 0 · full yes')

save(events); ledger.write_text(ledger.read_text() + '{torn\n')
rc, out = run(); check('R28 torn ledger', rc == 2 and 'full: malformed ledger' in out and 'PROBE FAILED:' in out)
for ident, value in [('object', {}), ('string', ['bad']), ('null', None)]:
    bad = copy.deepcopy(events); bad[1]['claims'] = value
    leg('R29-' + ident + ' malformed claims', bad, 2, 'PROBE FAILED:')
save(events)
rc, clean = run()
tracefile = root / 'slices.txt'; tracefile.write_text(clean)

def tr(ident, item, expected, needle, text=None):
    if text is not None: tracefile.write_text(text)
    args = [sys.executable, '-B', str(script), '--trace', str(tracefile)]
    if item is not None: args += ['--item', item]
    p = subprocess.run(args, capture_output=True, text=True)
    if p.stderr: print(p.stderr, end='')
    check(ident, p.returncode == expected and needle in p.stdout, f'raw_slices.py --trace OUTPUT --item {item} · exit {p.returncode}' + ('' if p.returncode == expected and needle in p.stdout else '\n' + p.stdout))

tr('R30 CR-153B-3/N1 outside LOSS', str(raw) + ':11', 1, 'LOSS', clean)
tr('R31 CR-153B-3/N1 inside VARIANCE', str(raw) + ':7', 0, 'VARIANCE')
tr('R32 crossing LOSS', str(raw) + ':9-11', 1, 'LOSS')
rc, whole = run(none, raw_file=other)
tr('R33 CR-153B-3/N1 added same basename retains LOSS', str(raw) + ':11', 1, 'LOSS', clean + whole)
tr('R34 CR-153B-3/N1 basename ambiguous', 'paper.md:11', 2, 'PROBE FAILED:')
tr('R35 whole source VARIANCE', str(other) + ':11', 0, 'VARIANCE')
tr('R36 trace missing source', 'absent.md:2', 2, 'PROBE FAILED:')
tr('R37 trace absent item', None, 2, 'PROBE FAILED:')
tr('R38 trace invalid item', str(raw) + ':0', 2, 'PROBE FAILED:')
tr('R39 trace empty output', str(raw) + ':1', 2, 'PROBE FAILED:', '')
tr('R40 CR-153C-N5 cut mid passage', str(raw) + ':15', 2, 'PROBE FAILED:', clean[:clean.index('14:')])
tr('R41 CR-153C-N5 missing controls', str(raw) + ':15', 2, 'PROBE FAILED:', clean[:clean.index('controls:')])
tr('R42 CR-153C-N5 complete line 15', str(raw) + ':15', 0, 'VARIANCE', clean)
tr('R43 duplicate output identity', str(raw) + ':15', 2, 'PROBE FAILED:', clean + clean)
tr('R44 incorrect numbered line', str(raw) + ':15', 2, 'PROBE FAILED:', clean.replace('15: Final.', '16: Final.'))
tr('R45 missing footer', str(raw) + ':15', 2, 'PROBE FAILED:', '\n'.join(x for x in clean.splitlines() if not x.startswith('raw: sha256')) + '\n')
tr('R46 malformed identity', str(raw) + ':1', 2, 'PROBE FAILED:', clean.replace('identity: {', 'identity: {bad'))

template = (here.parent / 'delegate/templates/brief-ingest-verify.md').read_text()
skill = (here / 'SKILL.md').read_text()
check('R47 part 2 template whole-raw confirmation', 'Every candidate' in template and 'whole' in template and 'skeleton' in template)
check('R48 CR-153B-3 shadow and rollback', '--trace' in skill and 'slicing loss' in skill and 'whole-raw' in skill)
check('R49 independent skeleton', m.Raw(raw.read_text()).skeleton() == m.Raw(raw.read_text()).skeleton() and '11: Outside fact.' not in clean)

# Part 6 adds its template checks here, before the final no-write proof.
block = template[template.index('### Compile lane {{compile lane id}}'):template.index('PROTOCOL,')]
slice_fixture = root / 'lane-slices.txt'; slice_fixture.write_text(clean)
m0_fixture = root / 'm0.txt'; m0_fixture.write_text('controls: fixture\n')
report_fixture = root / 'report.txt'; report_fixture.write_text('## Controls\nclaims-shape: fixture\n')

def filled(lane):
    values = [lane, str(page), str(raw), 'A deliberately absent plant claim', 'A true pointer', '[]', str(report_fixture), str(slice_fixture), str(m0_fixture)]
    slots = re.findall(r'\{\{[^}]+\}\}', block)
    if len(slots) != len(values): raise AssertionError('per-lane template slots changed')
    result = block
    for slot, value in zip(slots, values): result = result.replace(slot, value, 1)
    return result

def lint_brief(text, lanes):
    """The template leg checks the filled parallel form, including referenced files."""
    pieces = re.split(r'^### Compile lane (\S+)\s*$', text, flags=re.M)
    found, failures = [], []
    for i in range(1, len(pieces), 2):
        lane, body = pieces[i:i + 2]; found.append(lane)
        fields = dict(re.findall(r'^- ([^:]+): (.*)$', body, re.M))
        for key in ('Pages', 'Raws', 'Plant', 'Notes', 'Claims', 'Compile report', 'Slices file', 'M0 file'):
            if not fields.get(key, '').strip().strip('.') or '{{' in fields.get(key, ''): failures.append(lane + ' missing ' + key)
        for key in ('Compile report', 'Slices file', 'M0 file'):
            path = fields.get(key, '').rstrip('.')
            if not path or not Path(path).is_absolute() or not Path(path).is_file(): failures.append(lane + ' unreadable ' + key)
    # Six comes from the multi-lane design; set by judgement, unmeasured.
    if found != lanes or len(found) != len(set(found)) or not 1 <= len(found) <= 6: failures.append('lane list mismatch')
    return failures

two = filled('LA') + filled('LB')
check('V01 two-lane filled template', not lint_brief(two, ['LA', 'LB']), 'lint_brief(two, LA/LB) · exit 0')
missing_report = two.replace('- Compile report: ' + str(report_fixture) + '.\n', '', 1)
check('V01a missing compile report is rejected', any('Compile report' in why for why in lint_brief(missing_report, ['LA', 'LB'])))
check('V01b missing referenced compile report is rejected', any('Compile report' in why for why in lint_brief(two.replace(str(report_fixture), str(root / 'absent-report.txt'), 1), ['LA', 'LB'])))
missing_plant = two.replace('- Plant: A deliberately absent plant claim.\n', '', 1)
check('V02 missing one lane plant', bool(lint_brief(missing_plant, ['LA', 'LB'])), 'lint_brief(missing plant) · exit 1')
missing_slice = two.replace('- Slices file: ' + str(slice_fixture) + '.\n', '', 1)
check('V03 missing one lane slices', bool(lint_brief(missing_slice, ['LA', 'LB'])), 'lint_brief(missing slices) · exit 1')
check('V04 missing referenced slices', bool(lint_brief(two.replace(str(slice_fixture), str(root / 'missing.txt'), 1), ['LA', 'LB'])))
check('V05 duplicate lane id', bool(lint_brief(two.replace('### Compile lane LB', '### Compile lane LA'), ['LA', 'LB'])))
check('V06 absent lane block', bool(lint_brief(filled('LA'), ['LA', 'LB'])))
line = '<compile lane id> scores: fab <n> plant <n|-> cov <n> tier <n> struct <n> integ <n> lang <n> anom <n> claims <n|->'
check('V07 exact multi-lane score template', line in template)
reports = '\n'.join(line.replace('<compile lane id>', lane).replace('<n|->', '0').replace('<n>', '0') for lane in ['LA', 'LB']) + '\n'
names = ('fab', 'plant', 'cov', 'tier', 'struct', 'integ', 'lang', 'anom', 'claims')
pattern = '^[A-Z]+ scores: ' + ' '.join(name + ' [0-9]+' for name in names) + '$'
probe = subprocess.run(['grep', '-E', pattern], input=reports, text=True, capture_output=True)
if probe.stderr: print(probe.stderr, end='')
check('V08 two nine-name score lines parse', probe.returncode == 0 and len(probe.stdout.splitlines()) == 2, f'grep -E nine-name pattern · exit {probe.returncode} · lines {len(probe.stdout.splitlines())}')
probe = subprocess.run(['grep', '-E', pattern], input=reports.replace(' claims 0', ''), text=True, capture_output=True)
if probe.stderr: print(probe.stderr, end='')
check('V09 missing score name rejected', probe.returncode == 1, f'grep -E nine-name pattern · exit {probe.returncode}')
check('V10 per-lane records and controls', 'one `verify` event per compile lane' in template and 'own `## Controls`' in template and 'role: verify' in template)
check('V11 seventh lane and disputed call', 'a seventh opens a second' in skill and 'a disputed call re-runs that lane alone' in skill)
six_lanes = ['LA', 'LB', 'LC', 'LD', 'LE', 'LF']
check('V12 six-lane filled form passes', not lint_brief(''.join(filled(lane) for lane in six_lanes), six_lanes), 'lint_brief(six lanes) · exit 0')
seven_lanes = six_lanes + ['LG']
check('V13 seventh lane requires another verifier', bool(lint_brief(''.join(filled(lane) for lane in seven_lanes), seven_lanes)), 'lint_brief(seven lanes) · exit 1')

def manifest(directory):
    return {str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.rglob('*') if p.is_file()}

ro = root / 'readonly'; ro.mkdir(); (ro / 'raw.md').write_text(raw.read_text()); (ro / 'page.md').write_text(page.read_text())
ro_events = copy.deepcopy(events); ro_events[0]['inbox'] = [{'file':str(ro / 'raw.md')}]
ro_events[1]['source'] = str(ro / 'raw.md'); ro_events[1]['claims'][0]['source'] = str(ro / 'raw.md')
(ro / 'ledger.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in ro_events))
shutil.copyfile(script, ro / 'raw_slices.py')
before = manifest(ro)
for p in ro.rglob('*'): p.chmod(0o555 if p.is_dir() else 0o444)
ro.chmod(0o555)
p = subprocess.run([sys.executable, '-B', str(ro / 'raw_slices.py'), '--raw', str(ro / 'raw.md'), '--page', str(ro / 'page.md'), '--lane','LA','--ledger',str(ro / 'ledger.jsonl')], capture_output=True, text=True)
if p.stderr: print(p.stderr, end='')
check('R50 readonly execution', p.returncode == 0 and 'controls:' in p.stdout)
check('R51 checksum manifest unchanged', before == manifest(ro) and len(before) == 4, f'files {len(before)}')
changed = dict(before); changed['raw.md'] = 'planted'
check('R52 checksum positive control', changed != before)
patterns = [r'\.write(?:_text|_bytes)?\s*\(', r'\bopen\([^\n]*,[ ]*[\'\"][wax][^\'\"]*[\'\"]', r'\b(?:os|shutil)\.(?:replace|rename|remove|unlink|mkdir|makedirs|rmdir|copy|move|chmod)', r'\b(?:subprocess|os\.system|os\.popen)\b', r'\.(?:touch|unlink|mkdir|rename|replace|chmod)\s*\(']
controls = ['p.write_text(x)', 'open(p, "w")', 'os.replace(a,b)', 'subprocess.run(x)', 'p.unlink()']
source = script.read_text()
hits = [(pat, match.group()) for pat in patterns for match in re.finditer(pat, source)]
check('R53 source write grep controls', all(re.search(pat, control) for pat, control in zip(patterns, controls)), f'controls {len(controls)}')
check('R54 source write grep zero', not hits, f'hits {len(hits)}')
ro.chmod(0o755)
for p in ro.rglob('*'): p.chmod(0o755 if p.is_dir() else 0o644)
print(f'PASS {passed}/{passed + failed}' if not failed else f'FAIL {failed}/{passed + failed}')
sys.exit(bool(failed))
PY_RAW_SUITE
