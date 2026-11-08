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
    """Each per-lane slot filled by what its own text asks for, so a slot added to the template
    cannot shift the values of the slots after it."""
    by_slot = [('compile lane id', lane), ('absolute page paths', str(page)), ('absolute converted raw paths', str(raw)),
               ('raw <absolute converted raw> · page', 'raw ' + str(raw) + ' · page ' + str(page)),
               ('CONTEXT NOTES', 'A true pointer'),
               ('complete claim objects', '[]'), ('final report', str(report_fixture)),
               ('slices file', str(slice_fixture)), ('persisted M0 file', str(m0_fixture))]
    result = block
    for slot in re.findall(r'\{\{[^}]+\}\}', block):
        values = [value for key, value in by_slot if key in slot]
        if len(values) != 1: raise AssertionError('per-lane template slot not recognised: ' + slot)
        result = result.replace(slot, values[0], 1)
    return result

def lint_brief(text, lanes):
    """The template leg checks the filled parallel form, including referenced files."""
    pieces = re.split(r'^### Compile lane (\S+)\s*$', text, flags=re.M)
    found, failures = [], []
    for i in range(1, len(pieces), 2):
        lane, body = pieces[i:i + 2]; found.append(lane)
        fields = dict(re.findall(r'^- ([^:]+): (.*)$', body, re.M))
        for key in ('Pages', 'Raws', 'Locator evidence', 'Notes', 'Claims', 'Compile report', 'Slices file', 'M0 file'):
            if not fields.get(key, '').strip().strip('.') or '{{' in fields.get(key, ''): failures.append(lane + ' missing ' + key)
        for key in ('Compile report', 'Slices file', 'M0 file'):
            path = fields.get(key, '').rstrip('.')
            if not path or not Path(path).is_absolute() or not Path(path).is_file(): failures.append(lane + ' unreadable ' + key)
    # No lane-count cap: the ingest size rule bounds a verifier by raw bytes against its model's ceiling.
    if found != lanes or len(found) != len(set(found)) or not found: failures.append('lane list mismatch')
    return failures

two = filled('LA') + filled('LB')
check('V01 two-lane filled template', not lint_brief(two, ['LA', 'LB']), 'lint_brief(two, LA/LB) · exit 0')
missing_report = two.replace('- Compile report: ' + str(report_fixture) + '.\n', '', 1)
check('V01a missing compile report is rejected', any('Compile report' in why for why in lint_brief(missing_report, ['LA', 'LB'])))
check('V01b missing referenced compile report is rejected', any('Compile report' in why for why in lint_brief(two.replace(str(report_fixture), str(root / 'absent-report.txt'), 1), ['LA', 'LB'])))
missing_pairs = re.sub(r'^- Locator evidence: .*\n', '', two, count=1, flags=re.M)
check('V01c a lane block without its Locator evidence line (the raw and page pairs its locators: lines must name) is rejected', missing_pairs != two and any('Locator evidence' in why for why in lint_brief(missing_pairs, ['LA', 'LB'])))
missing_notes = two.replace('- Notes: A true pointer.\n', '', 1)
check('V02 missing one lane notes', missing_notes != two and bool(lint_brief(missing_notes, ['LA', 'LB'])), 'lint_brief(missing notes) · exit 1')
check('V02b the verify template carries no plant slot, dimension or score', 'plant' not in template.lower())
missing_slice = two.replace('- Slices file: ' + str(slice_fixture) + '.\n', '', 1)
check('V03 missing one lane slices', bool(lint_brief(missing_slice, ['LA', 'LB'])), 'lint_brief(missing slices) · exit 1')
check('V04 missing referenced slices', bool(lint_brief(two.replace(str(slice_fixture), str(root / 'missing.txt'), 1), ['LA', 'LB'])))
check('V05 duplicate lane id', bool(lint_brief(two.replace('### Compile lane LB', '### Compile lane LA'), ['LA', 'LB'])))
check('V06 absent lane block', bool(lint_brief(filled('LA'), ['LA', 'LB'])))
line = '<compile lane id> scores: fab <n> cov <n> tier <n> struct <n> integ <n> lang <n> anom <n> claims <n|->'
check('V07 exact multi-lane score template', line in template)
reports = '\n'.join(line.replace('<compile lane id>', lane).replace('<n|->', '0').replace('<n>', '0') for lane in ['LA', 'LB']) + '\n'
names = ('fab', 'cov', 'tier', 'struct', 'integ', 'lang', 'anom', 'claims')
pattern = '^[A-Z]+ scores: ' + ' '.join(name + ' [0-9]+' for name in names) + '$'
probe = subprocess.run(['grep', '-E', pattern], input=reports, text=True, capture_output=True)
if probe.stderr: print(probe.stderr, end='')
check('V08 two eight-name score lines parse', probe.returncode == 0 and len(probe.stdout.splitlines()) == 2, f'grep -E eight-name pattern · exit {probe.returncode} · lines {len(probe.stdout.splitlines())}')
probe = subprocess.run(['grep', '-E', pattern], input=reports.replace(' claims 0', ''), text=True, capture_output=True)
if probe.stderr: print(probe.stderr, end='')
check('V09 missing score name rejected', probe.returncode == 1, f'grep -E eight-name pattern · exit {probe.returncode}')
check('V10 per-lane records and controls', 'one `verify` event per compile lane' in template and 'own `## Controls`' in template and 'role: verify' in template)
check('V11 verifier grouping by raw bytes and disputed call', "that verifier model's `CEILING`" in skill and 'a seventh opens a second' not in skill and 'a disputed call re-runs that lane alone' in skill)
six_lanes = ['LA', 'LB', 'LC', 'LD', 'LE', 'LF']
check('V12 six-lane filled form passes', not lint_brief(''.join(filled(lane) for lane in six_lanes), six_lanes), 'lint_brief(six lanes) · exit 0')
seven_lanes = six_lanes + ['LG']
check('V13 a seventh lane passes (no count cap); an empty lane list is still rejected', not lint_brief(''.join(filled(lane) for lane in seven_lanes), seven_lanes) and bool(lint_brief('', [])), 'lint_brief(seven lanes) · exit 0; lint_brief(none) · exit 1')
check('V13b the verify template states no lane-count cap in any slot', 'one to six' not in template and 'up to six' not in template and 'seventh' not in template)

# Claims-locator check: the slicer's own attribution and locator resolution before and after the
# claims_emitted append (design review finding 6), and the verify brief's consumer of its evidence
# (finding 7). Every leg fails on a slicer without --check-claims.
def chk(rows, extras=(), event=None, raw_file=raw, page_file=page, lane='LA'):
    if rows is not None: save(rows)
    cmd = [sys.executable, '-B', str(script), '--check-claims', '--raw', str(raw_file), '--page', str(page_file), '--lane', lane, '--ledger', str(ledger), *extras]
    if event is not None: cmd += ['--event', event if isinstance(event, str) else json.dumps(event)]
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.stderr: print(p.stderr, end='')
    return p.returncode, p.stdout

def cleg(ident, expected, needles, *args, **kw):
    rc, out = chk(*args, **kw)
    good = rc == expected and all(n in out for n in needles)
    check(ident, good, f'raw_slices.py --check-claims · exit {rc}' + ('' if good else '\n' + out))
    return out

ckpt, opened = events[1], [events[0]]
clean_line = 'checkpoints 1 · claims 1 · facts 1 · resolved 1 · unresolved 0 · missing 0 · unattributed 0'
cleg('C01 ledger mode: a resolvable quotation passes', 0, [clean_line, 'controls: slicer controls passed'], events)
cleg('C02 event mode: the checkpoint to append, read as though appended, passes', 0, [clean_line, 'mode event'], opened, event=ckpt)
loc = copy.deepcopy(ckpt); loc['claims'][0]['facts'] = [{'fact': 'Kept', 'loc': '"Kept quotation."'}]
loc_out = cleg('C03 a planted fact keyed loc fails before the append, naming the key it found', 1, ['MISSING claim 1 Model fact 1: no locator key (found loc)', 'missing 1 · unattributed 0'], opened, event=loc)
cleg('C04 a Table 9 locator is unresolved', 1, ['UNRESOLVED claim 1 Model fact 1 Table 9: table 9', 'unresolved 1'], opened, event=missing[1])
both = [events[0], loc, copy.deepcopy(ckpt)]
both_out = cleg('C05 an earlier bad checkpoint followed by a later good one still fails in ledger mode', 1, ['checkpoints 2 · claims 2', 'missing 1'], both)
rc, slice_out = run(both)
check('C06 the check and the slicer agree on that ledger: the slicer takes full: partial claim', rc == 0 and 'full: partial claim' in slice_out and 'MISSING claim 1 Model fact 1' in both_out, f'slicer exit {rc}')

def parity(ident, rows, unattributed):
    save(rows)
    rc, out = chk(None)
    mm = re.search(r'^locators: (?:.* · )?checkpoints \d+ · claims (\d+) · .* · unattributed (\d+)$', out, re.M)
    selected = len(m.lane_claims(rows, 'LA', raw.resolve(), page.resolve()))
    good = bool(mm) and int(mm[2]) == unattributed and int(mm[1]) - int(mm[2]) == selected and rc == (1 if unattributed else 0)
    check(ident, good, f'check: claims {mm[1] if mm else "?"} · unattributed {mm[2] if mm else "?"} · lane_claims() selects {selected} · exit {rc}' + ('' if good else '\n' + out))

foreign_page = copy.deepcopy(events); foreign_page[1]['claims'][0]['from'] = '[' * 2 + 'other-page' + ']' * 2
suffix_amb = copy.deepcopy(events); suffix_amb[0]['inbox'].append({'file': str(root / 'other' / 'one' / 'paper.md')})
suffix_amb[1]['source'] = 'one/paper.md'; suffix_amb[1]['claims'][0]['source'] = 'one/paper.md'
bare_own = copy.deepcopy(events); bare_own[0]['inbox'].append({'file': str(other)})
bare_own[1]['source'] = 'paper.md'; bare_own[1]['claims'][0]['source'] = 'paper.md'
bare_none = copy.deepcopy(bare_own); bare_none[1]['claims'][0].pop('from')
parity('C07 correct page: selected by lane_claims() and by the check (unattributed 0)', events, 0)
parity('C08 foreign page: lane_claims() selects nothing and the check reads UNATTRIBUTED', foreign_page, 1)
parity('C09 ambiguous source path suffix: no selection by either, UNATTRIBUTED', suffix_amb, 1)
parity('C10 ambiguous bare basename on its own page: selected by both', bare_own, 0)
parity('C11 ambiguous bare basename with no page: no selection by either, UNATTRIBUTED', bare_none, 1)

empty_raw = root / 'empty-check.md'; empty_raw.write_text('')
cleg('C12 premise: an empty raw', 2, ['PROBE FAILED: empty raw'], events, raw_file=empty_raw)
cleg('C13 premise: a missing source page', 2, ['PROBE FAILED: source page missing'], events, page_file=root / 'absent-page.md')
save(events); ledger.write_text(ledger.read_text() + '{torn\n')
cleg('C14 premise: a malformed ledger line', 2, ['PROBE FAILED: malformed ledger line'], None)
cleg('C15 premise: --event is not JSON', 2, ['PROBE FAILED: --event is not JSON'], opened, event='{not json')
cleg('C16 premise: --event is not a claims_emitted checkpoint', 2, ['PROBE FAILED: --event is not a claims_emitted checkpoint'], opened, event={'event': 'checkpoint', 'stage': 'read', 'lane': 'LA'})
cleg('C17 premise: --event names another lane', 2, ['PROBE FAILED: --event names lane LB'], opened, event=dict(ckpt, lane='LB'))
cleg('C18 premise: claims not a list of objects', 2, ['PROBE FAILED: claims must be a list of objects'], opened, event=dict(ckpt, claims=['Model']))
cleg('C19 premise: no checkpoint for this lane and raw in the ledger', 2, ['PROBE FAILED: no claims_emitted checkpoint'], opened)
cleg('C20 premise: --source does not name --raw', 2, ['PROBE FAILED: --source does not name --raw'], events, extras=['--source', 'elsewhere/other.md'])
cleg('C21 premise: the checkpoint source names another raw', 2, ['PROBE FAILED: the checkpoint source does not name --raw'], opened, event=dict(ckpt, source=str(other)))
rc, out = run(events, extras=['--event', '{}'])
check('C22 premise: --event without --check-claims is refused', rc == 2 and 'PROBE FAILED: --event belongs to --check-claims' in out, f'exit {rc}')
cleg('C23 an empty claims list passes with claims 0', 0, ['claims 0 · facts 0', 'unattributed 0'], opened, event=dict(ckpt, claims=[], claims_count=0))
sab_text = script.read_text()
anchor = "'facts': [{'loc': '\"A known phrase.\"'}]"
sab = root / 'sabotaged_slices.py'; sab.write_text(sab_text.replace(anchor, "'facts': [{'locator': '\"A known phrase.\"'}]", 1))
p = subprocess.run([sys.executable, '-B', str(sab), '--check-claims', '--raw', str(raw), '--page', str(page), '--lane', 'LA', '--ledger', str(ledger)], capture_output=True, text=True)
check('C24 a sabotaged built-in control (the loc fact keyed locator) stops the run, exit 2', sab_text.count(anchor) == 1 and p.returncode == 2 and 'PROBE FAILED: claims-locator controls failed' in p.stdout, f'exit {p.returncode}')

core = (here.parent / 'delegate/lane-home-src/compile-core/SKILL.md').read_text()
brief_c = (here.parent / 'delegate/templates/brief-compile.md').read_text()
check('C25 compile-core §5 names the check, the locator key and what resolves', '--check-claims' in core and "Each fact's locator sits under the key `locator`" in core and 'A bare line number is not one the slicer resolves' in core)
check('C26 the compile brief runs the check before and after the append and records locators:', '--check-claims' in brief_c and '`locators:` line for each raw under `## Controls`' in brief_c and 'never `loc` or `location`' in brief_c)
check('C27 the ingest skill parallel step 4 names the check', 'raw_slices.py --check-claims' in skill)
loc_every = re.findall(r"grep -cE '(\^locators:)'", template)
loc_valid = re.findall(r"grep -cxE '([^']+)'", template)
loc_ident = re.findall(r"grep -F '(locators: lane <compile lane id> · raw <raw> · page <page> · checkpoints )'", template)
shape_req = re.findall(r"grep -qxE '([^']+)'", template)
shape_forb = re.findall(r"grep -qE '([^']+)'", template)
check('C28 the verify brief carries one keyed locator check (the line count, the clean form naming lane, raw and page, the per-raw identity grep) beside the one shape pair',
      len(loc_every) == len(loc_valid) == len(loc_ident) == len(shape_req) == len(shape_forb) == 1
      and loc_valid[0].startswith('locators: lane ') and ' · raw ' in loc_valid[0] and ' · page ' in loc_valid[0])

def controls_section(report):
    s = re.search(r'^## Controls\n(.*?)(?=^## |\Z)', report, re.M | re.S)
    return s[1] if s else ''

def grep_run(args, text):
    p = subprocess.run(['grep', *args], input=text, capture_output=True, text=True)
    if p.returncode not in (0, 1): raise RuntimeError('grep failed: ' + p.stderr)
    return p

def shape_ok(report):
    if len(shape_req) != 1 or len(shape_forb) != 1: return False
    t = controls_section(report)
    return grep_run(['-qxE', shape_req[0]], t).returncode == 0 and grep_run(['-qE', shape_forb[0]], t).returncode == 1

def locators_ok(report, lane, pairs):
    """The verify brief's locator check, run as it states it: every `locators:` line of the Controls
    section clean and keyed, then for each (raw, page) pair of the lane the identity grep piped into
    the same clean-form grep, which must count 1 or more."""
    if len(loc_every) != 1 or len(loc_valid) != 1 or len(loc_ident) != 1:
        return None  # no keyed consumer in the verify brief: every leg below fails
    t = controls_section(report)
    every = int(grep_run(['-cE', loc_every[0]], t).stdout.strip() or 0)
    valid = int(grep_run(['-cxE', loc_valid[0]], t).stdout.strip() or 0)
    if every != valid:
        return False
    for raw_path, page_path in pairs:
        ident = loc_ident[0].replace('<compile lane id>', lane).replace('<raw>', raw_path).replace('<page>', page_path)
        selected = grep_run(['-F', ident], t).stdout
        if int(grep_run(['-cxE', loc_valid[0]], selected).stdout.strip() or 0) < 1:
            return False
    return True

# A two-raw lane: raw A (one/paper.md, its page page.md) and raw B (two/paper.md, its page page-b.md).
page_b = root / 'page-b.md'; page_b.write_text('---\nsource_hash: ' + m.digest(other.read_bytes()) + '\n---\n# Source B\n')
A, PA, B, PB = str(raw.resolve()), str(page.resolve()), str(other.resolve()), str(page_b.resolve())
two_pairs = [(A, PA), (B, PB)]
shape_line = 'claims-shape: checkpoints 1 · objects 1 · invalid 0\n'
bad_counts = 'checkpoints 1 · claims 1 · facts 1 · resolved 0 · unresolved 1 · missing 0 · unattributed 0'
def keyed(lane, raw_path, page_path, counts=clean_line):
    return f'locators: lane {lane} · raw {raw_path} · page {page_path} · {counts}\n'
report_cases = [
    ('two-raws-complete', keyed('LA', A, PA) + keyed('LA', B, PB), two_pairs, True),
    ('raw-A-line-twice-for-two-raws', keyed('LA', A, PA) + keyed('LA', A, PA), two_pairs, False),
    ('A-clean-B-failed', keyed('LA', A, PA) + keyed('LA', B, PB, bad_counts), two_pairs, False),
    ('A-clean-B-absent', keyed('LA', A, PA), two_pairs, False),
    ('B-line-names-another-lane', keyed('LA', A, PA) + keyed('LB', B, PB), two_pairs, False),
    ('B-line-names-A-page', keyed('LA', A, PA) + keyed('LA', B, PA), two_pairs, False),
    ('B-line-names-a-longer-page-path', keyed('LA', A, PA) + keyed('LA', B, PB + '.old'), two_pairs, False),
    ('B-line-quoted', keyed('LA', A, PA) + '> ' + keyed('LA', B, PB), two_pairs, False),
    ('unkeyed-lines', ('locators: ' + clean_line + '\n') * 2, two_pairs, False),
    ('no-locators-lines', '', two_pairs, False),
    ('one-raw-complete', keyed('LA', A, PA), [(A, PA)], True),
    ('one-raw-failed', keyed('LA', A, PA, bad_counts), [(A, PA)], False),
]
for name, lines, pairs, expected in report_cases:
    report = '## Controls\n' + shape_line + lines
    check('C29-' + name + ' (valid shape evidence in every case)', shape_ok(report) and locators_ok(report, 'LA', pairs) is expected)
outside = '## Findings\n' + keyed('LA', A, PA) + keyed('LA', B, PB) + '## Controls\n' + shape_line
check('C29-lines-outside-controls (valid shape evidence)', shape_ok(outside) and locators_ok(outside, 'LA', two_pairs) is False)

claim_b = {'name': 'Bench', 'source': str(other), 'from': '[' * 2 + 'page-b' + ']' * 2, 'facts': [{'fact': 'Kept', 'locator': '"Kept quotation."'}]}
two_raw = [{'event': 'run_open', 'run': 'fixture', 'inbox': [{'file': str(raw)}, {'file': str(other)}]}, copy.deepcopy(events[1]),
           {'event': 'checkpoint', 'stage': 'claims_emitted', 'run': 'fixture', 'lane': 'LA', 'source': str(other), 'claims': [claim_b]}]
rc_a, out_a = chk(two_raw)
rc_b, out_b = chk(None, raw_file=other, page_file=page_b)
line_a = next((line for line in out_a.splitlines() if line.startswith('locators:')), '')
line_b = next((line for line in out_b.splitlines() if line.startswith('locators:')), '')
real_bad = next((line for line in loc_out.splitlines() if line.startswith('locators:')), '')
check("C30 the check's own summary lines: both raws' lines satisfy the verifier's check, raw A's line twice does not cover raw B, and the loc run's line fails it",
      rc_a == 0 and rc_b == 0
      and locators_ok('## Controls\n' + shape_line + line_a + '\n' + line_b + '\n', 'LA', two_pairs) is True
      and locators_ok('## Controls\n' + shape_line + line_a + '\n' + line_a + '\n', 'LA', two_pairs) is False
      and locators_ok('## Controls\n' + shape_line + real_bad + '\n', 'LA', [(A, PA)]) is False, f'exits {rc_a} {rc_b}')
check('C32 the compile-side carriers produce the keyed line: compile-core §5 shows it, and the compile brief LEDGER and REPORT lines and ingest Parallel step 4 say it names the lane, the raw and its source page',
      '`locators: lane <lane id> · raw <absolute raw> · page <absolute source page> · checkpoints N' in core
      and "one raw's line never stands in for another's" in core
      and 'it names this lane, the raw and its source page, which the verifier matches raw by raw' in brief_c
      and 'naming this lane, the raw and its source page as the check printed them' in brief_c
      and "the check's `locators:` line, which names the lane, the raw and its source page" in skill)
check('C33 the summary line names its lane, raw and page: each raw of a two-raw lane prints its own resolved paths',
      line_a == keyed('LA', A, PA).rstrip('\n') and line_b == keyed('LA', B, PB).rstrip('\n'), 'raw A: ' + line_a)
cleg('C34 premise: a lane id the summary line cannot name as one token', 2, ['PROBE FAILED: --lane must be one token'], events, lane='L A')

def tree_hashes(directory):
    return {str(q.relative_to(directory)): hashlib.sha256(q.read_bytes()).hexdigest() for q in directory.rglob('*') if q.is_file()}

ro_check = root / 'readonly-check'; ro_check.mkdir()
(ro_check / 'raw.md').write_text(raw.read_text()); (ro_check / 'page.md').write_text(page.read_text())
rc_events = copy.deepcopy(events); rc_events[0]['inbox'] = [{'file': str(ro_check / 'raw.md')}]
rc_events[1]['source'] = str(ro_check / 'raw.md'); rc_events[1]['claims'][0]['source'] = str(ro_check / 'raw.md')
(ro_check / 'ledger.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in rc_events))
before_check = tree_hashes(ro_check)
for q in ro_check.rglob('*'): q.chmod(0o444)
ro_check.chmod(0o555)
base_cmd = [sys.executable, '-B', str(script), '--check-claims', '--raw', str(ro_check / 'raw.md'), '--page', str(ro_check / 'page.md'), '--lane', 'LA', '--ledger', str(ro_check / 'ledger.jsonl')]
p1 = subprocess.run(base_cmd, capture_output=True, text=True)
p2 = subprocess.run(base_cmd + ['--event', json.dumps(rc_events[1])], capture_output=True, text=True)
ro_check.chmod(0o755)
for q in ro_check.rglob('*'): q.chmod(0o644)
check('C31 both check modes run against a read-only copy and its checksum manifest is unchanged', p1.returncode == 0 and p2.returncode == 0 and before_check == tree_hashes(ro_check) and len(before_check) == 3, f'exits {p1.returncode} {p2.returncode} · files {len(before_check)}')

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
