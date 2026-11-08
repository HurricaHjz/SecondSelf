#!/bin/sh
# Fixtures and patch artefacts live only below mktemp, removed on every exit.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TMP_CASE=$(mktemp -d "${TMPDIR:-/tmp}/merge-plan-suite.XXXXXX")
trap 'chmod -R u+w "$TMP_CASE"; rm -rf "$TMP_CASE"' EXIT HUP INT TERM
python3 -B - "$HERE" "$TMP_CASE" "${1:-$HERE/merge_plan.py}" <<'PY_MERGE_SUITE'
import copy
import contextlib
import difflib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from unittest import mock

here, root, script = map(Path, sys.argv[1:])
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('planner', script)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
passed = failed = 0

def check(leg, condition, detail=''):
    global passed, failed
    if condition: passed += 1; print('ok ' + leg + (' · ' + detail if detail else ''))
    else: failed += 1; print('FAIL ' + leg + (' · ' + detail if detail else ''))

# The union rule reads Markdown through markdown-it-py (IDEAS №172). The suite's own
# independent checks parse with it too, never with the planner's functions.
try:
    import markdown_it
    from markdown_it import MarkdownIt
except ImportError as error:
    print('PROBE FAILED: markdown-it-py not importable in the suite interpreter (' + str(error) + ')')
    sys.exit(2)
PARSER_PIN = '4.2.0'  # The capability register's pin: the version these probe sets were accepted on.
if markdown_it.__version__ != PARSER_PIN:
    print('PROBE FAILED: markdown-it-py ' + PARSER_PIN + ' expected, found ' + markdown_it.__version__ + '; re-run the acceptance and update the pin')
    sys.exit(2)
print('premise: markdown-it-py ' + markdown_it.__version__)
INDEPENDENT = MarkdownIt('commonmark')
try:
    import yaml  # Independent metadata oracle; the planner does not import PyYAML.
except ImportError as error:
    print('PROBE FAILED: PyYAML not importable in the suite interpreter (' + str(error) + ')')
    sys.exit(2)
BS, NBSP = chr(92), chr(0xa0)  # Escapes are built, never typed, so no tool decodes them on the way in.

def independent_offset(lines):
    if not lines or lines[0].strip() != '---': return 0
    for index, row in enumerate(lines[1:], 1):
        if re.fullmatch(r'(?:---|[.]{3})[ \t]*', row.rstrip('\r\n')): return index + 1
    raise ValueError('independent frontmatter does not close')

def independent_tokens(page):
    lines = page.splitlines(keepends=True)
    offset = independent_offset(lines)
    return lines, offset, INDEPENDENT.parse(''.join(lines[offset:]))

def independent_items(page, texts, title):
    """Each text is some line that starts a top-level list item holding only that line, under the named top-level heading."""
    lines, offset, tokens = independent_tokens(page)
    headings = [(t.map[1] + offset, tokens[i + 1].content.strip()) for i, t in enumerate(tokens) if t.type == 'heading_open' and t.level == 0]
    items = {t.map[0] + offset: t.map[1] + offset for t in tokens if t.type == 'list_item_open' and t.level == 1}
    def item(index):
        if index not in items or any(lines[j].strip(' \t\r\n') for j in range(index + 1, items[index])): return False
        above = [name for end, name in headings if end <= index]
        return bool(above) and above[-1] == title
    return bool(page) and all(any(item(i) for i, line in enumerate(lines) if line.rstrip('\r\n') == text) for text in texts)

def independent_code(page, text):
    """Some line with this text lies inside a fence or an indented code block."""
    lines, offset, tokens = independent_tokens(page)
    spans = [(t.map[0] + offset, t.map[1] + offset) for t in tokens if t.type in ('fence', 'code_block')]
    return any(start <= i < end for i, line in enumerate(lines) if line.rstrip('\r\n') == text for start, end in spans)

def independent_heading(page, title):
    lines, offset, tokens = independent_tokens(page)
    return any(t.type == 'heading_open' and t.level == 0 and tokens[i + 1].content.strip() == title for i, t in enumerate(tokens))

def placed(output, construct, where='added line'):
    """A placement refusal: manual, no command, one reason naming the construct and the line."""
    reasons = [line for line in output.splitlines() if line.startswith('  reason: union placement refused:')]
    return 'manual GPT' in output and 'conflict GPT' not in output and 'patch -F0' not in output and len(reasons) == 1 and construct in reasons[0] and where in reasons[0]

vault = root / 'vault'; (vault / 'wiki' / 'models').mkdir(parents=True)
target = vault / 'wiki' / 'models' / 'GPT.md'
base = '---\ntitle: GPT\ntype: model\nconfidence: medium\naliases: [GPT-4o]\n---\n# GPT\n\n## Key Points\nOriginal.\n\n## Appears in\n\n## Related\n'
target.write_text(base)
new = base.replace('Original.','Original.\nAdded.')
diff = root / 'update.diff'
rel = 'wiki/models/GPT.md'

def make_diff(path, old, new, oldpath='a/' + rel, newpath='b/' + rel, context=3):
    lines = difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile=oldpath, tofile=newpath, n=context)
    path.write_text(''.join(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n' for line in lines))
    return path

make_diff(diff, base, new)
claim = {'name':'GPT', 'type':'model', 'kind':'update','target':'GPT','source':'one.md','from':'one-page','facts':[{'fact':'Added.','locator':'Results'}], 'confidence':'medium','base':m.digest(base.encode()),'diff':str(diff),'diff_hash':m.digest(diff.read_bytes())}
scores = 'scores: fab 0 cov 0 tier 0 struct 0 integ 0 lang 0 anom 0 claims 0'

def event(kind, minute, lane=None, **kw):
    value = {'event':kind, 'run':'fixture','ts':f'2026-01-01T10:{minute:02}:00+00:00'}
    if lane: value['lane'] = lane
    value.update(kw); return value

def cycle(lane='LA', offset=0, claims=None):
    return [event('lane_open',1+offset,lane,role='compile'),event('checkpoint',2+offset,lane,stage='claims_emitted',claims=[copy.deepcopy(claim)] if claims is None else claims),event('lane_close',3+offset,lane),event('verify',4+offset,lane,scores=scores,quarantined=[])]

rows = [event('run_open',0,inbox=[])] + cycle()
ledger = root / 'ledger.jsonl'

def save(values, path=ledger):
    path.write_text(''.join(json.dumps(v) + '\n' for v in values))

def run(values=None, extra=(), ledger_file=ledger):
    if values is not None: save(values, ledger_file)
    args = [sys.executable,'-B',str(script),'--vault',str(vault),'--ledger',str(ledger_file), *map(str,extra)]
    p = subprocess.run(args,text=True,capture_output=True)
    if p.stderr: print(p.stderr,end='')
    return p.returncode,p.stdout

def leg(ident, values, code, needle, extra=()):
    rc, out = run(values, extra)
    good = rc == code and needle in out
    check(ident,good,f'merge_plan.py --vault VAULT --ledger LEDGER {" ".join(map(str,extra))} · exit {rc}' + ('' if good else '\n' + out))
    return out

clean = leg('M01 matching base',rows,0,'apply GPT')
check('M02 same-run controls', 'controls:' in clean)
conflict = copy.deepcopy(rows) + cycle('LB')
conflict[6]['claims'][0]['name'] = 'GPT-4o'; conflict[6]['claims'][0]['target'] = 'GPT-4o'
out = leg('M03 alias collision',conflict,0,'conflict GPT')
check('M04 alias collision no apply', '\napply ' not in '\n' + out)
raised = root / 'raised.diff'; make_diff(raised,base,new.replace('confidence: medium','confidence: high'))
lift = copy.deepcopy(rows); lift[2]['claims'][0].update(diff=str(raised),diff_hash=m.digest(raised.read_bytes()),confidence='high')
out = leg('M05 CR-153-1 raised apply',lift,0,'tier-raised GPT')
check('M06 CR-153-1 post-read path', 'then apply' in out and '\napply ' not in '\n' + out)
lift_conflict = copy.deepcopy(lift) + cycle('LB')
out = leg('M07 CR-153-1 conflict precedence',lift_conflict,0,'conflict GPT')
check('M08 raising conflict requires full page', 'confidence lift: read the page in full' in out)
drift = copy.deepcopy(lift); drift[2]['claims'][0]['base'] = '0' * 16
out = leg('M09 CR-153-1 manual precedence',drift,0,'manual GPT')
check('M10 raising manual requires full page', 'then manual' in out and 'tier-raised GPT' not in out)
missing = copy.deepcopy(rows); missing[2]['claims'][0].pop('diff')
leg('M11 missing diff',missing,0,'manual GPT')
missing[2]['claims'][0]['diff'] = str(root / 'absent.diff')
leg('M12 absent diff',missing,0,'manual GPT')
hashbad = copy.deepcopy(rows); hashbad[2]['claims'][0]['diff_hash'] = '0' * 16
leg('M13 changed diff hash',hashbad,0,'manual GPT')
target.write_text(base + 'Drift.\n')
leg('M14 moved current page',rows,0,'manual GPT'); target.write_text(base)

# Drift outside a hunk still passes exact-context patching; the base must stop it.
drifted_title = base.replace('title: GPT', 'title: Changed')
def inspected_run(change):
    save(rows)
    original = m.Catalogue
    def after_inspection(path):
        catalogue = original(path)
        if change == 'remove': target.unlink()
        elif change is not None: target.write_text(change)
        return catalogue
    output = io.StringIO()
    try:
        with mock.patch.object(m, 'Catalogue', side_effect=after_inspection), contextlib.redirect_stdout(output):
            code = m.main(['--vault', str(vault), '--ledger', str(ledger)])
        return code, output.getvalue()
    finally:
        target.write_text(base)

rc,out=inspected_run(drifted_title)
check('F3a drift after inspection becomes manual',rc==0 and 'manual GPT' in out and 'patch -F0' not in out,'merge_plan.main with post-catalogue title drift · exit '+str(rc))
check('F3b moved hash is never advertised as expected', 'base recheck immediately before real patch: '+m.digest(drifted_title.encode()) not in out)
target.write_text(drifted_title)
p=subprocess.run(shlex.split(m.patch_command(vault,target,diff,root/'drift.rej')),text=True,capture_output=True)
if p.stderr:print(p.stderr,end='')
check('F3c drift lies outside the hunk',p.returncode==0,'patch -F0 --dry-run on changed title · exit '+str(p.returncode))
target.write_text(base)
rc,out=inspected_run(None)
check('F3d unchanged snapshot applies with original hash',rc==0 and 'apply GPT' in out and 'base recheck immediately before real patch: '+claim['base'] in out,'merge_plan.main unchanged catalogue · exit '+str(rc))
rc,out=inspected_run('remove')
check('F3e missing base after inspection is manual',rc==0 and 'manual GPT' in out and 'patch -F0' not in out,'merge_plan.main with removed base · exit '+str(rc))

empty = root / 'empty.jsonl'; empty.write_text('')
rc,out = run(ledger_file=empty); check('M15 empty ledger',rc==2 and 'PROBE FAILED:' in out)
bad = root / 'bad.jsonl'; bad.write_text('not json\n')
rc,out = run(ledger_file=bad); check('M16 unparseable ledger',rc==2 and 'PROBE FAILED:' in out)
rc,out = run(ledger_file=root/'missing.jsonl'); check('M17 missing ledger',rc==2 and 'PROBE FAILED:' in out)
zero = [event('run_open',0,inbox=[])]
out = leg('M18 zero targets control',zero,0,'summary: targets 0')
check('M19 zero targets has control', 'controls:' in out)

nodiff = root / 'prose.diff'; nodiff.write_text('A prose proposal, with no diff.\n')
prose = copy.deepcopy(rows); prose[2]['claims'][0].update(diff=str(nodiff),diff_hash=m.digest(nodiff.read_bytes()))
out = leg('M20 CR-153C-N7 hashed prose',prose,0,'manual GPT')
check('M21 CR-153C-N7 no patch for prose', 'patch -F0' not in out)
leg('M22 CR-153C-N7 valid control',rows,0,'apply GPT')
for ident, content in [('empty',''),('torn','--- a/' + rel + '\n+++ b/' + rel + '\n@@ -1,9 +1,9 @@\n context\n'),('multi',diff.read_text()+diff.read_text())]:
    badfile=root/(ident+'.diff');badfile.write_text(content)
    val=copy.deepcopy(rows);val[2]['claims'][0].update(diff=str(badfile),diff_hash=m.digest(badfile.read_bytes()))
    leg('M23-'+ident+' unusable diff',val,0,'manual GPT')
for ident, header in [('absolute',str(target)),('dot','./'+rel),('canonical','b/'+rel),('foreign','b/wiki/models/Other.md')]:
    path=root/(ident+'.diff');make_diff(path,base,new,newpath=header)
    val=copy.deepcopy(rows);val[2]['claims'][0].update(diff=str(path),diff_hash=m.digest(path.read_bytes()))
    leg('M24-'+ident+' CR-153C-N9 header equivalence',val,0,('manual' if ident=='foreign' else 'apply')+' GPT')
for ident, tier in [('double','"high"'),('single',"'high'"),('unquoted','high'),('same','"medium"'),('lower',"'low'"),('very-low','"very-low"'),('authoritative',"'authoritative'")]:
    path=root/('resolved-'+ident+'.diff');make_diff(path,base,base.replace('confidence: medium','confidence: '+tier))
    rc,out=run(rows,('--resolved',path))
    needle='no confidence lift:' if ident in ('same','lower','very-low') else 'confidence lift: read the page in full'
    check('M25-'+ident+' CR-153B-5 quoted lift',rc==0 and needle in out,f'merge_plan.py --vault VAULT --resolved DIFF · exit {rc}')
rc,out=run(rows,('--resolved',nodiff));check('M26 resolved prose rejected',rc==2 and 'PROBE FAILED:' in out)
rc,out=run(rows,('--resolved',root/'absent.diff'));check('M27 missing resolution',rc==2 and 'PROBE FAILED:' in out)

nov = copy.deepcopy(rows);nov[-1].pop('scores')
leg('M28 CR-153B-1 missing scores',nov,2,'PROBE FAILED:')
nov[-1]['scores']=scores.replace(' claims 0','')
leg('M29 CR-153B-1 incomplete scores',nov,2,'PROBE FAILED:')
nov[-1]['scores']=scores.replace('claims 0','claims 1')
leg('M30 CR-153B-1 unnamed quarantine',nov,2,'PROBE FAILED:')
twins=copy.deepcopy(rows); second=copy.deepcopy(claim); second.update(source='two.md',**{'from':'two-page'})
twins[2]['claims'].append(second); twins[-1]['scores']=scores.replace('fab 0','fab 2').replace('claims 0','claims 2')
ref1={'name':'GPT','source':'one.md'};ref2={'name':'GPT','source':'two.md'}
twins[-1]['quarantined']=[ref1,ref1]
leg('M31 CR-153B-1 duplicate object',twins,2,'claim object named twice')
twins[-1]['quarantined']=[ref1,ref2]
leg('M32 CR-153B-1 distinct objects',twins,0,'quarantined GPT')
twins[-1]['quarantined']=[ref1];twins[-1]['scores']=scores.replace('claims 0','claims 1')
out=leg('M33 per-object quarantine keeps sibling',twins,0,'apply GPT')
check('M34 per-object retained count', 'objects 1' in out and 'quarantined objects 1' in out)
twins[-1]['quarantined']=[];twins[-1]['scores']=scores
leg('M35 no quarantine retains both',twins,0,'objects 2')
twins[-1]['quarantined']=['GPT'];twins[-1]['scores']=scores.replace('claims 0','claims 1')
leg('M36 ambiguous quarantine name',twins,2,'absent or ambiguous')
qfile=root/'quarantine.json';qfile.write_text(json.dumps([ref1,ref1]))
leg('M37 register duplicate quarantine file',rows,2,'claim object named twice',('--quarantine',qfile))
qfile.write_text(json.dumps([ref1]))
leg('M38 register unique quarantine file',rows,0,'quarantined GPT',('--quarantine',qfile))
for ident,value,code in [('object',{},2),('list',[],0),('null',None,2),('string','bad',2)]:
    qfile.write_text(json.dumps(value))
    leg('M39-'+ident+' CR-153C-N2 quarantine container',rows,code,'PROBE FAILED:' if code else 'apply GPT',('--quarantine',qfile))
for ident,value,code in [('object',{},2),('strings',['bad'],2),('empty',[],0),('null',None,2)]:
    val=copy.deepcopy(rows);val[2]['claims']=value
    leg('M40-'+ident+' CR-153C-N2 claim container',val,code,'PROBE FAILED:' if code else 'targets 0')
save(rows);ledger.write_text(ledger.read_text()+'{torn\n')
otherdir=root/'other';otherdir.mkdir();otherledger=otherdir/'ledger.jsonl';save([event('run_open',0,inbox=[])],otherledger);otherledger.write_text(otherledger.read_text()+'{torn\n')
rc,out=run(extra=('--allow-malformed',str(ledger)+':6','--ledger',otherledger))
check('M41 CR-153B-1 real-path approval isolates files',rc==2 and str(otherledger)+':2 · unsettled' in out,f'--allow-malformed LEDGER:6 --ledger OTHER/ledger.jsonl · exit {rc}')
rc,out=run(extra=('--allow-malformed',str(ledger)+':6','--ledger',otherledger,'--allow-malformed',str(otherledger)+':2'))
check('M42 CR-153B-1 exact-file approvals',rc==0 and 'apply GPT' in out,f'exit {rc}')
rc,out=run(extra=('--allow-malformed','ledger.jsonl:6'));check('M43 basename approval settles nothing',rc==2 and 'settles nothing' in out)
rc,out=run(extra=('--allow-malformed',str(ledger)+':6'));check('M44 named file approval',rc==0 and 'apply GPT' in out)
collision_rows=[event('run_open',0,inbox=[])]+[event('note',i,note='collision fixture') for i in range(1,5)]
save(collision_rows,otherledger);otherledger.write_text(otherledger.read_text()+'{torn\n')
check('F6a same-basename same-line premise',ledger.name==otherledger.name and ledger.read_text().splitlines()[5]=='{torn' and otherledger.read_text().splitlines()[5]=='{torn')
rc,out=run(extra=('--allow-malformed',str(ledger)+':6','--ledger',otherledger))
check('F6b line-six approval remains file-scoped',rc==2 and str(otherledger.resolve())+':6 · unsettled' in out,'--ledger OTHER/ledger.jsonl --allow-malformed LEDGER:6 · exit '+str(rc))
rc,out=run(extra=('--allow-malformed',str(ledger)+':6','--ledger',otherledger,'--allow-malformed',str(otherledger)+':6'))
check('F6c both exact line-six approvals pass',rc==0 and 'apply GPT' in out,'--allow-malformed LEDGER:6 --allow-malformed OTHER/ledger.jsonl:6 · exit '+str(rc))
save(rows)

later=copy.deepcopy(rows)+[event('lane_open',10,'LB',role='compile')]
leg('M45 CR-153C-N1 expected lane only open',later,2,'LB',('--lanes','LA,LB'))
leg('M46 CR-153C-N1 role discovers lane',later,2,'LB')
complete=copy.deepcopy(rows)+cycle('LB',9,[])
leg('M47 CR-153C-N1 empty completed lane',complete,0,'apply GPT')
reopened=copy.deepcopy(complete)+[event('lane_open',14,'LB',role='compile')]
leg('M48 CR-153C-N1 repeated open',reopened,2,'latest lane_close')
reclosed=reopened+[event('lane_close',15,'LB')]
leg('M49 CR-153C-N1 repeated close without verify',reclosed,2,'latest lane_close')
leg('M50 CR-153C-N1 completed second lifecycle',reclosed+[event('verify',16,'LB',scores=scores,quarantined=[])],0,'apply GPT')
closed_again=copy.deepcopy(rows)+[event('lane_close',5,'LA')]
leg('F4a close-verify-close leaves lane unverified',closed_again,2,'latest lane_close: LA')
leg('F4b verify after final close passes',closed_again+[event('verify',6,'LA',scores=scores,quarantined=[])],0,'apply GPT')
leg('F4c single close then verify still passes',rows,0,'apply GPT')
foreign=copy.deepcopy(rows);foreign[-1]['run']='foreign';foreign[-2]['run']='foreign'
leg('M51 CR-153C-N3 foreign verify',foreign,2,'foreign or unbound')
premature=copy.deepcopy(rows);premature[2],premature[4]=premature[4],premature[2]
leg('M52 CR-153C-N3 premature verify',premature,2,'PROBE FAILED:')
late=copy.deepcopy(rows)+[event('checkpoint',5,'LA',stage='claims_emitted',claims=[copy.deepcopy(claim)])]
leg('M53 CR-153C-N3 late claim',late,2,'claim ordering cannot establish coverage')
runless=copy.deepcopy(rows)
for e in runless[1:]:e.pop('run')
leg('M54 CR-153C-N3 runless bound by own file',runless,0,'apply GPT')
leg('M55 CR-153C-N3 ordered same-run',rows,0,'apply GPT')
claimsfile=root/'claims.jsonl';save([copy.deepcopy(rows[2])],claimsfile)
mainrows=copy.deepcopy(rows);mainrows.pop(2)
leg('M56 CR-153C-N10 separate ordered claims',mainrows,0,'apply GPT',('--ledger',claimsfile))
separate=copy.deepcopy(rows[2]);separate['ts']='2026-01-01T10:05:00+00:00';save([separate],claimsfile)
leg('M57 CR-153C-N10 late separate claim',mainrows,2,'claim ordering cannot establish coverage',('--ledger',claimsfile))
separate=copy.deepcopy(rows[2]);separate['run']='foreign';save([separate],claimsfile)
leg('M58 CR-153C-N10 foreign separate claim',mainrows,2,'foreign or unbound',('--ledger',claimsfile))
separate=copy.deepcopy(rows[2]);separate.pop('ts');save([separate],claimsfile)
leg('M59 CR-153C-N10 unordered separate claim',mainrows,2,'claim ordering cannot establish coverage',('--ledger',claimsfile))
separate=copy.deepcopy(rows[2]);separate.pop('run');save([separate],claimsfile)
leg('M60 separate runless file unbound',mainrows,2,'foreign or unbound',('--ledger',claimsfile))
minus=copy.deepcopy(rows);minus[-1]['scores']=scores.replace('fab 0 ','fab 0 plant 0 ')
leg('M61 a retired nine-name line with its plant score is refused',minus,2,'verify needs all eight score names')
minus[-1]['scores']=scores.replace('claims 0','claims -')
leg('M62 unscored claims',minus,2,'unscored claims')

create_text='---\ntitle: New Model\ntype: model\nconfidence: low\naliases: [NM, New Model]\n---\n# New Model\n## Definition\nDefinition.\n## Key Points\nDetails.\n## Appears in\n## Related\n'
create_diff=root/'create.diff';make_diff(create_diff,'',create_text,oldpath='/dev/null',newpath='b/wiki/models/New Model.md')
create_claim=copy.deepcopy(claim);create_claim.update(name='New Model',target='New Model',kind='create',diff=str(create_diff),diff_hash=m.digest(create_diff.read_bytes()),base=None,confidence='low')
creates=[event('run_open',0,inbox=[])]+cycle(claims=[create_claim])
create_out=leg('M64 absent create applies',creates,0,'apply New Model')
check('M64a create list carries diff aliases', '"NM"' in create_out)
(vault/'wiki/models/New Model.md').write_text(create_text)
leg('M65 existing create manual',creates,0,'manual New Model');(vault/'wiki/models/New Model.md').unlink()
aliasdiff=root/'alias-create.diff';make_diff(aliasdiff,'',create_text.replace('title: New Model','title: NM'),oldpath='/dev/null',newpath='b/wiki/models/NM.md')
otherclaim=copy.deepcopy(create_claim);otherclaim.update(name='NM',target='NM',diff=str(aliasdiff),diff_hash=m.digest(aliasdiff.read_bytes()))
leg('M66 create aliases join',creates+cycle('LB',claims=[otherclaim]),0,'conflict New Model')

reject=root/'rejects.txt'
cmd=shlex.split(m.patch_command(vault,target,diff,reject))
p=subprocess.run(cmd,text=True,capture_output=True)
if p.stderr:print(p.stderr,end='')
check('M67 patch flags dry-run',p.returncode==0, ' '.join(cmd)+f' · exit {p.returncode}')
check('M68 dry-run leaves page',target.read_text()==base)
p=subprocess.run(shlex.split(m.patch_command(vault,target,diff,reject,False)),text=True,capture_output=True)
if p.stderr:print(p.stderr,end='')
check('M69 patch byte equality',p.returncode==0 and target.read_text()==new,f'exit {p.returncode}')
p=subprocess.run(shlex.split(m.patch_command(vault,target,diff,reject,False)),text=True,capture_output=True)
if p.stderr:print(p.stderr,end='')
check('M70 repeated patch is failure',p.returncode!=0,f'exit {p.returncode}')
check('M71 no backups or rejects beside page',sorted(x.name for x in target.parent.iterdir())==['GPT.md'])
check('M72 reject positive control',reject.exists())
target.write_text(base)

fence_path=here.parent/'delegate/lane-fence.py'
if fence_path.is_file():
    fence_spec=importlib.util.spec_from_file_location('planner_fence_fixture',fence_path)
    fence=importlib.util.module_from_spec(fence_spec);fence_spec.loader.exec_module(fence)
    for label,dry in [('dry',True),('real',False)]:
        command=m.patch_command(vault,target,diff,reject,dry)
        event_input={'tool_name':'Bash','tool_input':{'command':command}}
        answer=fence.check(event_input,[str(root.resolve())],[str(root.resolve())],head=True)
        check('FENCE-'+label+' exact head patch command',answer==('silent',''),f'check(head=True) · {answer}')
        denied=fence.check(event_input,[],[],head=True)
        check('FENCE-'+label+' missing-grant control',denied[0]=='deny',f'check(head=True, grants=[]) · {denied[0]}')
else:
    check('FENCE-module required',False,'missing '+str(fence_path))

skill=(here/'SKILL.md').read_text();compile_template=(here.parent/'delegate/templates/brief-compile.md').read_text()
check('M73 CR-153-6 meter join key contract','same lane id' in compile_template and 'role: compile' in compile_template)
check('M74 CR-153-6 mismatched join key control','lane id must equal' in skill and 'same lane id' not in compile_template.replace('same lane id','different lane identifiers'))
check('M75 anchored apply contract','--dry-run' in skill and 'zero fuzz' in skill.casefold() and 'immediately before' in skill)
check('M76 resolved lift contract','--resolved' in skill and 'confidence lift' in skill)

# Part 7 adds its union cases here, before the final no-write proof.
uniondir=root/'unions';uniondir.mkdir()
link=lambda name,gloss='': '- ' + '['*2 + name + ']'*2 + ((' — '+gloss) if gloss else '') + '\n'

def union_rows(first,second,heading='## Appears in',raise_tier=False):
    result=[event('run_open',0,inbox=[])]
    for lane,text in [('LA',first),('LB',second)]:
        changed=base.replace(heading+'\n',heading+'\n'+text)
        if raise_tier and lane=='LB':changed=changed.replace('confidence: medium','confidence: "high"')
        path=root/(lane+'-links.diff');make_diff(path,base,changed)
        c=copy.deepcopy(claim);c.update(diff=str(path),diff_hash=m.digest(path.read_bytes()))
        result+=cycle(lane,claims=[c])
    return result

urows=union_rows(link('source-a'),link('source-b'))
out=leg('U01 links union',urows,0,'apply-union GPT',('--union-dir',uniondir))
artifacts=list(uniondir.glob('*.diff'))
check('U02 one artefact',len(artifacts)==1)
unionfile=artifacts[0] if artifacts else root/'absent-union.diff'
before_target=target.read_bytes()
p=subprocess.run(shlex.split(m.patch_command(vault,target,unionfile,root/'union.rej')),text=True,capture_output=True)
check('U03 union dry-run',p.returncode==0,f'patch -F0 --dry-run TARGET UNION · exit {p.returncode}')
p=subprocess.run(shlex.split(m.patch_command(vault,target,unionfile,root/'union.rej',False)),text=True,capture_output=True)
check('U04 union patch and unique lines',p.returncode==0 and target.read_text().count(link('source-a'))==1 and target.read_text().count(link('source-b'))==1,f'patch -F0 TARGET UNION · exit {p.returncode}')
check('U05 lane order',target.read_text().index('source-a')<target.read_text().index('source-b'))
target.write_bytes(before_target)
leg('U06 same-heading prose conflicts',union_rows('Prose A.\n','Prose B.\n','## Key Points'),0,'conflict GPT',('--union-dir',uniondir))
disjoint=union_rows('Prose A.\n','Prose B.\n','## Key Points')
bpath=root/'disjoint.diff';make_diff(bpath,base,base.replace('## Related\n','## Related\nProse B.\n'))
disjoint[6]['claims'][0].update(diff=str(bpath),diff_hash=m.digest(bpath.read_bytes()))
leg('U07 heading-disjoint prose conflicts',disjoint,0,'conflict GPT',('--union-dir',uniondir))
leg('U08 member confidence lift',union_rows(link('source-a'),link('source-b'),raise_tier=True),0,'tier-raised GPT',('--union-dir',uniondir))
same=union_rows(link('source-a'),link('source-a'))
out=leg('U09 identical links union',same,0,'apply-union GPT',('--union-dir',uniondir))
fname=next((x.split(' · ',1)[0][len('union diff: '):] for x in out.splitlines() if x.startswith('union diff: ')),None)
check('U10 identical link once',fname is not None and Path(fname).read_text().count('+'+link('source-a'))==1)
gloss=union_rows(link('source-a','first account'),link('source-a','second account'))
out=leg('U11 different glosses survive',gloss,0,'apply-union GPT',('--union-dir',uniondir))
fname=next((x.split(' · ',1)[0][len('union diff: '):] for x in out.splitlines() if x.startswith('union diff: ')),None)
check('U12 whole-line de-duplication',fname is not None and all(x in Path(fname).read_text() for x in ['first account','second account']))
normal=union_rows(link('source-a','Same Gloss'),link('source-a','Same  Gloss').rstrip('\n')+' \t\n')
out=leg('U13 normalised whole-line duplicates',normal,0,'apply-union GPT',('--union-dir',uniondir))
fname=next((x.split(' · ',1)[0][len('union diff: '):] for x in out.splitlines() if x.startswith('union diff: ')),None)
check('U14 normalised duplicate once',fname is not None and sum(x.startswith('+- ') for x in Path(fname).read_text().splitlines())==1)

for ident,first,second in [('comparison',link('A','effect > 0'),link('A','effect < 0')),('sign',link('A','effect +5'),link('A','effect -5')),('boundary',link('A','BC'),link('AB','C')),('case',link('A','Same Gloss'),link('A','same gloss'))]:
    out=leg('F2a-'+ident+' distinct link lines union',union_rows(first,second),0,'apply-union GPT',('--union-dir',uniondir))
    path=next((line.split(' · ',1)[0][len('union diff: '):] for line in out.splitlines() if line.startswith('union diff: ')),None)
    patch_text=Path(path).read_text() if path else ''
    check('F2b-'+ident+' both target and gloss lines survive',('+'+first) in patch_text and ('+'+second) in patch_text)
    if path:
        result=subprocess.run(shlex.split(m.patch_command(vault,target,Path(path),root/'distinct-links.rej',False)),text=True,capture_output=True)
        if result.stderr:print(result.stderr,end='')
        check('F2c-'+ident+' native patch keeps both lines',result.returncode==0 and first in target.read_text() and second in target.read_text(),'patch -F0 TARGET UNION · exit '+str(result.returncode))
        target.write_text(base)

urows=union_rows(link('source-a'),link('source-b'))
target.write_text(base.replace('## Appears in\n','## Citations\n'))
leg('U15 re-base fails manual',urows,0,'manual GPT',('--union-dir',uniondir))
target.write_text(base)
leg('U16 missing union scratch',urows,2,'--union-dir is required')
leg('U17 nonexistent union directory',urows,2,'existing scratch',('--union-dir',root/'absent-dir'))
leg('U18 vault cannot be union scratch',urows,2,'outside the vault',('--union-dir',vault))
out=leg('U19 Related links union',union_rows(link('source-a'),link('source-b'),'## Related'),0,'apply-union GPT',('--union-dir',uniondir))
# 2026-09-22 (№172): the Key Points fixtures add after the paragraph, as a compile lane appends;
# a bullet directly above it takes the paragraph in as a lazy line (CommonMark), so U20c is manual.
out=leg('U20 list lines under Key Points union (rule widened 2026-09-21)',union_rows(link('source-a'),link('source-b'),'Original.'),0,'apply-union GPT',('--union-dir',uniondir))
out=leg('U20c a bullet directly above a Key Points paragraph takes it in as a lazy line: manual',union_rows(link('source-a'),link('source-b'),'## Key Points'),0,'manual GPT',('--union-dir',uniondir))
check('U20d the refusal names the added item and the paragraph it takes in','union placement refused: list item at member LA added line' in out and "takes existing line" in out and "'Original.'" in out and 'patch -F0' not in out)
out=leg('U20b links under a non-list heading conflict',union_rows(link('source-a'),link('source-b'),'# GPT'),0,'conflict GPT',('--union-dir',uniondir))
# The Appears-in idiom, date stamps, superset lists, bullets and removals.
row=lambda variant,name,gloss: '- '+variant+' → '+'['*2+name+']'*2+' — '+gloss+'\n'
out=leg('U28 Appears-in rows without a leading link union',union_rows(row('Qwen3-8B','source-a','base model'),row('Qwen2-7B','source-b','reward model')),0,'apply-union GPT',('--union-dir',uniondir))
fname=next((x.split(' · ',1)[0][len('union diff: '):] for x in out.splitlines() if x.startswith('union diff: ')),None)
check('U28b both rows in the union',fname is not None and all(('+'+r) in Path(fname).read_text() for r in (row('Qwen3-8B','source-a','base model'),row('Qwen2-7B','source-b','reward model'))))
def stamped_rows(first,second,stamp_a='audited: 2026-01-02',stamp_b='audited: 2026-01-03',heading='## Appears in'):
    result=[event('run_open',0,inbox=[])]
    for lane,text,stamp in [('LA',first,stamp_a),('LB',second,stamp_b)]:
        changed=base.replace(heading+'\n',heading+'\n'+text)
        if stamp: changed=changed.replace('confidence: medium\n','confidence: medium\n'+stamp+'\n') if 'audited:' not in base else changed
        path=root/(lane+'-stamped.diff');make_diff(path,base,changed)
        c=copy.deepcopy(claim);c.update(diff=str(path),diff_hash=m.digest(path.read_bytes()))
        result+=cycle(lane,claims=[c])
    return result
out=leg('U29 date stamps added by both lanes still union',stamped_rows(link('source-a'),link('source-b')),0,'apply-union GPT',('--union-dir',uniondir))
fname=next((x.split(' · ',1)[0][len('union diff: '):] for x in out.splitlines() if x.startswith('union diff: ')),None)
utext=Path(fname).read_text() if fname else ''
check('U29b one stamp, the later date, both links',utext.count('+audited: ')==1 and '+audited: 2026-01-03' in utext and ('+'+link('source-a')) in utext and ('+'+link('source-b')) in utext)
if fname:
    p=subprocess.run(shlex.split(m.patch_command(vault,target,Path(fname),root/'stamped.rej',False)),text=True,capture_output=True)
    check('U29c stamped union applies with patch -F0',p.returncode==0 and target.read_text().count('audited: 2026-01-03')==1,f'exit {p.returncode}')
    target.write_text(base)
dated=base.replace('confidence: medium\n','confidence: medium\naudited: 2026-01-01\nupdated: 2026-01-01\n')
target.write_text(dated)
def redated_rows(first,second):
    result=[event('run_open',0,inbox=[])]
    for lane,text in [('LA',first),('LB',second)]:
        changed=dated.replace('## Appears in\n','## Appears in\n'+text).replace('audited: 2026-01-01','audited: 2026-01-05').replace('updated: 2026-01-01','updated: 2026-01-05')
        path=root/(lane+'-redated.diff');make_diff(path,dated,changed)
        c=copy.deepcopy(claim);c.update(base=m.digest(dated.encode()),diff=str(path),diff_hash=m.digest(path.read_bytes()))
        result+=cycle(lane,claims=[c])
    return result
out=leg('U30 re-dated stamps (a - line per stamp) still union',redated_rows(link('source-a'),link('source-b')),0,'apply-union GPT',('--union-dir',uniondir))
fname=next((x.split(' · ',1)[0][len('union diff: '):] for x in out.splitlines() if x.startswith('union diff: ')),None)
utext=Path(fname).read_text() if fname else ''
check('U30b stamps re-dated once each',utext.count('+audited: 2026-01-05')==1 and utext.count('+updated: 2026-01-05')==1 and utext.count('-audited: 2026-01-01')==1)
listed=dated.replace('aliases: [GPT-4o]\n','aliases: [GPT-4o]\nsources: [raw/a.md]\n')
target.write_text(listed)
def listed_rows(first,second,add_a='raw/b.md',add_b='raw/c.md'):
    result=[event('run_open',0,inbox=[])]
    for lane,text,add in [('LA',first,add_a),('LB',second,add_b)]:
        changed=listed.replace('## Appears in\n','## Appears in\n'+text).replace('sources: [raw/a.md]','sources: [raw/a.md, '+add+']')
        path=root/(lane+'-listed.diff');make_diff(path,listed,changed)
        c=copy.deepcopy(claim);c.update(base=m.digest(listed.encode()),diff=str(path),diff_hash=m.digest(path.read_bytes()))
        result+=cycle(lane,claims=[c])
    return result
out=leg('U31 sources appended by both lanes merge into one list',listed_rows(link('source-a'),link('source-b')),0,'apply-union GPT',('--union-dir',uniondir))
fname=next((x.split(' · ',1)[0][len('union diff: '):] for x in out.splitlines() if x.startswith('union diff: ')),None)
utext=Path(fname).read_text() if fname else ''
check('U31b merged list keeps the original order and both appends','+sources: [raw/a.md, raw/b.md, raw/c.md]' in utext and utext.count('+sources:')==1)
if fname:
    p=subprocess.run(shlex.split(m.patch_command(vault,target,Path(fname),root/'listed.rej',False)),text=True,capture_output=True)
    check('U31c list union applies with patch -F0',p.returncode==0 and 'sources: [raw/a.md, raw/b.md, raw/c.md]' in target.read_text(),f'exit {p.returncode}')
    target.write_text(listed)
shrunk=listed_rows(link('source-a'),link('source-b'),add_a='raw/b.md',add_b='raw/c.md')
bpath=root/'shrunk.diff';make_diff(bpath,listed,listed.replace('## Appears in\n','## Appears in\n'+link('source-b')).replace('sources: [raw/a.md]','sources: [raw/c.md]'))
shrunk[6]['claims'][0].update(diff=str(bpath),diff_hash=m.digest(bpath.read_bytes()))
leg('U32 a sources list that drops an item conflicts',shrunk,0,'conflict GPT',('--union-dir',uniondir))
quoted=listed.replace('aliases: [GPT-4o]','aliases: ["GPT-4, turbo", GPT-4o]')
target.write_text(quoted)
def quoted_rows():
    result=[event('run_open',0,inbox=[])]
    for lane,add in [('LA', '[' * 2 + 'source-a' + ']' * 2), ('LB', '[' * 2 + 'source-b' + ']' * 2)]:
        changed=quoted.replace('## Appears in\n','## Appears in\n- '+add+'\n').replace('aliases: ["GPT-4, turbo", GPT-4o]','aliases: ["GPT-4, turbo", GPT-4o, '+lane+'-alias]')
        path=root/(lane+'-quoted.diff');make_diff(path,quoted,changed)
        c=copy.deepcopy(claim);c.update(base=m.digest(quoted.encode()),diff=str(path),diff_hash=m.digest(path.read_bytes()))
        result+=cycle(lane,claims=[c])
    return result
out=leg('U32b a quoted alias with a comma survives an aliases merge',quoted_rows(),0,'apply-union GPT',('--union-dir',uniondir))
fname=next((x.split(' · ',1)[0][len('union diff: '):] for x in out.splitlines() if x.startswith('union diff: ')),None)
check('U32c merged aliases keep the quoted item whole',fname is not None and '+aliases: ["GPT-4, turbo", GPT-4o, LA-alias, LB-alias]' in Path(fname).read_text())
target.write_text(listed)
other=listed_rows(link('source-a'),link('source-b'))
bpath=root/'tags.diff';make_diff(bpath,listed,listed.replace('## Appears in\n','## Appears in\n'+link('source-b')).replace('type: model','type: benchmark'))
other[6]['claims'][0].update(diff=str(bpath),diff_hash=m.digest(bpath.read_bytes()))
leg('U33 any other frontmatter change conflicts',other,0,'conflict GPT',('--union-dir',uniondir))
target.write_text(base)
out=leg('U34 Key Points bullets from two lanes union',union_rows('- **Fact A.** one source.\n','- **Fact B.** another source.\n','Original.'),0,'apply-union GPT',('--union-dir',uniondir))
fname=next((x.split(' · ',1)[0][len('union diff: '):] for x in out.splitlines() if x.startswith('union diff: ')),None)
check('U34b both bullets kept',fname is not None and all(x in Path(fname).read_text() for x in ['+- **Fact A.**','+- **Fact B.**']))
leg('U35 a bullet beside bare prose conflicts',union_rows('- **Fact A.** one source.\n','Prose B.\n','Original.'),0,'conflict GPT',('--union-dir',uniondir))
removing=union_rows(link('source-a'),link('source-b'))
bpath=root/'removing.diff';make_diff(bpath,base,base.replace('## Appears in\n','## Appears in\n'+link('source-b')).replace('Original.\n',''))
removing[6]['claims'][0].update(diff=str(bpath),diff_hash=m.digest(bpath.read_bytes()))
leg('U36 a removed body line conflicts',removing,0,'conflict GPT',('--union-dir',uniondir))
flagged=copy.deepcopy(rows);flagged[-1]['flagged_facts']=[{'name':'GPT','lane':'LA','fact':'a refuted vault-state count','fix':'sentence rewritten by the head'}]
leg('U37 flagged_facts beside claims 0 is accepted',flagged,0,'apply GPT')
shaped=copy.deepcopy(rows);shaped[-1]['shape']='fail'
out=leg('U37b shape: fail is a printed note, not a probe failure',shaped,0,'apply GPT')
check('U37c the note names the lane','note: LA · the verifier recorded a claims-shape evidence failure' in out)
check('U40 skill text carries the widened union rule','list items (lines beginning `- `) under `## Appears in`, `## Related`, `## Key Points` or `## Conflicts / Open Questions`' in skill and 'link lines under `## Appears in` or `## Related`' not in skill)
check('U41 skill text carries flagged_facts and shape: fail','flagged_facts' in skill and 'shape: fail' in skill)
verify_template=(here.parent/'delegate/templates/brief-ingest-verify.md').read_text()
check('U42 verify template no longer scores a shape failure as claims 1','scores `claims 1`' not in verify_template and 'shape: fail' in verify_template and 'scores `claims 1`' not in compile_template)
counted=copy.deepcopy(rows);counted[-1]['scores']=scores.replace('claims 0','claims 1')
leg('U38 claims 1 with no object still fails closed',counted,2,'claims count differs')
scoped=copy.deepcopy(rows);scoped[-1]['scores']=scores.replace('claims 0','claims 1');scoped[-1]['quarantined']=[{'name':'GPT','lane':'LA','scope':'fact 5 only'}]
leg('U39 a scope field on a quarantine object still fails closed',scoped,2,'unknown quarantine selector field')
# CR-PLANNER round 1 (2026-09-21): the composition, list, stamp, gate and coverage findings, each with a must-fire and a must-not-fire side.
def two_lane_rows(page,changes,names=('LA','LB'),context=3):
    # changes: per lane a function page -> changed page; the target is written to `page` first
    target.write_text(page)
    result=[event('run_open',0,inbox=[])]
    for lane,fn in zip(names,changes):
        path=root/(lane+'-cr.diff');make_diff(path,page,fn(page),context=context)
        c=copy.deepcopy(claim);c.update(base=m.digest(page.encode()),diff=str(path),diff_hash=m.digest(path.read_bytes()))
        result+=cycle(lane,claims=[c])
    return result
def union_text(out):
    fname=next((x.split(' · ',1)[0][len('union diff: '):] for x in out.splitlines() if x.startswith('union diff: ')),None)
    return Path(fname).read_text() if fname else ''
subpage=base.replace('## Key Points\nOriginal.\n','## Key Points\n- parent one\n\n### Rejected claims\n- rejected one\n')
out=leg('C01 parent bullets union above a ### sub-heading',two_lane_rows(subpage,[lambda t:t.replace('- parent one\n','- parent one\n- parent two\n'),lambda t:t.replace('- parent one\n','- parent one\n- parent three\n')]),0,'apply-union GPT',('--union-dir',uniondir))
ut=union_text(out)
check('C01b the new bullets sit before the sub-heading',ut.index('+- parent two')<ut.index('### Rejected claims') if '+- parent two' in ut and '### Rejected claims' in ut else False)
leg('C02 a bullet added under the ### sub-heading conflicts',two_lane_rows(subpage,[lambda t:t.replace('- rejected one\n','- rejected one\n- rejected two\n'),lambda t:t.replace('- parent one\n','- parent one\n- parent three\n')]),0,'conflict GPT',('--union-dir',uniondir))
fencepage=base.replace('## Key Points\nOriginal.\n','## Key Points\n- real one\n\n```\n- example one\n```\n')
leg('C03 a fenced page requires a hand read',two_lane_rows(fencepage,[lambda t:t.replace('- example one\n','- example one\n- example two\n'),lambda t:t.replace('- real one\n','- real one\n- real two\n')]),0,'manual GPT',('--union-dir',uniondir))
# 2026-09-22 (№172): the parser places the fence, so a real bullet beside it unions and T13's
# de-duplication no longer swallows a bullet that shares a fenced line's text.
out=leg('C04 a real bullet beside fenced text unions: the parser places the fence',two_lane_rows(fencepage,[lambda t:t.replace('- real one\n','- real one\n- example one\n'),lambda t:t.replace('- real one\n','- real one\n- real two\n')]),0,'apply-union GPT',('--union-dir',uniondir))
composed=m.apply_memory(fencepage,m.parse_diff(union_text(out),vault.resolve())) if union_text(out) else ''
check('C04b both bullets join the list above the fence, whose example stays code',composed.count('- example one\n')==2 and independent_items(composed,['- example one','- real two'],'Key Points') and independent_code(composed,'- example one'))
quoted2=base.replace('aliases: [GPT-4o]\n','aliases: ["GPT", "Foo, shared"]\n')
out=leg('C05 quoted items with commas at later positions merge whole',two_lane_rows(quoted2,[lambda t:t.replace('aliases: ["GPT", "Foo, shared"]','aliases: ["GPT", "Foo, shared", "Bar, shared"]').replace('## Appears in\n','## Appears in\n'+link('source-a')),lambda t:t.replace('aliases: ["GPT", "Foo, shared"]','aliases: ["GPT", "Foo, shared", "Baz, shared"]').replace('## Appears in\n','## Appears in\n'+link('source-b'))]),0,'apply-union GPT',('--union-dir',uniondir))
check('C05b the merged list is intact','+aliases: ["GPT", "Foo, shared", "Bar, shared", "Baz, shared"]' in union_text(out))
mixed=base.replace('confidence: medium\n','confidence: medium\naudited: 2026-09-20\n')
out=leg('C06 a missing updated: beside an existing audited: composes one row each',two_lane_rows(mixed,[lambda t:t.replace('audited: 2026-09-20','audited: 2026-09-22').replace('aliases: [GPT-4o]\n','aliases: [GPT-4o]\nupdated: 2026-09-22\n').replace('## Appears in\n','## Appears in\n'+link('source-a')),lambda t:t.replace('## Appears in\n','## Appears in\n'+link('source-b'))]),0,'apply-union GPT',('--union-dir',uniondir))
ut=union_text(out)
if ut:
    p=subprocess.run(shlex.split(m.patch_command(vault,target,Path(next(x.split(' · ',1)[0][len('union diff: '):] for x in out.splitlines() if x.startswith('union diff: '))),root/'mixed.rej',False)),text=True,capture_output=True)
    page_now=target.read_text()
    check('C06b one audited row at the later date and one updated row',p.returncode==0 and page_now.count('audited:')==1 and 'audited: 2026-09-22' in page_now and page_now.count('updated:')==1 and 'updated: 2026-09-22' in page_now,f'exit {p.returncode}')
    check('C06c the planner parser reads the later date',m.frontmatter(page_now).get('audited')=='2026-09-22')
    target.write_text(mixed)
leg('C07 a stamp removed without a replacement conflicts',two_lane_rows(mixed,[lambda t:t.replace('audited: 2026-09-20\n','').replace('## Appears in\n','## Appears in\n'+link('source-a')),lambda t:t.replace('## Appears in\n','## Appears in\n'+link('source-b'))]),0,'conflict GPT',('--union-dir',uniondir))
leg('C08 a sources: list added from nothing conflicts',two_lane_rows(base,[lambda t:t.replace('aliases: [GPT-4o]\n','aliases: [GPT-4o]\nsources: [raw/a.md]\n').replace('## Appears in\n','## Appears in\n'+link('source-a')),lambda t:t.replace('## Appears in\n','## Appears in\n'+link('source-b'))]),0,'conflict GPT',('--union-dir',uniondir))
leg('C09 an invalid stamp date conflicts',two_lane_rows(mixed,[lambda t:t.replace('audited: 2026-09-20','audited: 2026-99-99').replace('## Appears in\n','## Appears in\n'+link('source-a')),lambda t:t.replace('## Appears in\n','## Appears in\n'+link('source-b'))]),0,'conflict GPT',('--union-dir',uniondir))
out=leg('C10 a backdated stamp keeps the page date',two_lane_rows(mixed,[lambda t:t.replace('audited: 2026-09-20','audited: 2026-01-01').replace('## Appears in\n','## Appears in\n'+link('source-a')),lambda t:t.replace('## Appears in\n','## Appears in\n'+link('source-b'))]),0,'apply-union GPT',('--union-dir',uniondir))
check('C10b no audited change in the union','audited:' not in union_text(out).replace(' audited:',''))
conf=base.replace('## Appears in\n\n## Related\n','## Appears in\n\n## Conflicts / Open Questions\n- **Open one.** first.\n\n## Related\n')
out=leg('C11 conflict-block bullets from two lanes union',two_lane_rows(conf,[lambda t:t.replace('- **Open one.** first.\n','- **Open one.** first.\n- **Open two.** second.\n'),lambda t:t.replace('- **Open one.** first.\n','- **Open one.** first.\n- **Open three.** third.\n')]),0,'apply-union GPT',('--union-dir',uniondir))
check('C11b both open questions kept',all(x in union_text(out) for x in ['+- **Open two.**','+- **Open three.**']))
target.write_text(base)
lifted=union_rows(link('source-a'),link('source-b'))
for i in (2,6): lifted[i]['claims'][0]['confidence']='high'
out=leg('C12 a claim-field lift on a union-eligible target is held',lifted,0,'tier-raised GPT',('--union-dir',uniondir))
check('C12b the plan composes the union but prints no apply command for it','held until the full-page read:' in out and 'after the full-page read' in out and 'patch -F0' not in out)
heldfile=next((x.split(' · ')[1][len('union diff '):] for x in out.splitlines() if x.startswith('held until the full-page read:')),None)
rc2,out2=run(None,('--resolved',heldfile)) if heldfile else (1,'')
check('C13 --resolved on the held union prints the apply commands after the read',rc2==0 and 'no confidence lift' in out2 and out2.count('patch -F0')==2 and 'base recheck immediately before real patch: '+m.digest(base.encode()) in out2)
(vault/'wiki/models/Llama.md').write_text(base.replace('GPT','Llama').replace('aliases: [GPT-4o]','aliases: [Llama-3]'))
collide=two_lane_rows(base,[lambda t:t.replace('aliases: [GPT-4o]','aliases: [GPT-4o, Llama]').replace('## Appears in\n','## Appears in\n'+link('source-a')),lambda t:t.replace('## Appears in\n','## Appears in\n'+link('source-b'))])
leg('C14 an alias appended by an update that names an existing page is manual, never a union',collide,0,'manual GPT',('--union-dir',uniondir))
(vault/'wiki/models/Llama.md').unlink();target.write_text(base)
leg('C15 stamp-only members with no list item are not a union',two_lane_rows(mixed,[lambda t:t.replace('audited: 2026-09-20','audited: 2026-09-22'),lambda t:t.replace('audited: 2026-09-20','audited: 2026-09-23')]),0,'manual GPT',('--union-dir',uniondir))
target.write_text(base)
urows=union_rows(link('source-a'),link('source-b'))
before_artifacts={p.name:p.read_bytes() for p in uniondir.iterdir()}
leg('U21 identical rerun artefact',urows,0,'apply-union GPT',('--union-dir',uniondir))
check('U22 rerun has no extra writes',{p.name:p.read_bytes() for p in uniondir.iterdir()}==before_artifacts)
saved=unionfile.read_bytes();unionfile.write_text('collision control\n')
leg('U23 no silent overwrite',urows,2,'different bytes',('--union-dir',uniondir))
check('U24 collision artefact unchanged',unionfile.read_text()=='collision control\n');unionfile.write_bytes(saved)
hold=copy.deepcopy(urows);hold.pop()
before_artifacts={p.name:p.read_bytes() for p in uniondir.iterdir()}
out=leg('U25 incomplete verify emits no union',hold,2,'PROBE FAILED:',('--union-dir',uniondir))
check('U26 incomplete evidence no writes or patch',before_artifacts=={p.name:p.read_bytes() for p in uniondir.iterdir()} and 'patch -F0' not in out)
check('U27 union never changed source page',target.read_text()==base)

# Round-two regressions. Each refusal has a same-run accepting control; all
# fixture writes remain below the suite's mktemp directory.
def union_page(output, page):
    patch = union_text(output)
    return m.apply_memory(page, m.parse_diff(patch, vault.resolve())) if patch else ''

def resolution(paths, extra=()):
    args = [sys.executable, '-B', str(script), '--vault', str(vault)]
    for path in paths: args += ['--resolved', str(path)]
    proc = subprocess.run(args + list(extra), text=True, capture_output=True)
    if proc.stderr: print(proc.stderr, end='')
    return proc.returncode, proc.stdout

def release_args(output):
    line = next((line for line in output.splitlines() if line.startswith('held until the full-page read:') and ' · then: ' in line), '')
    return shlex.split(line.split(' · then: ', 1)[1])[1:] if line else []

def release(args):
    proc = subprocess.run([sys.executable, '-B', str(script), *args], text=True, capture_output=True)
    if proc.stderr: print(proc.stderr, end='')
    return proc.returncode, proc.stdout

for ident, marker in [('D01', '~~~'), ('D02', '````')]:
    page = base.replace('Original.\n', '- real\n' + marker + '\n```\n- example\n```\n' + marker + '\n')
    vals = two_lane_rows(page, [lambda t:t.replace('- example\n', '- example\n- inserted\n'), lambda t:t.replace('- real\n', '- real\n- ordinary\n')])
    rc, output = run(vals, ('--union-dir', uniondir))
    check(ident + ' N07/N08/N26 an addition inside a nested fence is refused with the fence named', rc == 0 and placed(output, 'fence', 'member LA added line'))
page = base.replace('Original.\n', '- real\n~~~\n```\n- example\n```\n~~~~\n')
rc, output = run(two_lane_rows(page, [lambda t:t.replace('- real\n', '- real\n- first\n'), lambda t:t.replace('- real\n', '- real\n- second\n')]), ('--union-dir', uniondir))
composed = union_page(output, page)
check('D03 ordinary additions beside a mixed fence union above it: the parser keeps its character and length', rc == 0 and 'apply-union GPT' in output and independent_items(composed, ['- first', '- second'], 'Key Points') and independent_code(composed, '- example'))
for width, parent_id, child_id in [(1, 'D04', 'D05'), (2, 'D06', 'D07'), (3, 'D08', 'D09')]:
    # CommonMark permits zero through three leading spaces on an ATX heading, but after a
    # list item and a blank line two or more make it that item's own heading, not a section.
    heading = ' ' * width + '### Rejected claims\n'
    for suffix, lead in ((('', '- parent one\n\n'), ('b', '- parent one\n\nClosing paragraph.\n')) if width > 1 else (('', '- parent one\n\n'),)):
        page = subpage.replace('- parent one\n\n### Rejected claims\n', lead + heading)
        held = width > 1 and not suffix
        rc, output = run(two_lane_rows(page, [lambda t:t.replace('- parent one\n', '- parent one\n- first\n'), lambda t:t.replace('- parent one\n', '- parent one\n- second\n')]), ('--union-dir', uniondir))
        composed = union_page(output, page)
        if held: check(parent_id + ' N09 an indented heading held by the item above it: an addition after that item would take it in', rc == 0 and placed(output, 'list item', 'Rejected claims'))
        else: check(parent_id + suffix + ' N09 parent bullets precede an indented subsection', rc == 0 and '- first\n' in composed and composed.index('- first\n') < composed.index(heading) and composed.index('- second\n') < composed.index(heading))
        rc, output = run(two_lane_rows(page, [lambda t:t.replace('- rejected one\n', '- rejected one\n- inserted\n'), lambda t:t.replace('- parent one\n', '- parent one\n- second\n')]), ('--union-dir', uniondir))
        if held: check(child_id + ' the item-held heading is no section: the parent addition beside it is refused', rc == 0 and placed(output, 'list item', 'member LB added line'))
        else: check(child_id + suffix + ' indented subsection additions cannot union', rc == 0 and 'conflict GPT' in output and 'patch -F0' not in output)
page = base.replace('Original.\n', '- real\n~~~\n## Related\n### Example\n- code\n~~~\n')
rc, output = run(two_lane_rows(page, [lambda t:t.replace('- real\n', '- real\n- first\n'), lambda t:t.replace('- real\n', '- real\n- second\n')]), ('--union-dir', uniondir))
composed = union_page(output, page)
check('D10 headings inside a fence are code, not sections: the additions union above it', rc == 0 and 'apply-union GPT' in output and independent_items(composed, ['- first', '- second'], 'Key Points') and independent_code(composed, '## Related'))

items = ['Foo "common, suffix"', 'Bar "common, suffix"', 'Baz "common, suffix"']
page = base.replace('[GPT-4o]', json.dumps(items[:1]))
vals = two_lane_rows(page, [lambda t:t.replace(json.dumps(items[:1]), json.dumps(items[:2])), lambda t:t.replace(json.dumps(items[:1]), json.dumps([items[0], items[2]]))])
rc, output = run(vals, ('--union-dir', uniondir))
composed = union_page(output, page)
try:
    alias_row = next(line for line in composed.splitlines() if line.startswith('aliases: '))
    decoded = json.loads(alias_row.split(': ', 1)[1])
except (StopIteration, ValueError): decoded = None
check('D11 N14/N27 escaped quotes preserve every complete alias independently', rc == 0 and 'apply-union GPT' in output and decoded == items)
try:
    parsed_items = m.list_items(', '.join(json.dumps(item) for item in items))
except (ValueError, AttributeError): parsed_items = None
check('D12 escaped comma fragments are never separate list items', parsed_items == [json.dumps(item) for item in items])
spellings = ['"first, item"', "'second \"nested, quote\"'", '"third\'s, item"', "'O''Brien, fourth'", "O'Brien"]
try:
    parsed_items = m.list_items(', '.join(spellings))
except (ValueError, AttributeError): parsed_items = None
check('D13 P10/P11/N12/N13 quoted positions and opposite or doubled quotes survive', parsed_items == spellings)
page = base.replace('[GPT-4o]', "[O'Brien]")
rc, output = run(two_lane_rows(page, [lambda t:t.replace("[O'Brien]", "[O'Brien, First]"), lambda t:t.replace("[O'Brien]", "[O'Brien, Second]")]), ('--union-dir', uniondir))
check('D14 N10 an apostrophe within a plain item unions', rc == 0 and 'apply-union GPT' in output and "+aliases: [O'Brien, First, Second]" in union_text(output))
for ident, inner in [('D15', 'plain, "unfinished'), ('D16', "plain, 'unfinished")]:
    try: m.list_items(inner); refused = False
    except (ValueError, AttributeError): refused = True
    check(ident + ' an unterminated quoted item is refused', refused)

# Inject the retired escape-blind splitter: an independent composition check
# must reject its malformed output even if that splitter accepts its own result.
def escape_blind(inner, strict=True):
    result, buf, quote = [], '', None
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote: quote = None
        elif ch in ('"', "'"): quote = ch; buf += ch
        elif ch == ',': result.append(buf.strip()); buf = ''
        else: buf += ch
    if quote: raise ValueError('unterminated fixture quote')
    return [item for item in result + [buf.strip()] if item]
page = base.replace('[GPT-4o]', json.dumps(items[:1]))
members = []
for lane, addition in zip(('LA', 'LB'), items[1:]):
    changed = page.replace(json.dumps(items[:1]), json.dumps([items[0], addition]))
    patch = ''.join(difflib.unified_diff(page.splitlines(True), changed.splitlines(True), fromfile=str(target), tofile=str(target)))
    members.append({'text':page, 'parsed':m.parse_diff(patch, vault.resolve()), 'problems':[], 'target':target, 'claim':{'lane':lane}, 'lift':False})
try:
    with mock.patch.object(m, 'list_items', escape_blind, create=True): m.compose_union(members)
    refused = False
except ValueError: refused = True
check('D17 composition independently refuses an escape-blind splitter', refused)
page = base.replace('[GPT-4o]', '[' + ', '.join(spellings[:-1]) + ']')
rc, output = run(two_lane_rows(page, [lambda t:t.replace("]\n---", ", First]\n---"), lambda t:t.replace("]\n---", ", Second]\n---")]), ('--union-dir', uniondir))
check('D18 supported single and double quoted forms still compose', rc == 0 and 'apply-union GPT' in output and all(item in union_text(output) for item in spellings[:-1]))

target.write_text(base)
rc, output = resolution([diff, nodiff])
check('D19 N21 a valid then invalid batch emits no patch commands', rc == 2 and 'PROBE FAILED:' in output and 'patch -F0' not in output)
rc, output = resolution([nodiff, diff])
check('D20 an invalid first resolution also suppresses the whole batch', rc == 2 and 'PROBE FAILED:' in output and 'patch -F0' not in output)
rc, output = resolution([diff, diff])
check('D21 unchanged valid resolutions release together', rc == 0 and output.count('patch -F0') == 4 and 'controls:' in output)
original_apply = m.apply_memory
def moved_after_read(old, parsed):
    changed = original_apply(old, parsed)
    target.write_text(drifted_title)
    return changed
captured = io.StringIO()
try:
    with mock.patch.object(m, 'apply_memory', moved_after_read), contextlib.redirect_stdout(captured):
        rc = m.main(['--vault', str(vault), '--resolved', str(diff)])
finally: target.write_text(base)
output = captured.getvalue()
check('D22 N22 a base changed after the resolution read fails closed', rc == 2 and 'base moved during planning' in output and 'patch -F0' not in output)
rc, output = resolution([diff])
check('D23 an unchanged resolved base retains its validated hash', rc == 0 and output.count('patch -F0') == 2 and claim['base'] in output)

lifted = union_rows(link('source-a'), link('source-b'))
for i in (2, 6): lifted[i]['claims'][0]['confidence'] = 'high'
rc, held = run(lifted, ('--union-dir', uniondir))
args = release_args(held)
released_rc, released = release(args) if args else (1, '')
check('D24 N18 the printed held-union release keeps both members', rc == released_rc == 0 and released.count('patch -F0') == 2 and all(name in union_text(held) for name in ('source-a', 'source-b')))
substituted = list(args)
if '--resolved' in substituted: substituted[substituted.index('--resolved') + 1] = lifted[2]['claims'][0]['diff']
rc, output = release(substituted) if substituted else (1, '')
check('D25 N20 replacing the held union with a member is refused', rc == 2 and 'hash' in output and 'held' in output and 'patch -F0' not in output)
held_path = Path(args[args.index('--resolved') + 1]) if '--resolved' in args else None
saved_union = held_path.read_bytes() if held_path else b''
try:
    if held_path: held_path.write_bytes(Path(lifted[2]['claims'][0]['diff']).read_bytes())
    rc, output = release(args) if args else (1, '')
finally:
    if held_path: held_path.write_bytes(saved_union)
check('D26 changed bytes at the held artefact path are refused', rc == 2 and 'hash' in output and 'patch -F0' not in output)
target.write_text(drifted_title)
rc, output = release(args) if args else (1, '')
target.write_text(base)
check('D27 a held release binds the page read to its original base', rc == 2 and 'base' in output and 'patch -F0' not in output)
rc, output = release(args) if args else (1, '')
check('D28 N19 unchanged held bytes and base release after refusals', rc == 0 and output.count('patch -F0') == 2 and 'controls:' in output)

rc, output = resolution([raised])
check('D29 N30 a resolution-introduced lift is held without commands', rc == 0 and 'confidence lift: read the page in full' in output and 'held until the full-page read:' in output and 'patch -F0' not in output)
read_args = release_args(output)
rc, output = release(read_args) if read_args else (1, '')
check('D30 the named second step releases the read confidence lift', rc == 0 and output.count('patch -F0') == 2)
changed_lift = root / 'changed-lift.diff'
make_diff(changed_lift, base, new.replace('confidence: medium', 'confidence: authoritative'))
substituted = list(read_args)
if '--resolved' in substituted: substituted[substituted.index('--resolved') + 1] = str(changed_lift)
rc, output = release(substituted) if substituted else (1, '')
check('D31 acknowledgement cannot release a different confidence lift', rc == 2 and 'patch -F0' not in output)
rc, output = resolution([root / 'resolved-lower.diff'])
check('D32 a non-raising resolution needs no extra read step', rc == 0 and 'held until' not in output and output.count('patch -F0') == 2)

other_page = vault / 'wiki/models/Other.md'
other_page.write_text(base.replace('GPT', 'Other').replace('aliases: [Other-4o]', 'aliases: [Other, "Foo, shared"]'))
vals = two_lane_rows(base, [lambda t:t.replace('[GPT-4o]', '[GPT-4o, "Foo, shared"]'), lambda t:t.replace('## Related\n', '## Related\n- ordinary\n')])
rc, output = run(vals, ('--union-dir', uniondir))
check('D33 N25 existing and appended quoted aliases collide consistently', rc == 0 and 'manual GPT' in output and 'multiple existing pages' in output and 'patch -F0' not in output)
page = base.replace('Original.\n', '```yaml\naliases: [Sample]\n```\n')
vals = two_lane_rows(page, [lambda t:t.replace('aliases: [Sample]', 'aliases: [Other]')], names=('LA',))
rc, output = run(vals)
check('D34 N28 a body code example creates no alias collision', rc == 0 and 'apply GPT' in output and output.count('patch -F0') == 2)
vals = two_lane_rows(base, [lambda t:t.replace('[GPT-4o]', '[GPT-4o, GPT]'), lambda t:t.replace('## Related\n', '## Related\n- ordinary\n')])
rc, output = run(vals, ('--union-dir', uniondir))
check('D35 N23 an alias naming its own page still unions', rc == 0 and 'apply-union GPT' in output)
other_page.unlink()

page = base[:base.index('## Key Points')] + '## Key Points\n- real\n```\n- code\n```\n'
changes = [lambda t:t.replace('- real\n', '- real\n- first\n'), lambda t:t.replace('- real\n', '- real\n- second\n')]
rc, output = run(two_lane_rows(page, changes), ('--union-dir', uniondir))
check('D36 N05 a closed EOF fence is placed: parent additions union above it', rc == 0 and 'apply-union GPT' in output and independent_items(union_page(output, page), ['- first', '- second'], 'Key Points') and independent_code(union_page(output, page), '- code'))
opened = page.rsplit('```\n', 1)[0]
rc, output = run(two_lane_rows(opened, changes), ('--union-dir', uniondir))
check('D37 N01 an unclosed EOF fence is placed: parent additions union above it', rc == 0 and 'apply-union GPT' in output and independent_items(union_page(output, opened), ['- first', '- second'], 'Key Points') and independent_code(union_page(output, opened), '- code'))
page = base.replace('Original.\n', '```\n- code\n```\n- anchor\n')
compositions = []
for context, ident in [(0, 'D38'), (3, 'D39')]:
    rc, output = run(two_lane_rows(page, [lambda t:t.replace('- anchor\n', '- first\n- anchor\n'), lambda t:t.replace('- anchor\n', '- second\n- anchor\n')], context=context), ('--union-dir', uniondir))
    compositions.append(union_page(output, page))
    check(ident + ' N06 an insertion right after a closing fence unions', rc == 0 and 'apply-union GPT' in output and independent_items(compositions[-1], ['- first', '- second', '- anchor'], 'Key Points') and independent_code(compositions[-1], '- code'))
check('D40 zero and three context lines compose the same union', bool(compositions[0]) and compositions[0] == compositions[1])
rc, output = run(two_lane_rows(page, [lambda t:t.replace('- code\n', '- code\n- inserted\n'), lambda t:t.replace('- anchor\n', '- second\n- anchor\n')], context=0), ('--union-dir', uniondir))
check('D41 a zero-context insertion inside the fence is refused with the fence named', rc == 0 and placed(output, 'fence', 'member LA added line'))
page = base[:base.index('## Key Points')] + '## Key Points\n- real\n```\n- code\n```'
rc, output = run(two_lane_rows(page, changes), ('--union-dir', uniondir))
try: composed = union_page(output, page)
except ValueError: composed = ''
check('D42 a closed EOF fence without a final newline is placed: the union keeps that EOF exactly', rc == 0 and 'apply-union GPT' in output and composed.endswith('\n```') and independent_items(composed, ['- first', '- second'], 'Key Points'))
path = next((Path(line.split(' · ', 1)[0][len('union diff: '):]) for line in output.splitlines() if line.startswith('union diff: ')), None)
native = subprocess.run(shlex.split(m.patch_command(vault, target, path, root / 'eof.rej')), text=True, capture_output=True) if path else None
check('D43 that union carries the no-newline marker and applies natively at zero fuzz', path is not None and '\\ No newline at end of file' in path.read_text() and native.returncode == 0, 'patch -F0 --dry-run TARGET UNION · exit ' + (str(native.returncode) if native else 'none'))
target.write_text(base)

rc, output = resolution([diff], ('--after-read', 'invalid'))
check('D44 malformed read acknowledgement fails closed', rc == 2 and 'PROBE FAILED:' in output and 'patch -F0' not in output)
receipt = m.digest(base.encode()) + ':' + m.digest(diff.read_bytes())
rc, output = resolution([diff, diff], ('--after-read', receipt))
check('D45 read acknowledgements cannot be shared across a batch', rc == 2 and 'PROBE FAILED:' in output and 'patch -F0' not in output)
rc, output = resolution([diff, diff], ('--after-read', receipt, '--after-read', receipt))
check('D46 each validated acknowledgement releases its own batch member', rc == 0 and output.count('patch -F0') == 4)
rc, output = release(['--vault', str(vault), '--after-read', receipt])
check('D47 an acknowledgement without a resolution fails closed', rc == 2 and 'patch -F0' not in output)

original_command = m.patch_command
def drift_during_command(*args, **kwargs):
    command = original_command(*args, **kwargs)
    target.write_text(drifted_title)
    return command
captured = io.StringIO()
try:
    with mock.patch.object(m, 'patch_command', drift_during_command), contextlib.redirect_stdout(captured):
        rc = m.main(['--vault', str(vault), '--resolved', str(diff)])
finally: target.write_text(base)
check('D48 the last base check follows command preparation', rc == 2 and 'base moved during planning' in captured.getvalue() and 'patch -F0' not in captured.getvalue())
saved_diff = diff.read_bytes()
def diff_during_command(*args, **kwargs):
    command = original_command(*args, **kwargs)
    diff.write_bytes(raised.read_bytes())
    return command
captured = io.StringIO()
try:
    with mock.patch.object(m, 'patch_command', diff_during_command), contextlib.redirect_stdout(captured):
        rc = m.main(['--vault', str(vault), '--resolved', str(diff)])
finally: diff.write_bytes(saved_diff)
check('D49 a resolution changed during validation emits no commands', rc == 2 and 'diff hash changed during planning' in captured.getvalue() and 'patch -F0' not in captured.getvalue())

for marker, ident in [('~~~', 'D50'), ('````', 'D51')]:
    page = base.replace('Original.\n', '- real\n' + marker + '\n```\n- example\n```\n' + marker + '\n')
    rc, output = run(two_lane_rows(page, [lambda t:t.replace('- example\n', '- example\n- inserted\n'), lambda t:t.replace('- real\n', '- real\n- ordinary\n')], context=0), ('--union-dir', uniondir))
    check(ident + ' an addition inside a nested fence is refused even without context lines', rc == 0 and placed(output, 'fence', 'member LA added line'))
target.write_text(base.replace('## Appears in', '## Citations'))
rc, output = release(args) if args else (1, '')
check('D52 N19 changed held-union hunk context refuses release', rc == 2 and 'patch -F0' not in output)
target.write_text(base)

original_emit = m.emit_union
for ident, held_tier in [('D55', True), ('D56', False)]:
    vals = union_rows(link('source-a'), link('source-b'))
    if held_tier:
        for i in (2, 6): vals[i]['claims'][0]['confidence'] = 'high'
    save(vals)
    changed_artefacts = {}
    def replaced_union(*args, **kwargs):
        path = original_emit(*args, **kwargs)
        changed_artefacts[path] = path.read_bytes()
        path.write_bytes(Path(vals[2]['claims'][0]['diff']).read_bytes())
        return path
    captured = io.StringIO()
    try:
        with mock.patch.object(m, 'emit_union', replaced_union), contextlib.redirect_stdout(captured):
            rc = m.main(['--vault', str(vault), '--ledger', str(ledger), '--union-dir', str(uniondir)])
    finally:
        for path, content in changed_artefacts.items(): path.write_bytes(content)
    check(ident + ' a replaced union cannot become the advertised held or applicable artefact', rc == 2 and 'union diff hash changed during planning' in captured.getvalue() and 'patch -F0' not in captured.getvalue())

# Round four: refusal replaces Markdown interpretation on union paths.
def guarded(output, construct, location='page line'):
    reasons = [line for line in output.splitlines() if line.startswith('  reason: union page guard:')]
    return 'manual GPT' in output and 'conflict GPT' not in output and 'patch -F0' not in output and len(reasons) == 1 and construct in reasons[0] and location in reasons[0]

ordinary_changes = [lambda t:t.replace('Original.\n', 'Original.\n- first\n'), lambda t:t.replace('Original.\n', 'Original.\n- second\n')]
attack = '- ```\n  first example\n  ```\n```\n- middle example\n```\n- ```\n  last example\n  ```\n'
page = base.replace('Original.\n', 'Original.\n' + attack)
rc, output = run(two_lane_rows(page, [lambda t:t.replace('- middle example\n', '- middle example\n- fictional A\n'), lambda t:t.replace('- middle example\n', '- middle example\n- fictional B\n')]), ('--union-dir', uniondir))
check('E01 R03 additions inside a list-framed top-level fence are refused with the fence named', rc == 0 and placed(output, 'fence', 'member LA added line'))
rc, output = run(two_lane_rows(base, ordinary_changes), ('--union-dir', uniondir))
check('E02 R03 removing the fences restores an ordinary union', rc == 0 and 'apply-union GPT' in output and 'union page guard:' not in output)
page = base.replace('Original.\n', 'Original.\n\nRejected claims\n---\n- rejected\n')
rc, output = run(two_lane_rows(page, ordinary_changes), ('--union-dir', uniondir))
composed = union_page(output, page)
check('E03 R17 a Setext subsection is placed: parent additions union above it and it stays a heading', rc == 0 and 'apply-union GPT' in output and independent_items(composed, ['- first', '- second'], 'Key Points') and independent_heading(composed, 'Rejected claims') and composed.index('- second\n') < composed.index('Rejected claims\n'))
page = page.replace('Rejected claims\n---\n', 'Rejected claims\n')
rc, output = run(two_lane_rows(page, ordinary_changes), ('--union-dir', uniondir))
check('E04 R17 removing the underline restores a union', rc == 0 and 'apply-union GPT' in output and 'union page guard:' not in output)

other_page = vault / 'wiki/models/Other.md'
for ident, aliases, collides in [
    ('E05', 'aliases:\n  - "Foo\\u0020shared"', True),
    ('E06', 'aliases:\n  - "Foo shared"', True),
    ('E07', 'aliases: ["Foo\\u0020shared"]', True),
    ('E08', 'aliases:\n  - "Different\\u0020alias"', False),
]:
    other_page.write_text(base.replace('GPT', 'Other').replace('aliases: [Other-4o]', aliases))
    vals = two_lane_rows(base, [lambda t:t.replace('[GPT-4o]', '[GPT-4o, "Foo shared"]'), ordinary_changes[1]])
    rc, output = run(vals, ('--union-dir', uniondir))
    check(ident + ' R16 block and flow aliases share escape decoding', rc == 0 and (('manual GPT' in output and 'multiple existing pages' in output and 'patch -F0' not in output) if collides else 'apply-union GPT' in output))
other_page.write_text(base.replace('GPT', 'Other').replace('[Other-4o]', '[Alpha,]'))
target.write_text(base)
rc, output = run(rows)
check('E09 R18 unrelated trailing-comma YAML cannot abort a single-lane plan', rc == 0 and 'apply GPT' in output and 'PROBE FAILED:' not in output)
other_page.write_text(base.replace('GPT', 'Other').replace('[Other-4o]', '[Alpha]'))
rc, output = run(rows)
check('E10 R18 ordinary catalogue control still applies', rc == 0 and 'apply GPT' in output and 'controls:' in output)
other_page.unlink()
page = base.replace('[GPT-4o]', '[Alpha,]')
rc, output = run(two_lane_rows(page, ordinary_changes), ('--union-dir', uniondir))
check('E11 R18 a target with a refused list becomes manual without aborting', rc == 0 and 'manual GPT' in output and 'union list refused:' in output and 'patch -F0' not in output)
page = base.replace('[GPT-4o]', '[Alpha]')
rc, output = run(two_lane_rows(page, ordinary_changes), ('--union-dir', uniondir))
check('E12 R18 a strict-compatible target still unions', rc == 0 and 'apply-union GPT' in output)

rc, output = run(creates + cycle('LB', claims=[otherclaim]))
check('E13 competing creates retain conflict without scanning their frontmatter', rc == 0 and 'conflict New Model' in output and 'union page guard:' not in output)
page = base.replace('aliases: [GPT-4o]\n', 'aliases: [GPT-4o]\nsources: [\n  raw/a.md,\n  raw/b.md\n]\n')
rc, output = run(two_lane_rows(page, ordinary_changes), ('--union-dir', uniondir))
check('E14 untouched multiline sources do not become a rejected single-line merge', rc == 0 and 'apply-union GPT' in output)
other_text = base.replace('GPT', 'Other')
other_page.write_text(other_text)
other_diff = root / 'ordinary-other.diff'
make_diff(other_diff, other_text, other_text.replace('Original.', 'Ordinary change.'), oldpath='a/wiki/models/Other.md', newpath='b/wiki/models/Other.md')
ordinary_other = copy.deepcopy(claim)
ordinary_other.update(name='Other', target='Other', base=m.digest(other_text.encode()), diff=str(other_diff), diff_hash=m.digest(other_diff.read_bytes()))
for ident, page, changes in [
    ('E15', base.replace('[GPT-4o]', '[Alpha,]'), ordinary_changes),
    ('E16', base, [lambda t:t.replace('[GPT-4o]', '[Alpha,]'), ordinary_changes[1]]),
]:
    vals = two_lane_rows(page, changes)
    vals[2]['claims'].append(copy.deepcopy(ordinary_other))
    rc, output = run(vals, ('--union-dir', uniondir))
    check(ident + ' a local strict-list refusal leaves another target applying', rc == 0 and 'manual GPT' in output and 'apply Other' in output and output.count('patch -F0') == 2)
other_page.unlink()
page = base.replace('Original.\n', 'Original.\n- ```\n')
vals = two_lane_rows(page, ordinary_changes)
for i in (2, 6): vals[i]['claims'][0]['confidence'] = 'high'
rc, output = run(vals, ('--union-dir', uniondir))
check('E17 a lift beside a list item that opens a fence composes a held union and names the full-page read', rc == 0 and 'tier-raised GPT' in output and 'confidence lift: read the page in full' in output and 'held until the full-page read:' in output and 'patch -F0' not in output)
rc, output = run(two_lane_rows(page, [lambda t:t.replace('Original.\n', 'Changed prose.\n'), ordinary_changes[1]]), ('--union-dir', uniondir))
check('E18 a competing prose edit beside that placed fence is ordinary conflict', rc == 0 and 'conflict GPT' in output and 'patch -F0' not in output and 'union page guard:' not in output)
other_page.write_text(base.replace('GPT', 'Other').replace('Original.\n', 'Original.\n%% comment\n'))
target.write_text(base)
rc, output = run(rows)
check('E19 an unrelated guarded page does not inhibit an ordinary update', rc == 0 and 'apply GPT' in output and 'union page guard:' not in output)
other_page.unlink()

# 2026-09-22 (№172): the parser places fences, Setext headings and HTML blocks; the page
# guard keeps only %% and $$. 'union' expects a union, 'guard' the page guard, and any
# other word a placement refusal naming that construct at a member's added line.
families = [('fence', '- example ```', 'union', 'union'), ('Setext', '   ===', 'Setext heading', 'Setext heading'), ('HTML', '> 1. - <aside>', 'union', 'HTML block'), ('Obsidian comment', '- quoted %% example', 'guard', 'guard'), ('maths', '- quoted $$ example', 'guard', 'guard')]
said = {'union': 'is placed by the parser and the target unions', 'guard': 'is refused by the page guard'}
def family_outcome(output, want, family, location):
    if want == 'union': return 'apply-union GPT' in output and 'union page guard:' not in output and 'union placement refused:' not in output
    if want == 'guard': return guarded(output, family, location)
    return placed(output, want, 'member LA added line')
for index, (family, marker, on_page, on_member) in enumerate(families):
    page = base.replace('Original.\n', 'Original.\n' + marker + '\n')
    vals = two_lane_rows(page, ordinary_changes)
    before_files = {p.name:p.read_bytes() for p in uniondir.iterdir()}
    rc, output = run(vals, ('--union-dir', uniondir))
    check(f'E{20 + index * 2:02} {family} in the body ' + said.get(on_page, 'is placed: an addition that splits it is refused with the construct named'), rc == 0 and family_outcome(output, on_page, family, 'page line') and (on_page == 'union' or before_files == {p.name:p.read_bytes() for p in uniondir.iterdir()}))
    rc, output = run(two_lane_rows(base, ordinary_changes), ('--union-dir', uniondir))
    check(f'E{21 + index * 2:02} {family} body-free control unions', rc == 0 and 'apply-union GPT' in output and 'union page guard:' not in output)
    vals = two_lane_rows(base, [lambda t, marker=marker:t.replace('Original.\n', 'Original.\n' + marker + '\n'), ordinary_changes[1]])
    rc, output = run(vals, ('--union-dir', uniondir))
    check(f'E{30 + index * 2:02} {family} added by a member ' + said.get(on_member, 'is refused with the construct and the member line named'), rc == 0 and family_outcome(output, on_member, family, 'member LA added line'))
    rc, output = run(two_lane_rows(base, ordinary_changes), ('--union-dir', uniondir))
    check(f'E{31 + index * 2:02} {family} ordinary added-line control unions', rc == 0 and 'apply-union GPT' in output and 'union page guard:' not in output)
    # Both current and appended frontmatter values are outside the body guard.
    page = base.replace('[GPT-4o]', json.dumps([marker]))
    vals = two_lane_rows(page, [lambda t, marker=marker:t.replace(json.dumps([marker]), json.dumps([marker, marker + ' extra'])), ordinary_changes[1]])
    rc, output = run(vals, ('--union-dir', uniondir))
    check(f'E{40 + index:02} {family} frontmatter is excluded from the guard', rc == 0 and 'apply-union GPT' in output and 'union page guard:' not in output)

# 2026-09-22 (№172): a construct inside a container is placed there; an indented line the
# new item would take in (E46, E50) is refused, the rest union.
for ident, marker, refused in [('E45', '> - ~~~', False), ('E46', '    - ```', True), ('E47', '> ---', False), ('E48', '- ===', False), ('E49', '1. > - <div>', False), ('E50', '     <div>', True)]:
    page = base.replace('Original.\n', 'Original.\n' + marker + '\n')
    rc, output = run(two_lane_rows(page, ordinary_changes), ('--union-dir', uniondir))
    if refused: check(ident + ' an indented construct the added item would take in is refused', rc == 0 and placed(output, 'list item', 'takes existing line'))
    else: check(ident + ' a construct inside its container is placed: ordinary additions union', rc == 0 and 'apply-union GPT' in output and independent_items(union_page(output, page), ['- first', '- second'], 'Key Points'))
for ident, marker in [('E51', '- normal <inline> example'), ('E52', '- effect > 0'), ('E53', '- cost $5; 50% complete'), ('E54', '- three = signs and -- punctuation')]:
    page = base.replace('Original.\n', 'Original.\n' + marker + '\n')
    rc, output = run(two_lane_rows(page, ordinary_changes), ('--union-dir', uniondir))
    check(ident + ' ordinary punctuation does not fire the guard', rc == 0 and 'apply-union GPT' in output and 'union page guard:' not in output)

for ident, aliases in [('E55', 'aliases:\n  - "Foo\\qshared"'), ('E56', 'aliases: ["Foo\\qshared"]')]:
    other_page.write_text(base.replace('GPT', 'Other').replace('aliases: [Other-4o]', aliases))
    vals = two_lane_rows(base, [lambda t:t.replace('[GPT-4o]', "[GPT-4o, 'Foo\\qshared']"), ordinary_changes[1]])
    rc, output = run(vals, ('--union-dir', uniondir))
    check(ident + ' non-JSON quoted aliases share the raw-inner fallback', rc == 0 and 'manual GPT' in output and 'multiple existing pages' in output and 'patch -F0' not in output)
other_page.unlink()
page = base.replace('[GPT-4o]', '["Foo\\qshared"]')
rc, output = run(two_lane_rows(page, [lambda t:t.replace('["Foo\\qshared"]', '["Foo\\qshared", First]'), ordinary_changes[1]]), ('--union-dir', uniondir))
check('E57 raw-inner fallback is confined to the catalogue', rc == 0 and 'manual GPT' in output and 'union list refused:' in output and 'raw fallback' in output and 'patch -F0' not in output)
for ident, replacement in [('E58', '[Alpha,]'), ('E59', '["unfinished]')]:
    vals = two_lane_rows(base, [lambda t, replacement=replacement:t.replace('[GPT-4o]', replacement), ordinary_changes[1]])
    rc, output = run(vals, ('--union-dir', uniondir))
    check(ident + ' a refused proposed list is manual rather than a global failure', rc == 0 and 'manual GPT' in output and 'union list refused:' in output and 'patch -F0' not in output)
target.write_text(base)

page = base[:base.index('# GPT')].replace('aliases: [GPT-4o]\n', 'aliases: [GPT-4o]\ndescription: |\n  ## Key Points\n') + '- anchor\n'
changes = [lambda t:t.replace('- anchor\n', '- anchor\n- first\n'), lambda t:t.replace('- anchor\n', '- anchor\n- second\n')]
rc, output = run(two_lane_rows(page, changes), ('--union-dir', uniondir))
check('E62 an ATX-shaped frontmatter scalar cannot impersonate a body section', rc == 0 and 'conflict GPT' in output and 'patch -F0' not in output)
page = page.replace('---\n- anchor\n', '---\n## Key Points\n- anchor\n')
rc, output = run(two_lane_rows(page, changes), ('--union-dir', uniondir))
check('E63 a real body section ignores the same heading inside frontmatter', rc == 0 and 'apply-union GPT' in output and all(item in union_page(output, page) for item in ('- first\n', '- second\n')))
for ident, items, expected in [('E64', 'raw/a.md', 'apply-union GPT'), ('E65', 'raw/a.md,', 'manual GPT')]:
    page = base.replace('aliases: [GPT-4o]\n', 'aliases: [GPT-4o]\nsources: [' + items + '] # provenance\n')
    rc, output = run(two_lane_rows(page, ordinary_changes), ('--union-dir', uniondir))
    check(ident + ' strict validation reads an unchanged commented list content', rc == 0 and expected in output and ('union list refused:' in output if expected.startswith('manual') else 'union list refused:' not in output))
target.write_text(base)

# 2026-09-22 (№172): the guard keeps two families; the parser places the other three.
check('E60 skill states the two page-guard families and the constructs the parser places', 'The page guard remains only for what CommonMark cannot place: an Obsidian comment marker (%% anywhere) or a maths block marker ($$ anywhere)' in skill and all(term in skill for term in ('inside a fence, an indented code block or an HTML block', 'a Setext underline', 'a swallowing fence')))
for ident, value, expected in [('E66', '[Alpha] # [ordinary comment]', ['Alpha']), ('E67', '["Right ] # kept", "Other"] # [comment]', ['Right ] # kept', 'Other'])]:
    decoded = m.frontmatter('---\naliases: ' + value + '\n---\n').get('aliases')
    check(ident + ' flow-list boundaries distinguish comments from quoted brackets', decoded == expected)
for ident, value, expected in [('E68', '[raw/a.md] # [ordinary comment]', 'apply-union GPT'), ('E69', '[raw/a.md,] # [ordinary comment]', 'manual GPT'), ('E70', '["Right ] # kept", raw/a.md] # [comment]', 'apply-union GPT')]:
    page = base.replace('aliases: [GPT-4o]\n', 'aliases: [GPT-4o]\nsources: ' + value + '\n')
    rc, output = run(two_lane_rows(page, ordinary_changes), ('--union-dir', uniondir))
    check(ident + ' commented lists preserve strict contents and quoted delimiters', rc == 0 and expected in output)
target.write_text(base)
status_path = here.parents[1] / 'design-status-fact.md'
if status_path.is_file():
    # This proposal is a build-workspace artefact, not a shipped dependency.
    status_fact = status_path.read_text()
    check('E61 dated status fact carries the guard and bound second step', '**Status 2026-09-21' in status_fact and '--resolved <artefact> --after-read <base>:<diff_hash>' in status_fact and all(term in status_fact for term in ('page guard', 'Setext', 'HTML', 'Obsidian', 'maths')))
else:
    check('E61 current skill carries the guard and bound second step when the optional dated proposal is absent', '--resolved <artefact> --after-read <base>:<diff_hash>' in skill and all(term in skill for term in ('page guard', 'Setext', 'HTML', 'Obsidian', 'maths')))

# Round five: refuse re-parenting and undecodable list escapes.
nested_child = '  - Only at temperature 0.\n'
nested = base.replace('Original.\n', '- Treatment X improves accuracy.\n' + nested_child)
before_child = [lambda t, name=name:t.replace(nested_child, '- Treatment ' + name + ' improves accuracy.\n' + nested_child) for name in ('Y', 'Z')]
after_child = [lambda t, name=name:t.replace(nested_child, nested_child + '- Treatment ' + name + ' improves accuracy.\n') for name in ('Y', 'Z')]
for refusal_id, control_id, context in [('E71', 'E72', 3), ('E73', 'E74', 0)]:
    rc, output = run(two_lane_rows(nested, before_child, context=context), ('--union-dir', uniondir))
    reasons = [line for line in output.splitlines() if line.startswith('  reason: union placement refused:')]
    check(refusal_id + ' S10c insertion before an existing child is manual', rc == 0 and 'manual GPT' in output and 'patch -F0' not in output and len(reasons) == 1 and all(text in reasons[0] for text in ('member LA', 'added line', '- Treatment Y improves accuracy.', 'takes existing line', '  - Only at temperature 0.')), reasons[0].strip() if reasons else '')
    rc, output = run(two_lane_rows(nested, after_child, context=context), ('--union-dir', uniondir))
    composed = union_page(output, nested)
    check(control_id + ' S10b additions after the complete nested block union', rc == 0 and 'apply-union GPT' in output and '- Treatment X improves accuracy.\n' + nested_child in composed and all('- Treatment ' + name + ' improves accuracy.\n' in composed for name in ('Y', 'Z')))
for ident, continuation in [('E75', '  Only at temperature 0.\n'), ('E76', '\tOnly at temperature 0.\n')]:
    page = nested.replace(nested_child, continuation)
    changes = [lambda t, name=name, continuation=continuation:t.replace(continuation, '- Treatment ' + name + ' improves accuracy.\n' + continuation) for name in ('Y', 'Z')]
    rc, output = run(two_lane_rows(page, changes, context=0), ('--union-dir', uniondir))
    check(ident + ' an existing indented continuation also requires a hand read', rc == 0 and 'manual GPT' in output and 'union placement refused:' in output and 'patch -F0' not in output)
rc, output = run(two_lane_rows(nested, [lambda t:t.replace(nested_child, '- first added parent\n- final added parent\n' + nested_child), after_child[1]]), ('--union-dir', uniondir))
check('E77 consecutive additions name the one immediately before the child', rc == 0 and 'manual GPT' in output and 'final added parent' in output and 'takes existing line' in output and 'patch -F0' not in output)
page = base.replace('Original.\n', '- parent\n  \n- next complete item\n')
rc, output = run(two_lane_rows(page, [lambda t:t.replace('- parent\n', '- parent\n- first\n'), lambda t:t.replace('- parent\n', '- parent\n- second\n')]), ('--union-dir', uniondir))
check('E78 whitespace-only lines are not existing children or continuations', rc == 0 and 'apply-union GPT' in output and 'union placement refused:' not in output)
page = base[:base.index('## Key Points')] + '## Key Points\n- parent\n' + nested_child
rc, output = run(two_lane_rows(page, [lambda t:t + '- first\n', lambda t:t + '- second\n'], context=0), ('--union-dir', uniondir))
check('E79 an addition after the complete nested block at EOF still unions', rc == 0 and 'apply-union GPT' in output and '- parent\n' + nested_child in union_page(output, page))

unsafe_alias = '"Foo\\qshared"'
rc, output = run(two_lane_rows(base, [lambda t:t.replace('[GPT-4o]', '[GPT-4o, ' + unsafe_alias + ']'), ordinary_changes[1]]), ('--union-dir', uniondir))
reasons = [line for line in output.splitlines() if line.startswith('  reason: union list refused:')]
check('E80 S09 an appended alias needing raw fallback is manual', rc == 0 and 'manual GPT' in output and 'patch -F0' not in output and len(reasons) == 1 and all(text in reasons[0] for text in (unsafe_alias, 'member LA', 'line', 'raw fallback')), reasons[0].strip() if reasons else '')
for ident, spelling, decoded in [('E81', json.dumps('Foo\\qshared'), 'Foo\\qshared'), ('E82', '"Foo\\u0020shared"', 'Foo shared'), ('E83', "'Foo\\qshared'", 'Foo\\qshared')]:
    rc, output = run(two_lane_rows(base, [lambda t, spelling=spelling:t.replace('[GPT-4o]', '[GPT-4o, ' + spelling + ']'), ordinary_changes[1]]), ('--union-dir', uniondir))
    composed = union_page(output, base)
    check(ident + ' valid escaped or single-quoted aliases still union', rc == 0 and 'apply-union GPT' in output and spelling in composed and decoded in m.frontmatter(composed).get('aliases', []))

other_page = vault / 'wiki/models/Other.md'
variants = [('"Foo\\u0020shared"', 'Foo shared'), ("'Foo\\u0020shared'", 'Foo\\u0020shared'), (unsafe_alias, 'Foo\\qshared')]
for index, (form, spelling, decoded) in enumerate((form, spelling, decoded) for form in ('block', 'flow') for spelling, decoded in variants):
    aliases = 'aliases:\n  - ' + spelling if form == 'block' else 'aliases: [' + spelling + ']'
    other_text = base.replace('GPT', 'Other').replace('aliases: [Other-4o]', aliases)
    other_page.write_text(other_text)
    vals = two_lane_rows(base, [lambda t, decoded=decoded:t.replace('[GPT-4o]', '[GPT-4o, ' + json.dumps(decoded) + ']'), ordinary_changes[1]])
    rc, output = run(vals, ('--union-dir', uniondir))
    check(f'E{84 + index:02} S17 {form} alias decoding and collision remain consistent', m.frontmatter(other_text).get('aliases') == [decoded] and rc == 0 and 'manual GPT' in output and 'multiple existing pages' in output and 'union list refused:' not in output and 'patch -F0' not in output)
other_page.unlink()
for ident, aliases in [('E90', 'aliases: [' + unsafe_alias + ']'), ('E91', 'aliases:\n  - ' + unsafe_alias)]:
    page = base.replace('aliases: [GPT-4o]', aliases)
    rc, output = run(two_lane_rows(page, ordinary_changes), ('--union-dir', uniondir))
    check(ident + ' an existing fallback alias refuses only its union target', rc == 0 and 'manual GPT' in output and 'union list refused:' in output and unsafe_alias in output and 'page line' in output and 'patch -F0' not in output)
other_page.write_text(base.replace('GPT', 'Other').replace('aliases: [Other-4o]', 'aliases:\n  - ' + unsafe_alias))
target.write_text(base)
rc, output = run(rows)
check('E92 catalogue fallback on an unrelated page cannot abort ordinary work', rc == 0 and 'apply GPT' in output and output.count('patch -F0') == 2)
other_page.unlink()
rc, output = run(two_lane_rows(base, [lambda t:t.replace('aliases: [GPT-4o]', 'aliases:\n  - GPT-4o\n  - ' + unsafe_alias), ordinary_changes[1]]), ('--union-dir', uniondir))
check('E93 a proposed block alias needing fallback names its member line', rc == 0 and 'manual GPT' in output and 'union list refused:' in output and unsafe_alias in output and 'member LA line' in output and 'patch -F0' not in output)
try: m.list_items(unsafe_alias); refused = False
except (ValueError, AttributeError): refused = True
check('E94 the strict list parser never returns a raw-fallback item', refused)
check('E95 class wording places the page-guard exception before ordinary classes', 'The page guard is an exception applied before ordinary classification' in skill and 'otherwise `conflict` outranks `manual`' in skill)
page = base.replace('aliases: [GPT-4o]\n', 'aliases: [GPT-4o]\nsources: [raw/a.md]\n')
rc, output = run(two_lane_rows(page, [lambda t:t.replace('[raw/a.md]', '[raw/a.md, ' + unsafe_alias + ']'), ordinary_changes[1]]), ('--union-dir', uniondir))
check('E96 sources items requiring fallback are also refused with a member line', rc == 0 and 'manual GPT' in output and 'union list refused:' in output and unsafe_alias in output and 'sources' in output and 'member LA' in output and 'line' in output and 'patch -F0' not in output)
target.write_text(base)

# Round six (IDEAS №172, 2026-09-22): the planner reads Markdown through markdown-it-py.
# Every probe of the five critic reports is a leg named by its probe id, with the outcome
# the critic stated: a union where the placement is right (confirmed by the suite's own
# CommonMark read), manual with a reason where a construct cannot be placed.
def outcome(values, extra=None):
    return run(values, ('--union-dir', uniondir) if extra is None else extra)

def after(anchor, text):
    return lambda t: t.replace(anchor, anchor + text, 1)

def key_points(body):
    return base.replace('## Key Points\nOriginal.\n', '## Key Points\n' + body)

def unioned(output, page, texts, title='Key Points'):
    return 'apply-union GPT' in output and independent_items(union_page(output, page), texts, title)

def lanes(page, first, second, **kw):
    return two_lane_rows(page, [first, second], **kw)

plain_other = base.replace('GPT', 'Other')

def split_items(inner):
    """The planner's strict list splitter, or None where it refuses or is absent (the shipped control)."""
    try: return m.list_items(inner)
    except (ValueError, AttributeError): return None
two_links = (after('## Appears in\n', link('source-a')), after('## Appears in\n', link('source-b')))
parents = (after('Original.\n', '- first\n'), after('Original.\n', '- second\n'))

# The parser: missing, or its one dependency missing, the planner stops; present, it runs.
# A name set to None in sys.modules refuses to import wherever the package is installed,
# so these legs do not depend on the install layout; the same harness blocking an unused
# name is the positive control that it really runs the plan.
blocker = 'import runpy, sys\nfor name in sys.argv[1].split(","): sys.modules[name] = None\nsys.argv = sys.argv[2:]\nrunpy.run_path(sys.argv[0], run_name="__main__")\n'
def blocked(names):
    target.write_text(base); save(rows)
    p = subprocess.run([sys.executable, '-B', '-c', blocker, names, str(script), '--vault', str(vault), '--ledger', str(ledger)], text=True, capture_output=True)
    return p.returncode, p.stdout, p.stderr
rc, out, err = blocked('markdown_it')
check('PARSER-01 without markdown-it-py the planner prints PROBE FAILED and exits 2, never scanning lines instead', rc == 2 and out.startswith('PROBE FAILED: markdown-it-py not importable (') and 'apply GPT' not in out and 'patch -F0' not in out and not err, 'markdown_it blocked · exit ' + str(rc) + ' · ' + out.strip()[:90])
rc, out, err = blocked('mdurl')
check('PARSER-01b without its dependency mdurl the planner also exits 2 naming the missing module', rc == 2 and out.startswith('PROBE FAILED: markdown-it-py not importable (') and 'mdurl' in out and 'patch -F0' not in out, 'mdurl blocked · exit ' + str(rc) + ' · ' + out.strip()[:90])
rc, out, err = blocked('no_such_module_control')
check('PARSER-02 the same harness with the parser present runs the plan (positive control)', rc == 0 and 'apply GPT' in out and 'PROBE FAILED' not in out, 'unused name blocked · exit ' + str(rc))
check('SKILL-01 the skill names the parser, its missing-parser exit and the residue guard', 'markdown-it-py' in skill and 'PROBE FAILED: markdown-it-py not importable' in skill and 'The page guard remains only for what CommonMark cannot place' in skill)
target.write_text(base); save(rows)
captured, code = io.StringIO(), None
if getattr(m, 'markdown_it', None) is not None and hasattr(m, 'PARSER_PIN'):
    with mock.patch.object(m.markdown_it, '__version__', '0.0.0-control'), contextlib.redirect_stdout(captured):
        code = m.main(['--vault', str(vault), '--ledger', str(ledger)])
out = captured.getvalue()
check('VERSION-01 another markdown-it-py version is named in a note, the plan still runs', code == 0 and 'note: markdown-it-py 0.0.0-control is not the accepted ' + str(getattr(m, 'PARSER_PIN', '?')) in out and 'apply GPT' in out)
rc, out = run(rows)
check('VERSION-02 the accepted version prints no version note', rc == 0 and 'apply GPT' in out and 'note: markdown-it-py' not in out and markdown_it.__version__ == getattr(m, 'PARSER_PIN', None))

# The composed-page oracle: round five's section-end placement under a bold pseudo-heading
# moves the additions into another list; the oracle refuses it, the list-aware placement unions.
pseudo = key_points('- a\n\n**Rejected:**\n- r\n')
vals = lanes(pseudo, after('- a\n', '- first\n'), after('- a\n', '- second\n'))
save(vals)
original_joined = m.joined_list if hasattr(m, 'joined_list') else None
def section_end(view, ids, at, count):
    # Round five's placement, injected: the end of the section's own text, never the list.
    if original_joined(view, ids, at, count) is None: return None
    section = view.section_of(at)
    last = view.last_content(view.blocks[section].end, view.own_end(section))
    return ('at', next(ident[1] for ident in reversed(ids[:last]) if ident[0] == 'E') + 1)
captured, code = io.StringIO(), None
if original_joined:
    with mock.patch.object(m, 'joined_list', section_end), contextlib.redirect_stdout(captured):
        code = m.main(['--vault', str(vault), '--ledger', str(ledger), '--union-dir', str(uniondir)])
out = captured.getvalue()
check('ORACLE-01 a composition that moves additions into another list is refused by the composed-page oracle', code == 0 and 'manual GPT' in out and 'union placement refused: composed page line' in out and 'patch -F0' not in out)
rc, output = outcome(vals)
composed = union_page(output, pseudo)
check('ORACLE-02 the list-aware placement of the same page unions above the pseudo-heading', rc == 0 and unioned(output, pseudo, ['- first', '- second']) and composed.index('- second\n') < composed.index('**Rejected:**'))

# The second parser build: a repeated first line is not a duplicate item in
# another context. These exercise the full planner, then attack the oracle alone.
repeat = '- Treatment Y improves accuracy.\n'
qualifier = '  - Only at temperature 0.\n'
critic_repeat = key_points(repeat + qualifier + '\n**Unconditional results**\n- anchor\n')
rc, output = outcome(lanes(critic_repeat, after('- anchor\n', repeat), after('- anchor\n', '- Other result.\n')))
composed = union_page(output, critic_repeat)
check('DUP-01 critic finding 1: qualified and unconditional occurrences both survive', rc == 0 and unioned(output, critic_repeat, [repeat.rstrip(), '- Other result.']) and composed.count(repeat) == 2 and repeat + qualifier in composed and composed.index('**Unconditional results**') < composed.rindex(repeat) and output.count('patch -F0') == 2)
same_place = key_points('- anchor\n')
rc, output = outcome(lanes(same_place, after('- anchor\n', repeat), after('- anchor\n', repeat)))
check('DUP-02 same-context duplicates from two members union once (accepting control)', rc == 0 and unioned(output, same_place, [repeat.rstrip()]) and union_page(output, same_place).count(repeat) == 1)
existing_repeat = key_points('- anchor\n' + repeat)
rc, output = outcome(lanes(existing_repeat, after(repeat, repeat), after(repeat, '- Other result.\n')))
check('DUP-03 an adjacent complete existing duplicate is retained once', rc == 0 and unioned(output, existing_repeat, [repeat.rstrip(), '- Other result.']) and union_page(output, existing_repeat).count(repeat) == 1)
continued = key_points(repeat + '  Only in the first cohort.\n\n**Other cohort**\n- anchor\n')
rc, output = outcome(lanes(continued, after('- anchor\n', repeat), after('- anchor\n', '- Other result.\n')))
composed = union_page(output, continued)
check('DUP-04 different continuation text: the complete existing item cannot consume a standalone addition', rc == 0 and unioned(output, continued, [repeat.rstrip(), '- Other result.']) and composed.count(repeat) == 2 and repeat + '  Only in the first cohort.\n' in composed)
rc, output = outcome(lanes(same_place, after('- anchor\n', repeat + '  Only in cohort A.\n'), after('- anchor\n', repeat + '  Only in cohort B.\n')))
check('DUP-05 two newly added continuations retain the one-line contract: conflict, no partial union', rc == 0 and 'conflict GPT' in output and 'union diff:' not in output and 'patch -F0' not in output)
headed_repeat = key_points(repeat + '\n**Another heading in the section**\n- anchor\n')
rc, output = outcome(lanes(headed_repeat, after('- anchor\n', repeat), after('- anchor\n', '- Other result.\n')))
composed = union_page(output, headed_repeat)
check('DUP-06 duplicate under another heading in the same section keeps both contexts', rc == 0 and unioned(output, headed_repeat, [repeat.rstrip(), '- Other result.']) and composed.count(repeat) == 2 and composed.index('**Another heading in the section**') < composed.rindex(repeat))
anchored_repeat = key_points(repeat + '- different anchor\n')
rc, output = outcome(lanes(anchored_repeat, after('- different anchor\n', repeat), after('- different anchor\n', '- Other result.\n')))
check('DUP-07 another anchor in the same list gives a different section position: both survive', rc == 0 and unioned(output, anchored_repeat, [repeat.rstrip(), '- Other result.']) and union_page(output, anchored_repeat).count(repeat) == 2)
sub_repeat = key_points('- anchor\n\n### Qualified subsection\n' + repeat)
rc, output = outcome(lanes(sub_repeat, after('- anchor\n', repeat), after('- anchor\n', '- Other result.\n')))
check('DUP-08 a matching first line under an actual subheading cannot consume the parent-section addition', rc == 0 and unioned(output, sub_repeat, [repeat.rstrip(), '- Other result.']) and union_page(output, sub_repeat).count(repeat) == 2)
rc, output = outcome(lanes(critic_repeat, lambda t: t.replace(qualifier, repeat + qualifier, 1), after('- anchor\n', '- Other result.\n')))
reasons = [line for line in output.splitlines() if line.startswith('  reason: union placement refused:')]
check('DUP-09 keeping a repeat above a qualification would change its parent: manual, both lines named', rc == 0 and 'manual GPT' in output and 'patch -F0' not in output and len(reasons) == 1 and all(term in reasons[0] for term in ('added line', repeat.strip(), 'takes existing line', qualifier.strip())))

def oracle_fixture(page, changed):
    patch = ''.join(difflib.unified_diff(page.splitlines(keepends=True), changed.splitlines(keepends=True), fromfile='a/' + rel, tofile='b/' + rel))
    member = {'text': page, 'changed': changed, 'parsed': m.parse_diff(patch, vault.resolve()), 'problems': [], 'claim': {'lane': 'LA'}, 'target': target, 'lift': False}
    text, ids = m.proposal(member)
    ids = [('A', 0, index) if ident[0] == 'A' else ident for index, ident in enumerate(ids)]
    return member, [(m.page_view(text), ids)]

def oracle_verdict(page, proposed, composed, origin, duplicates=None):
    if not hasattr(m, 'check_composed'): return False, 'oracle absent'
    try:
        member, views = oracle_fixture(page, proposed)
        # Deliberately omit every addition from kept: completeness must come from
        # the member's proposal, not a list the composer can accidentally shorten.
        m.check_composed(composed, origin, [member], views, [], **({'duplicates': duplicates} if duplicates is not None else {}))
    except (m.ProbeError, TypeError) as error: return False, str(error)
    return True, ''

base_origin = [('E', index) for index in range(len(same_place.splitlines()))]
accepted, reason = oracle_verdict(same_place, after('- anchor\n', repeat)(same_place), same_place, base_origin)
check('DUP-10 the oracle refuses a silently dropped addition even when kept is empty', not accepted and 'added line' in reason and 'dropped without an exact same-context duplicate' in reason, reason)
if hasattr(m, 'check_composed'):
    member, views = oracle_fixture(same_place, after('- anchor\n', repeat)(same_place))
    accepted, reason = oracle_verdict(same_place, member['changed'], member['changed'], views[0][1])
else: accepted, reason = False, 'oracle absent'
check('DUP-11 all additions present in their own context pass the same oracle harness', accepted, reason)
if hasattr(m, 'check_composed'):
    member, views = oracle_fixture(critic_repeat, after('- anchor\n', repeat)(critic_repeat))
    added_id = next(ident for ident in views[0][1] if ident[0] == 'A')
    old_id = ('E', critic_repeat.splitlines().index(repeat.rstrip()))
    accepted, reason = oracle_verdict(critic_repeat, member['changed'], critic_repeat, [('E', i) for i in range(len(critic_repeat.splitlines()))], {added_id: old_id})
else: accepted, reason = True, 'oracle absent'
check('DUP-12 a forged duplicate mapping is refused with both occurrence lines', not accepted and 'added line' in reason and 'was dropped against line' in reason and 'different context' in reason, reason)
if hasattr(m, 'check_composed'):
    member, views = oracle_fixture(existing_repeat, after(repeat, repeat)(existing_repeat))
    added_id = next(ident for ident in views[0][1] if ident[0] == 'A')
    old_id = ('E', existing_repeat.splitlines().index(repeat.rstrip()))
    accepted, reason = oracle_verdict(existing_repeat, member['changed'], existing_repeat, [('E', i) for i in range(len(existing_repeat.splitlines()))], {added_id: old_id})
else: accepted, reason = False, 'oracle absent'
check('DUP-13 the oracle accepts a verified complete same-context duplicate', accepted, reason)
metadata_only = base.replace('[GPT-4o]', '[GPT-4o, AddedAlias]')
accepted, reason = oracle_verdict(base, metadata_only, base, [('E', i) for i in range(len(base.splitlines()))])
check('DUP-14 every added metadata line is checked too: a lost alias refuses', not accepted and 'added frontmatter line' in reason and 'did not survive' in reason, reason)
if hasattr(m, 'check_composed'):
    member, views = oracle_fixture(base, metadata_only)
    accepted, reason = oracle_verdict(base, metadata_only, metadata_only, views[0][1])
else: accepted, reason = False, 'oracle absent'
check('DUP-15 the same metadata addition preserved in the composed list passes', accepted, reason)
if hasattr(m, 'check_composed'):
    member, views = oracle_fixture(same_place, after('- anchor\n', repeat)(same_place))
    altered_text = member['changed'].replace(repeat, '- Different evidence.\n')
    accepted, reason = oracle_verdict(same_place, member['changed'], altered_text, views[0][1])
else: accepted, reason = True, 'oracle absent'
check('DUP-16 an identity retained on the wrong text cannot hide a lost addition', not accepted and 'changed text at composed page line' in reason, reason)
rc, output = outcome(lanes(same_place, after('- anchor\n', '- First added anchor.\n' + repeat), after('- anchor\n', '- Second added anchor.\n' + repeat)))
check('DUP-17 different added anchors in one base gap preserve both repeated occurrences', rc == 0 and unioned(output, same_place, [repeat.rstrip(), '- First added anchor.', '- Second added anchor.']) and union_page(output, same_place).count(repeat) == 2)

# The closing fence is at column zero. PyYAML reads the fixture metadata
# independently; no production splitter supplies its input or expected aliases.
for suffix, close in (('dash', '---'), ('dots', '...'), ('spaces', '--- \t')):
    metadata = 'title: Other\ntype: model\nconfidence: medium\ndescription: |\n  ---\n  narrative\naliases: [Shadow]\n'
    other_text = '---\n' + metadata + close + '\n# Other\n'
    other_page.write_text(other_text)
    check('FM-01-' + suffix + ' aliases below an indented fence agree with PyYAML', m.frontmatter(other_text).get('aliases') == yaml.safe_load(metadata)['aliases'] == ['Shadow'])
    rc, output = outcome(lanes(base, lambda t: t.replace('[GPT-4o]', '[GPT-4o, Shadow]'), parents[1]))
    check('FM-02-' + suffix + ' critic finding 2: the hidden alias collision is manual', rc == 0 and 'manual GPT' in output and 'multiple existing pages' in output and 'patch -F0' not in output)
    plain_metadata = metadata.replace('  ---\n', '  ordinary text\n')
    other_page.write_text('---\n' + plain_metadata + close + '\n# Other\n')
    rc, output = outcome(lanes(base, lambda t: t.replace('[GPT-4o]', '[GPT-4o, Shadow]'), parents[1]))
    check('FM-03-' + suffix + ' unindented closing fence control retains the same collision', rc == 0 and 'manual GPT' in output and 'multiple existing pages' in output and 'patch -F0' not in output)
other_page.unlink()
for suffix, marker in (('dash', '  ---'), ('dots', '  ...')):
    metadata_page = base.replace('aliases: [GPT-4o]\n', 'description: |\n' + marker + '\n  %% metadata comment %%\n  $$ metadata maths $$\naliases: [GPT-4o]\n')
    rc, output = outcome(lanes(metadata_page, *parents))
    check('FM-04-' + suffix + ' metadata markers remain outside the body guard and additions union', rc == 0 and unioned(output, metadata_page, ['- first', '- second']) and 'union page guard:' not in output)
    bad_page = metadata_page.replace('---\n# GPT', '# GPT')
    rc, output = outcome(lanes(bad_page, *parents))
    check('FM-05-' + suffix + ' genuinely unclosed frontmatter fails closed despite an indented delimiter', rc == 2 and 'PROBE FAILED: frontmatter does not close' in output and 'patch -F0' not in output)
dot_page = base.replace('---\n# GPT', '...\n# GPT')
rc, output = outcome(lanes(dot_page, *parents))
check('FM-06 a column-zero document-end fence gives the correct body offset', rc == 0 and unioned(output, dot_page, ['- first', '- second']))
first_close = base.replace('Original.\n', 'Original.\n\n%% body comment %%\n---\naliases: [BodyOnly]\n')
rc, output = outcome(lanes(first_close, *parents))
check('FM-07 the first real closing fence wins: later metadata-like body lines remain body', rc == 0 and guarded(output, 'Obsidian comment') and m.frontmatter(first_close).get('aliases') == ['GPT-4o'])
for suffix, aliases in (('flow', 'aliases: [Shadow, OtherAlias]'), ('block', 'aliases:\n  - Shadow\n  - OtherAlias')):
    metadata = 'title: Other\ndescription: |\n  ---\n  ...\n  %% metadata %%\n' + aliases + '\n'
    other_text = '---\n' + metadata + '---\n# Other\n'
    check('FM-08-' + suffix + ' every alias after scalar delimiters matches PyYAML', m.frontmatter(other_text).get('aliases') == yaml.safe_load(metadata)['aliases'] == ['Shadow', 'OtherAlias'])
target.write_text(base)

# Catalogue block sequences: each leg reads its metadata independently through
# PyYAML. Scalar bytes (including chomping) are compared before identities merge.
def catalogue_yaml(metadata):
    try: return yaml.safe_load(metadata)
    except yaml.YAMLError as error:
        print('PROBE FAILED: catalogue fixture is not valid YAML · ' + str(error))
        sys.exit(2)

catalogue_forms = [
    ('blank', 'aliases:\n  - Existing\n\n  - Shadow', 'Shadow'),
    ('comment', 'aliases:\n  - Existing\n  # between items\n  - Shadow', 'Shadow'),
    ('folded', 'aliases:\n  - Existing\n  - >-\n    Shadow', 'Shadow'),
    ('gapless', 'aliases:\n  - Existing\n  - Shadow', 'Shadow'),
    ('flow', 'aliases: [Existing, Shadow]', 'Shadow'),
    ('literal', 'aliases:\n  - Existing\n  - |\n    Shadow', 'Shadow'),
    ('single-colon', "aliases:\n  - Existing\n  - 'Shadow: name'", 'Shadow: name'),
    ('trailing-comment', 'aliases:\n  - Existing # first\n  - Shadow # last', 'Shadow'),
    ('header-comment', 'aliases: # catalogue\n\n# before first\n  - Existing\n  - Shadow', 'Shadow'),
    ('indentless', 'aliases:\n- Existing\n\n# between\n- Shadow', 'Shadow'),
    ('quoted-escapes', 'aliases:\n  - "Exis' + BS + 'u0074ing"\n  - "Sha' + BS + 'u0064ow" # alias', 'Shadow'),
    ('doubled-quote', "aliases:\n  - Existing\n  - 'Shadow''s name' # alias", "Shadow's name"),
    ('folded-lines', 'aliases:\n  - Existing\n  - >-\n    Shadow\n    name', 'Shadow name'),
    ('folded-paragraph', 'aliases:\n  - Existing\n  - >\n    Shadow\n\n    name\n', 'Shadow name'),
    ('folded-indented', 'aliases:\n  - Existing\n  - >-\n    Shadow\n      detailed\n    name', 'Shadow detailed name'),
    ('literal-keep', 'aliases:\n  - Existing\n  - |+\n    Shadow\n\n', 'Shadow'),
    ('literal-strip', 'aliases:\n  - Existing\n  - |-\n    Shadow\n\n', 'Shadow'),
    ('explicit-indent', 'aliases:\n  - Existing\n  - >2- # indentation\n    Shadow\n    name', 'Shadow name'),
    ('reverse-indicators', 'aliases:\n  - Existing\n  - >-2\n    Shadow\n    name', 'Shadow name'),
    ('scalar-then-item', 'aliases:\n  - >-\n    Existing\n\n  # after scalar\n  - Shadow', 'Shadow'),
]
for label, sequence, identity in catalogue_forms:
    metadata = 'title: Other\ndescription: |\n  ...\n' + sequence + '\nsources:\n  - source-one\n\n  # source gap\n  - source-two\nconfidence: medium\n'
    page = '---\n' + metadata + '---\n# Other\n'
    other_page.write_text(page)
    decoded = m.frontmatter(page)
    oracle = catalogue_yaml(metadata)
    check('CAT-read-' + label + ' aliases and sources equal independent PyYAML', decoded.get('aliases') == oracle['aliases'] and decoded.get('sources') == oracle['sources'] and not getattr(decoded, 'uncertain', []), repr(oracle['aliases']))
    before_artefacts = set(uniondir.iterdir())
    rc, output = outcome(lanes(base, lambda t, identity=identity: t.replace('[GPT-4o]', '[GPT-4o, ' + json.dumps(identity) + ']'), parents[1]))
    check('CAT-collision-' + label + ' manual with zero commands and artefacts', catalogue_yaml(metadata)['aliases'] == oracle['aliases'] and rc == 0 and 'manual GPT' in output and 'multiple existing pages' in output and 'patch -F0' not in output and 'union diff:' not in output and set(uniondir.iterdir()) == before_artefacts, 'commands ' + str(output.count('patch -F0')))
    rc, output = outcome(lanes(base, lambda t: t.replace('[GPT-4o]', '[GPT-4o, UniqueCatalogueControl]'), parents[1]))
    check('CAT-clear-' + label + ' non-colliding alias keeps its union (positive control)', catalogue_yaml(metadata)['aliases'] == oracle['aliases'] and rc == 0 and 'apply-union GPT' in output and output.count('patch -F0') == 2)
    # The same sequence is untouched on the target, exercising strict reads of
    # both keys without widening the single-line append eligibility rule.
    other_page.unlink()
    for field in ('aliases', 'sources'):
        local_sequence = sequence.replace('aliases:', field + ':', 1)
        local_page = base.replace('aliases: [GPT-4o]', local_sequence)
        local_meta = ''.join(local_page.splitlines(keepends=True)[1:independent_offset(local_page.splitlines(keepends=True)) - 1])
        rc, output = outcome(lanes(local_page, *parents))
        check('CAT-local-' + field + '-' + label + ' untouched sequence stays union-eligible', m.frontmatter(local_page).get(field) == catalogue_yaml(local_meta)[field] and rc == 0 and unioned(output, local_page, ['- first', '- second']))

uncertain_forms = [
    ('anchor', '  - &new Shadow', 'anchor', ['Existing', 'Shadow', 'Later']),
    ('tag', '  - !!str Shadow', 'tag', ['Existing', 'Shadow', 'Later']),
    ('reference', '  - *known', 'alias reference', ['Existing', 'Shadow', 'Later']),
    ('double-multiline', '  - "Shadow\n    name"', 'multi-line quoted scalar', ['Existing', 'Shadow name', 'Later']),
    ('single-multiline', "  - 'Shadow\n    name'", 'multi-line quoted scalar', ['Existing', 'Shadow name', 'Later']),
    ('mapping', '  - Shadow: name', 'nested mapping', ['Existing', {'Shadow': 'name'}, 'Later']),
    ('continuation', '  - Shadow\n    name', 'scalar continuation', ['Existing', 'Shadow name', 'Later']),
    ('nested-sequence', '  - [Shadow, name]', 'nested sequence', ['Existing', ['Shadow', 'name'], 'Later']),
    ('implicit', '  - true', 'implicit non-string scalar', ['Existing', True, 'Later']),
    ('empty', '  -', 'empty scalar item', ['Existing', None, 'Later']),
]
for label, item, form, expected in uncertain_forms:
    metadata = 'seed: &known Shadow\naliases:\n  - Existing\n' + item + '\n  - Later\nconfidence: medium\n'
    page = '---\n' + metadata + '---\n# Other\n'
    other_page.write_text(page)
    decoded = m.frontmatter(page)
    issues = getattr(decoded, 'uncertain', [])
    problem_row = '    name' if label == 'continuation' else item.splitlines()[0]
    number = page.splitlines().index(problem_row) + 1
    check('CAT-uncertain-' + label + ' PyYAML-valid form records its field, form and line', catalogue_yaml(metadata)['aliases'] == expected and any(key == 'aliases' and line == number and form in why for key, line, why in issues) and 'Later' in decoded.get('aliases', []))
    before_artefacts = set(uniondir.iterdir())
    rc, output = outcome(lanes(base, lambda t: t.replace('[GPT-4o]', '[GPT-4o, Shadow]'), parents[1]))
    reasons = [row for row in output.splitlines() if row.startswith('  reason:')]
    check('CAT-remote-' + label + ' uncertain identity prevents a silent alias collision', catalogue_yaml(metadata)['aliases'] == expected and rc == 0 and 'manual GPT' in output and any('UNCERTAIN' in row and form in row and 'Other.md' in row and 'line ' + str(number) in row for row in reasons) and 'patch -F0' not in output and 'union diff:' not in output and set(uniondir.iterdir()) == before_artefacts)
    rc, output = outcome(lanes(base, *parents))
    check('CAT-unrelated-' + label + ' body-only union on a known unrelated page is unchanged', catalogue_yaml(metadata)['aliases'] == expected and rc == 0 and unioned(output, base, ['- first', '- second']))
    rc, output = run(rows)
    check('CAT-single-' + label + ' unrelated single-lane plan still applies', catalogue_yaml(metadata)['aliases'] == expected and rc == 0 and 'apply GPT' in output and 'PROBE FAILED:' not in output)
    other_page.unlink()
    for field in ('aliases', 'sources'):
        local_metadata = metadata.replace('aliases:', field + ':', 1)
        local_page = base.replace('aliases: [GPT-4o]\n', local_metadata)
        local_number = local_page.splitlines().index(problem_row) + 1
        rc, output = outcome(lanes(local_page, *parents))
        reasons = [row for row in output.splitlines() if row.startswith('  reason:')]
        check('CAT-touch-' + field + '-' + label + ' union touching uncertain metadata is manual', catalogue_yaml(local_metadata)[field] == expected and rc == 0 and 'manual GPT' in output and any('UNCERTAIN' in row and form in row and field in row and 'line ' + str(local_number) in row for row in reasons) and 'patch -F0' not in output and 'union diff:' not in output)
        rc, output = outcome(lanes(base, lambda t, local_metadata=local_metadata: t.replace('aliases: [GPT-4o]\n', local_metadata), parents[1]))
        check('CAT-proposed-' + field + '-' + label + ' unsupported proposed form also refuses before classification', catalogue_yaml(local_metadata)[field] == expected and rc == 0 and 'manual GPT' in output and 'UNCERTAIN' in output and 'member LA line ' + str(local_number) in output and form in output and 'patch -F0' not in output)
target.write_text(base)

for label, header in (('anchor', '&sequence'), ('tag', '!!seq')):
    for field in ('aliases', 'sources'):
        metadata = field + ': ' + header + '\n  - Existing\n  - Shadow\n'
        page = base.replace('aliases: [GPT-4o]\n', metadata)
        decoded = m.frontmatter(page)
        number = page.splitlines().index(field + ': ' + header) + 1
        check('CAT-header-' + field + '-' + label + ' sequence properties are explicit uncertainty', decoded.get(field) == catalogue_yaml(metadata)[field] and any(key == field and line == number and label in form for key, line, form in getattr(decoded, 'uncertain', [])))
        rc, output = outcome(lanes(page, *parents))
        check('CAT-header-manual-' + field + '-' + label + ' uncertain sequence header prevents union', catalogue_yaml(metadata)[field] == ['Existing', 'Shadow'] and rc == 0 and 'manual GPT' in output and 'UNCERTAIN' in output and label in output and 'line ' + str(number) in output and 'patch -F0' not in output)

# Three rows exercise the beginning, intervening break and ending of a scalar;
# the Cartesian product covers both styles, all listed indicator orders and
# ordinary, empty, more-indented, spaces-only and tab content in each position.
import itertools
scalar_valid = scalar_invalid = scalar_agreed = 0
scalar_mismatches = []
for style, flags, content_rows in itertools.product('|>', ('', '-', '+', '2', '2-', '+2'), itertools.product(('Shadow', 'name', '', '  more', '  ', '\tmore', '\t'), repeat=3)):
    metadata = 'aliases:\n  - ' + style + flags + '\n' + ''.join('    ' + row + '\n' if row else '\n' for row in content_rows) + '  - Tail\n'
    try: expected = yaml.safe_load(metadata)['aliases']
    except yaml.YAMLError:
        scalar_invalid += 1; continue
    scalar_valid += 1
    decoded = m.frontmatter('---\n' + metadata + '---\n')
    if decoded.get('aliases') == expected and not getattr(decoded, 'uncertain', []): scalar_agreed += 1
    else: scalar_mismatches.append((metadata, decoded.get('aliases'), expected))
check('CAT-scalar-matrix every valid scalar equals independent PyYAML exactly', scalar_valid > 0 and scalar_invalid > 0 and scalar_agreed == scalar_valid, f'valid {scalar_valid} · agreed {scalar_agreed} · invalid {scalar_invalid} · mismatches {len(scalar_mismatches)} ' + repr(scalar_mismatches[:1]))
altered = list(expected); altered[0] += 'planted'
check('CAT-scalar-control the same byte comparator detects a changed scalar', altered != expected and scalar_agreed > 0)
target.write_text(base)

def independent_kind(page, text, kinds):
    """Some line with this text lies inside a block of one of these kinds, by the suite's own parse."""
    lines, offset, tokens = independent_tokens(page)
    spans = [(t.map[0] + offset, t.map[1] + offset) for t in tokens if t.type in kinds and t.map]
    return any(start <= i < end for i, line in enumerate(lines) if line.rstrip('\r\n') == text for start, end in spans)

# Sections as the brief defines them: from a heading to the next heading of the same or
# higher level; the innermost section holding a line decides its heading.
nested_sections = key_points('- top\n\n### Sub\n- sub item\n\n#### Deeper\n- deeper item\n')
rows_ = nested_sections.splitlines()
at_ = {text: rows_.index(text) for text in ('## Key Points', '### Sub', '#### Deeper', '## Appears in', '- top', '- sub item', '- deeper item')}
try:
    view_ = m.page_view(nested_sections)
    by_line = {view_.blocks[h].start: h for h in view_.headings}
    kp, sub, deeper = by_line[at_['## Key Points']], by_line[at_['### Sub']], by_line[at_['#### Deeper']]
    sections_ok = (view_.sections[kp] == (at_['## Key Points'] + 1, at_['## Appears in'], at_['### Sub']) and view_.sections[sub] == (at_['### Sub'] + 1, at_['## Appears in'], at_['#### Deeper'])
                   and [view_.section_of(at_[text]) for text in ('- top', '- sub item', '- deeper item')] == [kp, sub, deeper])
except (AttributeError, KeyError, ValueError): sections_ok = False
check('SECTION-01 a section runs to the next heading of the same or higher level; the innermost decides a line', sections_ok)
rc, output = outcome(lanes(nested_sections, after('- top\n', '- first\n'), after('- deeper item\n', '- second\n')))
check('SECTION-02 an addition in a #### sub-section of Key Points belongs to that sub-section: conflict', rc == 0 and 'conflict GPT' in output and 'union diff:' not in output)
rc, output = outcome(lanes(nested_sections, after('- top\n', '- first\n'), after('- top\n', '- second\n')))
check('SECTION-03 additions in the own text of Key Points union above its sub-sections', rc == 0 and unioned(output, nested_sections, ['- first', '- second']) and union_page(output, nested_sections).index('- second\n') < union_page(output, nested_sections).index('### Sub'))

# An item holding only a link reference definition has no block of its own and would
# define a label for the whole page, so it is not a union line.
rc, output = outcome(lanes(base, after('Original.\n', '- [ref-a]: https://example.org/a\n'), parents[1]))
check('REFDEF-01 an added item the parser reads as a link reference definition is not a union line: conflict', rc == 0 and 'conflict GPT' in output and 'union diff:' not in output)
rc, output = outcome(lanes(base, after('Original.\n', '- [ref-a] see the reference\n'), parents[1]))
check('REFDEF-02 the same bracket text as an ordinary item unions', rc == 0 and unioned(output, base, ['- [ref-a] see the reference', '- second']))

# str.splitlines ends a line at a form feed; CommonMark does not, so the two line numberings
# would differ and a union path refuses such a body.
sep_page = base.replace('## Related\n', '## Related\nSee' + chr(12) + 'page break.\n')
rc, output = outcome(lanes(sep_page, *parents))
check('SEP-01 a body line holding a form feed is manual, naming the separator and its page line', rc == 0 and 'manual GPT' in output and 'union placement refused: line separator U+000C at page line' in output and 'patch -F0' not in output)
clean_sep = base.replace('## Related\n', '## Related\nSee page break.\n')
rc, output = outcome(lanes(clean_sep, *parents))
check('SEP-02 the same page without the form feed unions', rc == 0 and unioned(output, clean_sep, ['- first', '- second']))
target.write_text(base)

# The page guard lifted construct by construct (IDEAS №172): for each construct the parser
# now places, a must-fire probe and a must-not-fire probe.
fenced_kp = key_points('- real\n\n```\n- example\n```\n')
rc, output = outcome(lanes(fenced_kp, after('- example\n', '- inside\n'), after('- real\n', '- second\n')))
check('LIFT-01a fence, must fire: an addition inside a fence is manual, naming the fence and the member line', rc == 0 and placed(output, 'fence', 'member LA added line'))
rc, output = outcome(lanes(fenced_kp, after('- real\n', '```\n'), after('- real\n', '- second\n')))
check('LIFT-01b fence, must fire: an added opener that would swallow the lines after it is manual, naming the fence', rc == 0 and placed(output, 'fence', 'member LA added line'))
rc, output = outcome(lanes(fenced_kp, after('- real\n', '- first\n'), after('- real\n', '- second\n')))
check('LIFT-01c fence, must not fire: additions beside the fence union and the fence stays code', rc == 0 and unioned(output, fenced_kp, ['- first', '- second']) and independent_code(union_page(output, fenced_kp), '- example'))
rc, output = outcome(lanes(base, after('Original.\n', '---\n'), parents[1]))
check('LIFT-02a Setext underline, must fire: an added underline turning an existing line into a heading is manual, naming both', rc == 0 and placed(output, 'Setext heading', 'member LA added line') and "'Original.'" in output)
setext_page = base.replace('Original.\n', 'Original.\n\nRejected claims\n---\n- rejected\n')
rc, output = outcome(lanes(setext_page, *parents))
check('LIFT-02b Setext underline, must not fire: an existing Setext sub-heading is placed and parent additions union above it', rc == 0 and unioned(output, setext_page, ['- first', '- second']) and independent_heading(union_page(output, setext_page), 'Rejected claims'))
rule_page = key_points('- one\n\n***\n\n- two\n')
rc, output = outcome(lanes(rule_page, after('- one\n', '- - -\n'), after('- two\n', '- second\n')))
check('LIFT-03a thematic break, must fire: an added "- - -" is a break, not a list item, so the target is no union', rc == 0 and 'conflict GPT' in output and 'union diff:' not in output)
rc, output = outcome(lanes(rule_page, after('- one\n', '- first\n'), after('- two\n', '- second\n')))
check('LIFT-03b thematic break, must not fire: items on either side of a body break union into their own lists', rc == 0 and unioned(output, rule_page, ['- first', '- second']) and independent_kind(union_page(output, rule_page), '***', ('hr',)))
html_page = key_points('- real\n\n<div>\nraw html\n</div>\n')
rc, output = outcome(lanes(html_page, after('raw html\n', '- inside\n'), after('- real\n', '- second\n')))
check('LIFT-04a HTML block, must fire: an addition inside an HTML block is manual, naming the block and the member line', rc == 0 and placed(output, 'HTML block', 'member LA added line'))
rc, output = outcome(lanes(html_page, after('- real\n', '- first\n'), after('- real\n', '- second\n')))
check('LIFT-04b HTML block, must not fire: additions beside the block union and the block keeps its lines', rc == 0 and unioned(output, html_page, ['- first', '- second']) and independent_kind(union_page(output, html_page), 'raw html', ('html_block',)))
rc, output = outcome(lanes(base, after('Original.\n', '-     code-like item\n'), parents[1]))
check('LIFT-05a indented code, must fire: an added item the parser reads as indented code is manual, naming the block', rc == 0 and placed(output, 'indented code block', 'member LA added line'))
code_page = key_points('Original.\n\n    code line\n')
rc, output = outcome(lanes(code_page, after('    code line\n', '- first\n'), after('    code line\n', '- second\n')))
check('LIFT-05b indented code, must not fire: additions after the code block union and the code stays code', rc == 0 and unioned(output, code_page, ['- first', '- second']) and independent_code(union_page(output, code_page), '    code line'))
for ident, marker, family in (('LIFT-06a', '%% note %%', 'Obsidian comment'), ('LIFT-06b', '$$ x $$', 'maths block')):
    rc, output = outcome(lanes(key_points('- real\n\n' + marker + '\n'), after('- real\n', '- first\n'), after('- real\n', '- second\n')))
    check(ident + ' the residue guard still holds ' + family + ': manual, saying the parser cannot place it', rc == 0 and guarded(output, family) and 'not CommonMark, so the parser cannot place it' in output)
target.write_text(base)

# A seeded property check over random pages (IDEAS №172). Pages are built from the
# constructs of the critic probes; two or three members each add one or two lines of
# several shapes anywhere in the body. Every union the planner composes is re-read with the
# suite's own CommonMark pass: (1) each existing line keeps its ancestor blocks, each named
# by the first existing line it holds; (2) each addition keeps its section heading, the
# existing lines of its list and its item's own blocks, as its member's proposal gave them.
# With the planner's existing-line comparison and composed-page oracle switched off, the
# same cases must show a violation: the positive control.
import random
FUZZ_SEED, FUZZ_CASES = 172, 4000  # Seed and case budget: set by judgement, unmeasured.
FUZZ_FLOOR = 25  # Minimum unions for a non-vacuous run: set by judgement, unmeasured.
FUZZ_HEADINGS = [['## Key Points'], ['## Appears in'], ['## Related'], ['## Conflicts / Open Questions'], ['### Sub'], ['# Title'], [' ## Related'], ['   ## Key Points'],
                 ['Key Points', '---'], ['Appears in', '==='], ['## Key Points ##'], ['    ## Key Points']]
FUZZ_CHUNKS = [['Text p.'], ['Text a.', 'Text b.'], ['- item one'], ['- item one', '- item two'], ['* star one', '* star two'], ['1. first', '2. second'],
               ['- parent', '  - child'], ['- parent', '\tcontinued'], ['- parent', '  cont'], ['- parent', NBSP * 2 + 'nbsp cont'], ['- parent', 'lazy'],
               ['- parent', '', '  - spaced child'], ['- parent', '', '  para in item'], ['```', '- example', '```'], ['~~~', '- example', '~~~'],
               ['````', '```', '- example', '```', '````'], ['```'], ['```python', '## Related', '```'], ['- ```', '  inner', '  ```'], ['- a ```'],
               ['~~~~', '~~~', '- inside', '~~~~'], ['    code'], ['', '    code line'], ['<div>', '- inner', '</div>'], ['<!--', '- c', '-->'], ['<div>'],
               ['> q', '> - qi'], ['> q', 'lazy'], ['> ```', '> - quoted', '> ```'], ['***'], ['---'], ['[r]: /u'], ['| a | b |', '|---|---|', '| 1 | 2 |'],
               ['Rejected claims', '---'], ['  ### Indented'], ['- - -'], ['<script>', '- in script', '</script>'], ['<custom-tag>', '- inside custom'],
               ['- outer', '  > quoted in item', '  > - deeper'], ['[multi]: /url', '  "title on next line"'], ['- item', '', '      code in item'],
               ['Text p.', '    indented continuation'], ['- item', '  ```', '  open fence in item'], ['+ plus one'], ['-', '  after empty marker']]
FUZZ_FORMS = ['- add-{}', '- add-{}', '- add-{}', '- **add-{}** gloss', '- add-{} ```', '- [add-{}]: /url', '- # add-{}', '- > add-{}', '-     add-{}',
              '- add-{} <div>', '- <div> add-{}', '- ~~~ add-{}', '- ' + '[' * 2 + 'add-{}' + ']' * 2 + ' — gloss']

def fuzz_split(text):
    rows = text.splitlines(keepends=True)
    offset = independent_offset(rows)
    return rows, offset, INDEPENDENT.parse(''.join(rows[offset:]))

def fuzz_paths(text, ident):
    rows, shift, tokens = fuzz_split(text)
    spans = [(t.type.replace('_open', ''), t.map[0] + shift, t.map[1] + shift) for t in tokens if t.nesting >= 0 and t.type != 'inline' and t.map]
    out = {}
    for index in range(shift, len(rows)):
        if ident[index] is None or not rows[index].strip(' \t\r\n'): continue
        out[ident[index]] = tuple((kind, next((ident[j] for j in range(a, b) if ident[j] is not None and rows[j].strip(' \t\r\n')), None)) for kind, a, b in spans if a <= index < b)
    return out

def fuzz_places(text, ident, wanted):
    rows, shift, tokens = fuzz_split(text)
    heads = [(t.map[1] + shift, t.tag + ' ' + tokens[k + 1].content.strip()) for k, t in enumerate(tokens) if t.type == 'heading_open' and t.level == 0]
    out = {}
    for k, t in enumerate(tokens):
        if t.type != 'list_item_open' or t.level != 1 or rows[t.map[0] + shift].rstrip('\r\n') not in wanted: continue
        line = t.map[0] + shift
        holder = max(j for j in range(k) if tokens[j].type in ('bullet_list_open', 'ordered_list_open') and tokens[j].level == 0)
        a, b = tokens[holder].map[0] + shift, tokens[holder].map[1] + shift
        kids = []
        for u in tokens[k + 1:]:
            if u.type == 'list_item_close' and u.level == 1: break
            if u.level == 2 and u.nesting >= 0 and u.type != 'inline': kids.append(u.type)
        above = [name for end, name in heads if end <= line]
        out.setdefault(rows[line].rstrip('\r\n'), []).append((above[-1] if above else None, frozenset(ident[j] for j in range(a, b) if ident[j] is not None and rows[j].strip(' \t\r\n')), tuple(kids)))
    return out

def fuzz_run(seed, cases):
    rng, stats = random.Random(seed), dict(union=0, refused=0, drift=0, misplaced=0, errors=0)
    for case in range(cases):
        lines = ['---', 'title: GPT', 'type: model', 'confidence: medium', 'aliases: [GPT-4o]', '---', '# GPT', '']
        for _ in range(rng.randint(1, 4)):
            lines += rng.choice(FUZZ_HEADINGS)
            for _ in range(rng.randint(0, 3)):
                if rng.random() < 0.6: lines += [''] * rng.choice((0, 1, 1, 2))
                lines += rng.choice(FUZZ_CHUNKS)
            lines += [''] * rng.choice((0, 1, 1, 2))
        text = '\n'.join(lines) + '\n'
        if rng.random() < 0.1: text = text.rstrip('\n')
        rows = text.splitlines(keepends=True)
        fm = rows.index('---\n', 1)
        items = [i + 1 for i in range(fm + 1, len(rows)) if rows[i].startswith('- ')]
        heads = [i + 1 for i in range(fm + 1, len(rows)) if rows[i].lstrip(' ').startswith('#')]
        names = ['LA', 'LB', 'LC'][:rng.choice((2, 2, 3))]
        added, proposals = {}, {}
        for lane in names:
            new, mine = list(rows), []
            for n in range(rng.choice((1, 1, 2))):
                at = rng.choice(rng.choice((list(range(fm + 1, len(rows) + 1)),) * 2 + ((items or [len(rows)]), (heads or [len(rows)]))))
                mine.append((at, rng.choice(FUZZ_FORMS).format(lane + '-' + str(n)) + '\n'))
            if new and not new[-1].endswith('\n') and any(at == len(rows) for at, _ in mine): new[-1] += '\n'
            for at, line in sorted(mine, reverse=True): new[at:at] = [line]
            added[lane], proposals[lane] = [line for _, line in mine], ''.join(new)
        context = rng.choice((0, 3))
        try:
            members = []
            for lane in names:
                patch = ''.join(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n' for line in difflib.unified_diff(rows, proposals[lane].splitlines(keepends=True), fromfile='a/' + rel, tofile='b/' + rel, n=context))
                parsed = m.parse_diff(patch, vault.resolve())
                members.append({'text': text, 'parsed': parsed, 'changed': m.apply_memory(text, parsed), 'problems': [], 'target': target, 'claim': {'lane': lane}, 'lift': False, 'diff': 'fuzz-' + lane})
        except Exception:
            stats['errors'] += 1; continue  # a member the harness cannot build is its own fault, never a refusal
        try:
            if m.classify(members) != 'apply-union': stats['refused'] += 1; continue
            patch = m.compose_union(members)
        except m.ProbeError:
            stats['refused'] += 1; continue
        except Exception:
            stats['errors'] += 1; continue
        try: union = m.apply_memory(text, m.parse_diff(patch, vault.resolve()))
        except Exception:
            stats['errors'] += 1; continue  # a composed union that does not apply is a defect, never a refusal
        stats['union'] += 1
        every = {line.rstrip('\n') for lane in names for line in added[lane]}
        uid, count = [], 0
        for row in union.splitlines(keepends=True):
            if row.rstrip('\n') in every: uid.append(None)
            else: uid.append(count); count += 1
        if count != len(rows) or fuzz_paths(text, list(range(len(rows)))) != fuzz_paths(union, uid):
            stats['drift'] += 1
        for lane in names:
            own, mid, count = {line.rstrip('\n') for line in added[lane]}, [], 0
            for row in proposals[lane].splitlines(keepends=True):
                if row.rstrip('\n') in own: mid.append(None)
                else: mid.append(count); count += 1
            want, got = fuzz_places(proposals[lane], mid, own), fuzz_places(union, uid, own)
            if any(got.get(key) != want.get(key) for key in own): stats['misplaced'] += 1; break
    return stats

try: fuzz = fuzz_run(FUZZ_SEED, FUZZ_CASES)
except Exception as error: fuzz = dict(union=0, refused=0, drift=-1, misplaced=-1, errors=repr(error))
check('FUZZ-01 the seeded property run composes enough unions to mean something', fuzz['union'] >= FUZZ_FLOOR and fuzz['errors'] == 0, str(fuzz))
check('FUZZ-02 no composed union moves an existing line or an addition out of its member-given blocks', fuzz['union'] >= FUZZ_FLOOR and fuzz['drift'] == 0 and fuzz['misplaced'] == 0, str(fuzz))
try:
    with mock.patch.object(m.Page, 'shapes', lambda self, ids, shared: {}), mock.patch.object(m, 'check_composed', lambda *args, **kwargs: None):
        control = fuzz_run(FUZZ_SEED, FUZZ_CASES)
except Exception as error: control = dict(union=0, refused=0, drift=0, misplaced=0, errors=repr(error))
check('FUZZ-03 positive control: the same cases with the comparison and the oracle switched off show violations', control['drift'] + control['misplaced'] > 0 and control['errors'] == 0, str(control))
target.write_text(base)

# Round one: P and T series.
target.write_text(base)
rc, output = outcome(union_rows(link('source-a'), link('source-b')))
check('P00 ordinary bullets union as list items under their heading', rc == 0 and unioned(output, base, [link('source-a').rstrip(), link('source-b').rstrip()], 'Appears in'))
bare = base[base.index('# GPT'):]
vals = lanes(bare, *two_links)
for i in (2, 6): vals[i]['claims'][0]['confidence'] = ''
rc, output = outcome(vals)
check('P01 a page without frontmatter unions its body additions', rc == 0 and unioned(output, bare, [link('source-a').rstrip(), link('source-b').rstrip()], 'Appears in'))
unclosed = base.replace('---\n# GPT', '# GPT')
rc, output = outcome(lanes(unclosed, *two_links))
check('P02 an unclosed frontmatter exits 2 before planning', rc == 2 and 'PROBE FAILED: frontmatter does not close' in output and 'patch -F0' not in output)
twice = base.replace('## Appears in\n', '## Key Points\n- other\n\n## Appears in\n')
rc, output = outcome(lanes(twice, *parents))
check('P03 a repeated section heading refuses composition: manual', rc == 0 and 'manual GPT' in output and 'heading missing or repeated' in output and 'patch -F0' not in output)
rc, output = outcome(lanes(subpage, after('- parent one\n', '- parent two\n'), after('- parent one\n', '- parent three\n')))
composed = union_page(output, subpage)
check('P04 parent additions stay above the ### subsection', rc == 0 and independent_items(composed, ['- parent two', '- parent three'], 'Key Points'))
rc, output = outcome(lanes(subpage, after('- rejected one\n', '- rejected two\n'), after('- parent one\n', '- parent three\n')))
check('P05 an addition inside the subsection conflicts', rc == 0 and 'conflict GPT' in output)
fenced = key_points('- real\n\n```\n- example\n```\n')
rc, output = outcome(lanes(fenced, after('- example\n', '- inside A\n'), after('- example\n', '- inside B\n')))
check('P06 additions inside a simple fence are refused with the fence named', rc == 0 and placed(output, 'fence'))
rc, output = outcome(lanes(mixed, lambda t: t.replace('audited: 2026-09-20\n', '').replace('## Appears in\n', '## Appears in\n' + link('source-a')), two_links[1]))
check('P07 a stamp removed without a replacement conflicts', rc == 0 and 'conflict GPT' in output)
rc, output = outcome(lanes(base, lambda t: t.replace('aliases: [GPT-4o]\n', 'aliases: [GPT-4o]\nsources: [raw/a.md]\n').replace('## Appears in\n', '## Appears in\n' + link('source-a')), two_links[1]))
check('P08 a sources: list added from nothing conflicts', rc == 0 and 'conflict GPT' in output)
multi = base.replace('aliases: [GPT-4o]\n', 'aliases: [GPT-4o]\nsources:\n  - raw/a.md\n')
rc, output = outcome(lanes(multi, lambda t: t.replace('  - raw/a.md\n', '  - raw/a.md\n  - raw/b.md\n').replace('## Appears in\n', '## Appears in\n' + link('source-a')), two_links[1]))
check('P09 a multiline sources: append conflicts', rc == 0 and 'conflict GPT' in output)
first_quoted = base.replace('[GPT-4o]', '["GPT-4, turbo", GPT-4o]')
rc, output = outcome(lanes(first_quoted, lambda t: t.replace('GPT-4o]', 'GPT-4o, LA-alias]').replace('## Appears in\n', '## Appears in\n' + link('source-a')), lambda t: t.replace('GPT-4o]', 'GPT-4o, LB-alias]').replace('## Appears in\n', '## Appears in\n' + link('source-b'))))
check('P10 a first-position quoted comma item survives an aliases merge', rc == 0 and '+aliases: ["GPT-4, turbo", GPT-4o, LA-alias, LB-alias]' in union_text(output))
rc, output = outcome(lanes(quoted2, lambda t: t.replace('"Foo, shared"]', '"Foo, shared", "Bar, shared"]').replace('## Appears in\n', '## Appears in\n' + link('source-a')), lambda t: t.replace('"Foo, shared"]', '"Foo, shared", "Baz, shared"]').replace('## Appears in\n', '## Appears in\n' + link('source-b'))))
check('P11 later-position quoted comma items survive whole', rc == 0 and '+aliases: ["GPT", "Foo, shared", "Bar, shared", "Baz, shared"]' in union_text(output))
linked = base.replace('## Appears in\n', '## Appears in\n' + link('existing'))
rc, output = outcome(lanes(linked, after(link('existing'), '- \n'), after(link('existing'), link('source-b'))))
check('P12 an empty dash-space item is no union line: conflict', rc == 0 and 'conflict GPT' in output)
rc, output = outcome(lanes(linked, after(link('existing'), '-\n'), after(link('existing'), link('source-b'))))
check('P13 a lone dash after a list item is an empty item: conflict', rc == 0 and 'conflict GPT' in output)
rc, output = outcome(lanes(base, after('Original.\n', '-\n'), parents[1]))
check('P13b a lone dash under a paragraph is a Setext underline: manual with the construct named', rc == 0 and placed(output, 'Setext heading'))
vals = lanes(base, *two_links)
target.write_bytes(base.replace('\n', '\r\n').encode())
rc, output = outcome(vals)
check('P14 a CRLF page with LF member diffs fails closed: manual, no union', rc == 0 and 'manual GPT' in output and not union_text(output) and 'patch -F0' not in output)
target.write_text(base)
vals = lanes(mixed, lambda t: t.replace('audited: 2026-09-20', 'audited: 2026-09-22').replace('Original.\n', 'Original.\n- first\n'), parents[1])
first_hunk = m.parse_diff(Path(vals[2]['claims'][0]['diff']).read_text(), vault.resolve())['hunks'][0][0]
rc, output = outcome(vals)
check('P15 a hunk starting inside the frontmatter unions its stamp and its item', first_hunk < mixed.splitlines().index('---', 1) and rc == 0 and '+audited: 2026-09-22' in union_text(output) and unioned(output, mixed, ['- first', '- second']))
rc, output = outcome(lanes(base, lambda t: t.replace('confidence: medium', 'confidence: high').replace('## Appears in\n', '## Appears in\n' + link('source-a')), two_links[1]))
check('P16 a confidence edit beside a bullet is tier-raised and composes no union', rc == 0 and 'tier-raised GPT' in output and 'union diff:' not in output)
older = base.replace('Original.', 'Older text.')
vals = lanes(base, *two_links)
stale = root / 'P17-stale.diff'; make_diff(stale, older, older.replace('## Appears in\n', '## Appears in\n' + link('source-b')))
vals[6]['claims'][0].update(base=m.digest(older.encode()), diff=str(stale), diff_hash=m.digest(stale.read_bytes()))
rc, output = outcome(vals)
check('P17 members on different bases refuse composition: manual', rc == 0 and 'manual GPT' in output and 'patch -F0' not in output)
rc, output = outcome(lanes(mixed, lambda t: t.replace('audited: 2026-09-20', 'audited: 2026-09-22').replace('aliases: [GPT-4o]\n', 'aliases: [GPT-4o]\nupdated: 2026-09-22\n').replace('## Appears in\n', '## Appears in\n' + link('source-a')), two_links[1]))
composed = union_page(output, mixed)
check('P18 mixed missing and existing stamps compose one row each at the latest date', rc == 0 and composed.count('audited:') == 1 and 'audited: 2026-09-22' in composed and composed.count('updated:') == 1 and m.frontmatter(composed).get('audited') == '2026-09-22')
rc, output = outcome(lanes(mixed, lambda t: t.replace('audited: 2026-09-20', 'audited: 2026-09-22'), lambda t: t.replace('audited: 2026-09-20', 'audited: 2026-09-23')))
check('P19 stamp-only members are not a union: manual', rc == 0 and 'manual GPT' in output)
rc, output = outcome(lanes(base, after('Original.\n', '- **Fact A.** one source.\n'), after('Original.\n', '- **Fact A.** one source\n')))
check("P20 near-duplicate facts both survive for the head's read", rc == 0 and unioned(output, base, ['- **Fact A.** one source.', '- **Fact A.** one source']))
rc, output = outcome(lanes(mixed, lambda t: t.replace('audited: 2026-09-20', 'audited: 2026-01-01').replace('## Appears in\n', '## Appears in\n' + link('source-a')), two_links[1]))
check('P21 a backdated stamp keeps the page date', rc == 0 and 'apply-union GPT' in output and 'audited:' not in union_text(output).replace(' audited:', ''))
rc, output = outcome(lanes(mixed, lambda t: t.replace('audited: 2026-09-20', 'audited: 2026-99-99').replace('## Appears in\n', '## Appears in\n' + link('source-a')), two_links[1]))
check('P22 an invalid calendar date conflicts', rc == 0 and 'conflict GPT' in output)
try: m.planted(); planted_ok = True
except Exception: planted_ok = False
check('P23 planted() controls pass', planted_ok)
target.write_text(base)

verify_text = (here.parent / 'delegate/templates/brief-ingest-verify.md').read_text()
revised = 'shape: fail' in verify_text and 'scores `claims 1`' not in verify_text and 'names the compile lane' not in verify_text and 'name the compile lane' in verify_text and '- Compile report:' in verify_text
check('T01 the revised verifier-consumer predicate passes and the retired one fails', revised and not ('scores `claims 1`' in verify_text and 'names the compile lane' in verify_text))
import ast
# sha256[:16] of each definition's source text in the planner shipped on 2026-09-15: the
# ledger, evidence, diff, patch and write core that the union work never touches. A change
# to one of these is deliberate and updates its digest here.
SHIPPED_CORE = {'Catalogue': '9be31e6270feb7c8', 'ProbeError': 'f7863de8dea489f7', 'apply_memory': 'db7e9d2454c36164', 'base_problem': '0a9d262eab81f769', 'before': '141cb4a53736e8dd', 'claim_name': '9c62d49eef6d47d1', 'claims_from': '7cba20831c7483eb', 'diff_problem': '2a5ccabcc4cf5753', 'digest': '8806915ea38cdfc8', 'emit_union': '90eb985663c10d8b', 'evidence': 'a1c23c50488654f2', 'header_path': 'f484ba85ed622f1c', 'json_type': '7364b307a83b7a86', 'normalise': '43e9f98f9efa0cb9', 'normalise_link_line': 'a0b540108bcd0b8e', 'parse_diff': 'aad3616cf63623cb', 'patch_command': 'f02d7cbe5edf46ef', 'read_events': 'aec96bff180e8f58', 'reference_ids': '01c264e34b47d9b2', 'scalar': 'a5ac5e47b8b7aeb0', 'score_values': 'aa0f9c570ca9c34f', 'timestamp': '3f8343f07f595978'}
source_lines = script.read_text().split('\n')
found = {node.name: hashlib.sha256('\n'.join(source_lines[node.lineno - 1:node.end_lineno]).encode()).hexdigest()[:16] for node in ast.parse('\n'.join(source_lines)).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
same = [name for name, value in SHIPPED_CORE.items() if found.get(name) == value]
check('T03 the ledger, evidence, diff and write core is the shipped code', len(same) == len(SHIPPED_CORE), f'{len(same)} of {len(SHIPPED_CORE)} definitions match')
lifted = union_rows(link('source-a'), link('source-b'))
for i in (2, 6): lifted[i]['claims'][0]['confidence'] = 'high'
rc, output = outcome(lifted)
check('T04 a claim-field lift on a union-eligible target is composed and held with no command', rc == 0 and 'tier-raised GPT' in output and 'held until the full-page read:' in output and 'patch -F0' not in output)
shaped = copy.deepcopy(rows); shaped[-1]['shape'] = 'fail'
rc, output = run(shaped)
check('T05 shape: fail prints its note and keeps the apply', rc == 0 and 'apply GPT' in output and 'note: LA · the verifier recorded a claims-shape evidence failure' in output)
counted = copy.deepcopy(rows); counted[-1]['scores'] = scores.replace('claims 0', 'claims 1')
rc, output = run(counted)
check('T06 a claims count with no object exits 2 without commands', rc == 2 and 'claims count differs' in output and 'patch -F0' not in output)
scoped = copy.deepcopy(counted); scoped[-1]['quarantined'] = [{'name': 'GPT', 'lane': 'LA', 'scope': 'fact 5 only'}]
rc, output = run(scoped)
check('T07 a scope selector on a quarantine object exits 2 without commands', rc == 2 and 'unknown quarantine selector field' in output and 'patch -F0' not in output)
rc, output = outcome(union_rows(link('source-a'), link('source-b'), '# GPT'))
check('T08 links under a non-union heading conflict', rc == 0 and 'conflict GPT' in output)
rc, output = outcome(union_rows('Prose A.\n', 'Prose B.\n', 'Original.'))
check('T09 prose from two lanes conflicts', rc == 0 and 'conflict GPT' in output)
removing = union_rows(link('source-a'), link('source-b'))
bpath = root / 'T10-removing.diff'; make_diff(bpath, base, base.replace('## Appears in\n', '## Appears in\n' + link('source-b')).replace('Original.\n', ''))
removing[6]['claims'][0].update(diff=str(bpath), diff_hash=m.digest(bpath.read_bytes()))
rc, output = outcome(removing)
check('T10 a removed body line conflicts', rc == 0 and 'conflict GPT' in output)
rc, output = outcome(lanes(quoted2, lambda t: t.replace('"Foo, shared"]', '"Foo, shared", "Bar, shared"]').replace('Original.\n', 'Original.\n- first\n'), lambda t: t.replace('"Foo, shared"]', '"Foo, shared", "Baz, shared"]')))
row_text = next((line for line in union_page(output, quoted2).splitlines() if line.startswith('aliases: ')), 'aliases: ')
try: decoded = json.loads(row_text.split(': ', 1)[1])
except ValueError: decoded = None
check('T11 the merged quoted list decodes independently to all four aliases', rc == 0 and decoded == ['GPT', 'Foo, shared', 'Bar, shared', 'Baz, shared'])
rc, output = outcome(lanes(mixed, lambda t: t.replace('audited: 2026-09-20', 'audited: 2026-09-22').replace('aliases: [GPT-4o]\n', 'aliases: [GPT-4o]\nupdated: 2026-09-22\n').replace('Original.\n', 'Original.\n- first\n'), parents[1]))
composed = union_page(output, mixed)
check('T12 one audited row and one updated row, at the latest dates', rc == 0 and composed.count('audited:') == 1 and composed.count('updated:') == 1 and 'audited: 2026-09-22' in composed)
t13 = key_points('- real one\n\n```\n- example one\n```\n')
rc, output = outcome(lanes(t13, after('- real one\n', '- example one\n'), after('- real one\n', '- real two\n')))
composed = union_page(output, t13)
check("T13 a bullet sharing a fenced line's text survives de-duplication and the fence stays code", rc == 0 and independent_items(composed, ['- example one', '- real two'], 'Key Points') and independent_code(composed, '- example one'))
llama = vault / 'wiki/models/Llama.md'; llama.write_text(base.replace('GPT', 'Llama').replace('aliases: [GPT-4o]', 'aliases: [Llama-3]'))
rc, output = outcome(lanes(base, lambda t: t.replace('aliases: [GPT-4o]', 'aliases: [GPT-4o, Llama]').replace('## Appears in\n', '## Appears in\n' + link('source-a')), two_links[1]))
llama.unlink()
check('T14 an appended alias naming an existing page is manual', rc == 0 and 'manual GPT' in output and 'multiple existing pages' in output)
vals = lanes(base.replace('\n', '\r\n'), lambda t: t.replace('## Appears in\r\n', '## Appears in\r\n' + link('source-a').replace('\n', '\r\n')), lambda t: t.replace('## Appears in\r\n', '## Appears in\r\n' + link('source-b').replace('\n', '\r\n')))
target.write_text(base)
rc, output = outcome(vals)
check('T15 CRLF member diffs against an LF page fail closed: manual, no union', rc == 0 and 'manual GPT' in output and not union_text(output) and 'patch -F0' not in output)
target.write_text(base)

# Round two: the N series.
eof_open = base[:base.index('## Key Points')] + '## Key Points\n- real\n```\n- code\n'
rc, output = outcome(lanes(eof_open, after('- real\n', '- first\n'), after('- real\n', '- second\n')))
check('N01a an unclosed EOF fence is placed: parent additions union above it', rc == 0 and unioned(output, eof_open, ['- first', '- second']) and independent_code(union_page(output, eof_open), '- code'))
rc, output = outcome(lanes(eof_open, after('- code\n', '- inside\n'), after('- real\n', '- second\n')))
check('N01b an addition inside an unclosed EOF fence is refused with the fence named', rc == 0 and placed(output, 'fence'))
tilde = key_points('- real\n\n~~~\n- example\n~~~\n')
rc, output = outcome(lanes(tilde, after('- example\n', '- inside\n'), after('- real\n', '- second\n')))
check('N02 an addition inside a tilde fence is refused with the fence named', rc == 0 and placed(output, 'fence'))
rc, output = outcome(lanes(fenced, lambda t: t.replace('```\n- example', '```\n- opened\n- example', 1), after('- real\n', '- second\n')))
check('N03 an addition right under an opener held in the hunk context is refused', rc == 0 and placed(output, 'fence'))
quoted_fence = key_points('- real\n\n> ```\n> - quoted\n> ```\n')
rc, output = outcome(lanes(quoted_fence, after('- real\n', '- first\n'), after('- real\n', '- second\n')))
check('N04 fence lines inside a blockquote are placed: ordinary bullets union', rc == 0 and unioned(output, quoted_fence, ['- first', '- second']))
eof_closed = eof_open + '```\n'
rc, output = outcome(lanes(eof_closed, after('- real\n', '- first\n'), after('- real\n', '- second\n')))
check('N05 a closed EOF fence is placed: parent additions union', rc == 0 and unioned(output, eof_closed, ['- first', '- second']))
adjacent = base.replace('Original.\n', '```\n- code\n```\n- anchor\n')
composed_pair = []
for ident, context in (('N06a', 0), ('N06b', 3)):
    rc, output = outcome(lanes(adjacent, lambda t: t.replace('- anchor\n', '- first\n- anchor\n'), lambda t: t.replace('- anchor\n', '- second\n- anchor\n'), context=context))
    composed_pair.append(union_page(output, adjacent))
    check(ident + ' an insertion right after a closing fence unions with ' + str(context) + ' context lines', rc == 0 and unioned(output, adjacent, ['- first', '- second']))
check('N06c both context widths compose the same page', bool(composed_pair[0]) and composed_pair[0] == composed_pair[1])
for ident, outer in (('N07', '````'), ('N08', '~~~')):
    nest = key_points('- real\n\n' + outer + '\n```\n- example\n```\n' + outer + '\n')
    rc, output = outcome(lanes(nest, after('- example\n', '- escaped\n'), after('- real\n', '- second\n')))
    check(ident + ' an example inside a ' + outer + ' fence stays fenced: the addition there is refused', rc == 0 and placed(output, 'fence'))
top_heading = key_points('- parent one\n\nClosing paragraph.\n  ### Rejected claims\n- rejected one\n')
rc, output = outcome(lanes(top_heading, after('- parent one\n', '- first\n'), after('- parent one\n', '- second\n')))
composed = union_page(output, top_heading)
check('N09 parent additions precede a two-space-indented subsection', rc == 0 and independent_items(composed, ['- first', '- second'], 'Key Points') and composed.index('- second\n') < composed.index('  ### Rejected claims'))
held_heading = key_points('- parent one\n\n  ### Rejected claims\n- rejected one\n')
rc, output = outcome(lanes(held_heading, after('- parent one\n', '- first\n'), after('- parent one\n', '- second\n')))
check("N09b that heading after a list item and a blank line is the item's own: an addition beside it is refused", rc == 0 and placed(output, 'list item', 'Rejected claims'))
page = base.replace('[GPT-4o]', "[O'Brien]")
rc, output = outcome(lanes(page, lambda t: t.replace("[O'Brien]", "[O'Brien, First]"), lambda t: t.replace("[O'Brien]", "[O'Brien, Second]")))
check('N10 an apostrophe within a plain item unions', rc == 0 and "+aliases: [O'Brien, First, Second]" in union_text(output))
blank_list = base.replace('[GPT-4o]', '[  ]')
rc, output = outcome(lanes(blank_list, lambda t: t.replace('[  ]', '[First]').replace('Original.\n', 'Original.\n- first\n'), lambda t: t.replace('[  ]', '[Second]')))
check('N11 a whitespace-only list reads as empty and grows by union', split_items('  ') == [] and rc == 0 and '+aliases: [First, Second]' in union_text(output))
check('N12 opposite nested quotes survive the list splitter', split_items('"first, item", ' + "'second \"nested, quote\"'") == ['"first, item"', "'second \"nested, quote\"'"])
check('N13 doubled single quotes survive the list splitter', split_items("'O''Brien, fourth', plain") == ["'O''Brien, fourth'", 'plain'])
escaped_items = ['Foo "common, suffix"', 'Bar "common, suffix"']
check('N14 escaped double quotes never split an item', split_items(', '.join(json.dumps(item) for item in escaped_items)) == [json.dumps(item) for item in escaped_items])
rc, output = outcome(lanes(base, lambda t: t.replace('confidence: medium\n', 'confidence: medium\nupdated: 2026-09-21\naudited: 2026-09-21\n').replace('Original.\n', 'Original.\n- first\n'), lambda t: t.replace('confidence: medium\n', 'confidence: medium\nupdated: 2026-09-22\naudited: 2026-09-22\n').replace('Original.\n', 'Original.\n- second\n')))
composed = union_page(output, base)
check('N15 two missing stamps are inserted once each at the latest date', rc == 0 and composed.count('updated:') == 1 and composed.count('audited:') == 1 and 'updated: 2026-09-22' in composed and 'audited: 2026-09-22' in composed)
anchorless = base.replace('confidence: medium\n', '')
vals = lanes(anchorless, lambda t: t.replace('aliases: [GPT-4o]\n', 'aliases: [GPT-4o]\naudited: 2026-09-22\n').replace('Original.\n', 'Original.\n- first\n'), parents[1])
for i in (2, 6): vals[i]['claims'][0]['confidence'] = ''
rc, output = outcome(vals)
check('N16 a stamp with no confidence line to follow refuses composition: manual', rc == 0 and 'manual GPT' in output and 'no confidence line' in output)
commented = base.replace('confidence: medium\n', 'confidence: medium\naudited: 2026-09-20 # checked\n')
rc, output = outcome(lanes(commented, lambda t: t.replace('2026-09-20 # checked', '2026-09-22 # checked').replace('Original.\n', 'Original.\n- first\n'), parents[1]))
check('N17 an edited stamp carrying a comment conflicts', rc == 0 and 'conflict GPT' in output)
lifted = union_rows(link('source-a'), link('source-b'))
for i in (2, 6): lifted[i]['claims'][0]['confidence'] = 'high'
target.write_text(base)
rc, held = outcome(lifted)
args = release_args(held)
released_rc, released = release(args) if args else (1, '')
check('N18 the printed held-union release keeps both members', rc == released_rc == 0 and released.count('patch -F0') == 2 and all(name in union_text(held) for name in ('source-a', 'source-b')))
target.write_text(base.replace('## Appears in', '## Citations'))
rc, output = release(args) if args else (1, '')
target.write_text(base)
check('N19 a changed held-union context exits 2 with no command', rc == 2 and 'patch -F0' not in output)
substituted = list(args)
if '--resolved' in substituted: substituted[substituted.index('--resolved') + 1] = lifted[2]['claims'][0]['diff']
rc, output = release(substituted) if substituted else (1, '')
bare_rc, bare_out = resolution([lifted[2]['claims'][0]['diff']])
check('N20 a member diff put in place of the held union is refused; the bare reviewed-diff route stays', rc == 2 and 'held' in output and 'patch -F0' not in output and bare_rc == 0 and bare_out.count('patch -F0') == 2)
rc, output = resolution([diff, nodiff])
check('N21 a valid then invalid resolution batch prints no command', rc == 2 and 'patch -F0' not in output)
captured = io.StringIO()
try:
    with mock.patch.object(m, 'apply_memory', moved_after_read), contextlib.redirect_stdout(captured):
        code = m.main(['--vault', str(vault), '--resolved', str(diff)])
finally: target.write_text(base)
check('N22 a base changed after the resolution read fails closed', code == 2 and 'base moved during planning' in captured.getvalue() and 'patch -F0' not in captured.getvalue())
rc, output = outcome(lanes(base, lambda t: t.replace('[GPT-4o]', '[GPT-4o, GPT]'), lambda t: t.replace('## Related\n', '## Related\n- ordinary\n')))
check('N23 an alias naming its own page unions', rc == 0 and 'apply-union GPT' in output)
fresh = '---\ntitle: Newthing\ntype: model\nconfidence: low\naliases: []\n---\n# Newthing\n## Definition\nD.\n## Key Points\nK.\n## Appears in\n## Related\n'
fresh_diff = root / 'N24-create.diff'; make_diff(fresh_diff, '', fresh, oldpath='/dev/null', newpath='b/wiki/models/Newthing.md')
update_diff = root / 'N24-update.diff'; make_diff(update_diff, base, base.replace('[GPT-4o]', '[GPT-4o, Newthing]'))
update_claim = copy.deepcopy(claim); update_claim.update(diff=str(update_diff), diff_hash=m.digest(update_diff.read_bytes()))
fresh_claim = copy.deepcopy(create_claim); fresh_claim.update(name='Newthing', target='Newthing', diff=str(fresh_diff), diff_hash=m.digest(fresh_diff.read_bytes()))
rc, output = outcome([event('run_open', 0, inbox=[])] + cycle('LA', claims=[update_claim]) + cycle('LB', claims=[fresh_claim]))
check('N24 an appended alias naming a same-run create conflicts', rc == 0 and 'conflict GPT' in output)
other_page.write_text(plain_other.replace('aliases: [Other-4o]', 'aliases: [Other, "Foo, shared"]'))
rc, output = outcome(lanes(base, lambda t: t.replace('[GPT-4o]', '[GPT-4o, "Foo, shared"]'), lambda t: t.replace('## Related\n', '## Related\n- ordinary\n')))
other_page.unlink()
check('N25 an existing quoted alias with a comma collides with the same appended alias', rc == 0 and 'manual GPT' in output and 'multiple existing pages' in output)
mixed_fence = base.replace('Original.\n', '- real\n~~~\n```\n- example\n```\n~~~\n')
rc, output = outcome(lanes(mixed_fence, after('- example\n', '- inserted\n'), after('- real\n', '- ordinary\n')))
check('N26 the full planner refuses the mixed-fence example with the fence named', rc == 0 and placed(output, 'fence'))
items = ['Foo "common, suffix"', 'Bar "common, suffix"', 'Baz "common, suffix"']
page = base.replace('[GPT-4o]', json.dumps(items[:1]))
rc, output = outcome(lanes(page, lambda t: t.replace(json.dumps(items[:1]), json.dumps(items[:2])), lambda t: t.replace(json.dumps(items[:1]), json.dumps([items[0], items[2]]))))
row_text = next((line for line in union_page(output, page).splitlines() if line.startswith('aliases: ')), 'aliases: ')
try: decoded = json.loads(row_text.split(': ', 1)[1])
except ValueError: decoded = None
check('N27 an escaped-quote list unions and decodes independently', rc == 0 and decoded == items)
page = base.replace('Original.\n', '```yaml\naliases: [Sample]\n```\n')
rc, output = run(two_lane_rows(page, [lambda t: t.replace('aliases: [Sample]', 'aliases: [Other]')], names=('LA',)))
check('N28 an aliases: example in a body fence adds no alias: the single-lane update applies', rc == 0 and 'apply GPT' in output and output.count('patch -F0') == 2)
rc, output = outcome(lanes(conf, after('- **Open one.** first.\n', '- **Open two.** second.\n'), after('- **Open one.** first.\n', '- **Open three.** third.\n')))
check('N29 Conflicts / Open Questions bullets union', rc == 0 and unioned(output, conf, ['- **Open two.** second.', '- **Open three.** third.'], 'Conflicts / Open Questions'))
target.write_text(base)
rc, output = resolution([raised])
read_args = release_args(output)
held_ok = rc == 0 and 'held until the full-page read:' in output and 'patch -F0' not in output
rc, output = release(read_args) if read_args else (1, '')
check('N30 a resolution-introduced lift is held, then released by its bound acknowledgement', held_ok and rc == 0 and output.count('patch -F0') == 2)

# Round three: the R series.
info = key_points('- real\n\n```python\n- example\n```\n')
rc, output = outcome(lanes(info, after('- example\n', '- inside\n'), after('- real\n', '- second\n')))
check('R01 an addition inside a fence with an info string is refused with the fence named', rc == 0 and placed(output, 'fence'))
marker_item = key_points('- real\n- ```\n  inner\n  ```\n')
rc, output = outcome(lanes(marker_item, after('- real\n', '- first\n'), after('- real\n', '- second\n')))
check('R02 a fence opened on a list-marker line is placed: parent additions union', rc == 0 and unioned(output, marker_item, ['- first', '- second']) and independent_code(union_page(output, marker_item), '  inner'))
framed = base.replace('Original.\n', 'Original.\n' + attack)
rc, output = outcome(lanes(framed, after('- middle example\n', '- fictional A\n'), after('- middle example\n', '- fictional B\n')))
check('R03 additions inside the list-framed top-level fence are refused with the fence named', rc == 0 and placed(output, 'fence'))
short_close = key_points('- real\n\n~~~~\n- example\n~~~\n- still inside\n~~~~\n')
rc, output = outcome(lanes(short_close, after('- still inside\n', '- inside\n'), after('- real\n', '- second\n')))
check('R04 a shorter tilde marker does not close the fence: the addition inside is refused', rc == 0 and placed(output, 'fence'))
long_close = key_points('- real\n\n~~~\n- example\n~~~~~\n')
rc, output = outcome(lanes(long_close, after('- real\n', '- first\n'), after('- real\n', '- second\n')))
check('R04b a longer closing marker closes the fence: ordinary additions union', rc == 0 and unioned(output, long_close, ['- first', '- second']))
fenced_heading = base.replace('Original.\n', '- real\n~~~\n## Related\n### Example\n- code\n~~~\n')
rc, output = outcome(lanes(fenced_heading, after('- real\n', '- first\n'), after('- real\n', '- second\n')))
check('R05 a heading inside a fence is code: parent additions union above the fence', rc == 0 and unioned(output, fenced_heading, ['- first', '- second']))
no_newline = base[:base.index('## Key Points')] + '## Key Points\n- real\n```\n- code\n```'
rc, output = outcome(lanes(no_newline, after('- real\n', '- first\n'), after('- real\n', '- second\n')))
check('R06 a closing fence at EOF without a newline unions and keeps that EOF', rc == 0 and unioned(output, no_newline, ['- first', '- second']) and union_page(output, no_newline).endswith('\n```'))
yaml_only = base.replace('[GPT-4o]', "['O''Brien', plain]")
rc, output = outcome(lanes(yaml_only, lambda t: t.replace('plain]', 'plain, First]').replace('Original.\n', 'Original.\n- first\n'), lambda t: t.replace('plain]', 'plain, Second]')))
check('R07 single-quoted and plain YAML items decode and merge', rc == 0 and m.frontmatter(union_page(output, yaml_only)).get('aliases') == ["O'Brien", 'plain', 'First', 'Second'])
check('R08 an empty flow list reads as empty', m.frontmatter('---\naliases: []\n---\n').get('aliases') == [] and split_items('') == [])
empty_list = base.replace('[GPT-4o]', '[]')
rc, output = outcome(lanes(empty_list, lambda t: t.replace('[]', '[First]').replace('Original.\n', 'Original.\n- first\n'), lambda t: t.replace('[]', '[Second]')))
check('R08b an empty list grows by union', rc == 0 and '+aliases: [First, Second]' in union_text(output))
rc, output = outcome(lanes(base.replace('[GPT-4o]', '[Alpha,]'), *parents))
check('R09 a trailing-comma list is refused for the union: manual', rc == 0 and 'manual GPT' in output and 'union list refused:' in output)
for ident, item, expected in (('R10', 'C#', 'apply-union GPT'), ('R10b', '"x # y"', 'apply-union GPT'), ('R10c', 'new #note', 'manual GPT')):
    rc, output = outcome(lanes(base, lambda t, item=item: t.replace('[GPT-4o]', '[GPT-4o, ' + item + ']'), parents[1]))
    check(ident + ' a hash in ' + item + (' is refused as comment syntax' if expected.startswith('manual') else ' is kept'), rc == 0 and expected in output and (item in union_text(output) if expected.startswith('apply') else 'union list refused:' in output))
target.write_text(base)
rc, held = outcome(lifted)
args = release_args(held)
target.write_text(drifted_title)
rc, output = release(args) if args else (1, '')
target.write_text(base)
check('R11 a stale acknowledgement after a page change outside the hunk exits 2', rc == 2 and 'patch -F0' not in output)
foreign_hash = next((p.name.rsplit('-', 1)[1][:-len('.diff')] for p in sorted(uniondir.glob('gpt-*.diff')) if args and p.name not in ' '.join(args)), None)
swapped = list(args)
if foreign_hash and '--after-read' in swapped:
    swapped[swapped.index('--after-read') + 1] = swapped[swapped.index('--after-read') + 1].split(':')[0] + ':' + foreign_hash
rc, output = release(swapped) if foreign_hash else (1, '')
check("R12 another artefact's hash from the same run exits 2", foreign_hash is not None and rc == 2 and 'patch -F0' not in output)
first_rc, _ = release(args) if args else (1, '')
second_rc, _ = release(args) if args else (1, '')
held_path = Path(args[args.index('--resolved') + 1]) if '--resolved' in args else None
applied = subprocess.run(shlex.split(m.patch_command(vault, target, held_path, root / 'R13.rej', False)), text=True, capture_output=True) if held_path else None
third_rc, third = release(args) if args else (1, '')
target.write_text(base)
check('R13 releases repeat while bytes stand still; after the apply the release fails', first_rc == second_rc == 0 and applied is not None and applied.returncode == 0 and third_rc == 2 and 'patch -F0' not in third)
example_page = base.replace('aliases: [GPT-4o]\n', 'aliases:\n  - GPT-4o\n').replace('Original.\n', 'Original.\n\n```yaml\naliases:\n  - Sample\n```\n')
other_page.write_text(plain_other.replace('[Other-4o]', '[Other-alias]'))
rc, output = run(two_lane_rows(example_page, [lambda t: t.replace('  - Sample\n', '  - Sample\n  - Other\n')], names=('LA',)))
check('R14 a body example list adds no catalogue alias: the update applies', rc == 0 and 'apply GPT' in output)
open_list = base.replace('aliases: [GPT-4o]', 'aliases: [GPT-4o').replace('Original.\n', 'Original.\nOther]\n')
rc, output = run(two_lane_rows(open_list, [after('Original.\n', 'Added.\n')], names=('LA',)))
check('R15 body text cannot complete a frontmatter list: the single-lane update applies', rc == 0 and 'apply GPT' in output and m.frontmatter(open_list).get('aliases') == ['GPT-4o'])
unicode_alias = '"Foo' + BS + 'u0020shared"'
for ident, spelling in (('R16', 'aliases:\n  - ' + unicode_alias), ('R16b', 'aliases: [' + unicode_alias + ']')):
    other_page.write_text(plain_other.replace('aliases: [Other-4o]', spelling))
    rc, output = outcome(lanes(base, lambda t: t.replace('[GPT-4o]', '[GPT-4o, "Foo shared"]'), parents[1]))
    check(ident + ' block and flow Unicode aliases decode alike and collide', rc == 0 and 'manual GPT' in output and 'multiple existing pages' in output)
other_page.unlink()
setext_sub = base.replace('Original.\n', 'Original.\n\nRejected claims\n---\n- rejected\n')
rc, output = outcome(lanes(setext_sub, *parents))
check('R17 a Setext subsection is placed: parent additions union above it', rc == 0 and unioned(output, setext_sub, ['- first', '- second']) and independent_heading(union_page(output, setext_sub), 'Rejected claims'))
other_page.write_text(plain_other.replace('[Other-4o]', '[Alpha,]'))
target.write_text(base)
rc, output = run(rows)
check('R18 an unrelated trailing-comma page cannot abort a plan', rc == 0 and 'apply GPT' in output and 'PROBE FAILED:' not in output)
other_page.unlink()

# Round four: the S series.
refdef = key_points('- a\n\n[ref]: https://example.org\n')
rc, output = outcome(lanes(refdef, after('- a\n', '- first\n'), after('- a\n', '- second\n')))
check('S01 a link reference definition leaves the added bullets top-level list items', rc == 0 and unioned(output, refdef, ['- first', '- second']))
code_after = key_points('Original.\n\n    code line\n')
rc, output = outcome(lanes(code_after, after('    code line\n', '- first\n'), after('    code line\n', '- second\n')))
check('S02 indented code after a paragraph stays code; bullets after it union', rc == 0 and unioned(output, code_after, ['- first', '- second']) and independent_code(union_page(output, code_after), '    code line'))
rc, output = outcome(lanes(code_after, *parents))
check('S02b a bullet above the blank line would take the indented code into its item: manual', rc == 0 and placed(output, 'list item', 'code line'))
table = key_points('| a | b |\n|---|---|\n| 1 | 2 |\n')
rc, output = outcome(lanes(table, after('| 1 | 2 |\n', '- first\n'), after('| 1 | 2 |\n', '- second\n')))
check('S03 a table stays whole and the bullets after it union', rc == 0 and unioned(output, table, ['- first', '- second']))
lazy_quote = key_points('> quoted\nlazy line\n')
rc, output = outcome(lanes(lazy_quote, after('lazy line\n', '- first\n'), after('lazy line\n', '- second\n')))
check('S04 a lazy blockquote line stays quoted; the bullets stay outside it', rc == 0 and unioned(output, lazy_quote, ['- first', '- second']))
footnote = key_points('Text.[^1]\n\n[^1]: A note.\n')
rc, output = outcome(lanes(footnote, after('[^1]: A note.\n', '- first\n'), after('[^1]: A note.\n', '- second\n')))
check('S05 a footnote definition and the ordinary bullets stay separate', rc == 0 and unioned(output, footnote, ['- first', '- second']))
callout = key_points('> [!note] Title\n> body\n')
rc, output = outcome(lanes(callout, after('> body\n', '- first\n'), after('> body\n', '- second\n')))
check('S06 a callout-shaped blockquote keeps the bullets outside it', rc == 0 and unioned(output, callout, ['- first', '- second']))
ref_title = key_points(link('a') + '[ref]: https://example.org\n  "Title"\n')
rc, output = outcome(lanes(ref_title, after('  "Title"\n', '- first\n'), after('  "Title"\n', '- second\n')))
check('S07 a reference-shaped lazy line stays with its item; additions after it union', rc == 0 and unioned(output, ref_title, ['- first', '- second']))
rc, output = outcome(lanes(ref_title, after(link('a'), '- first\n'), after('  "Title"\n', '- second\n')))
check('S08 an addition directly above that lazy line would take it in: manual', rc == 0 and placed(output, 'list item', 'takes existing line'))
rc, output = outcome(lanes(base, lambda t: t.replace('[GPT-4o]', '[GPT-4o, ' + unsafe_alias + ']'), parents[1]))
check('S09 an appended alias needing the raw fallback is manual', rc == 0 and 'manual GPT' in output and 'raw fallback' in output)
rc, output = outcome(lanes(base, lambda t: t.replace('aliases: [GPT-4o]', 'aliases:\n  - GPT-4o\n  - ' + unsafe_alias), parents[1]))
check('S09-block the block spelling of that alias is manual with its member line', rc == 0 and 'manual GPT' in output and 'raw fallback' in output and 'member LA line' in output)

# Native regression input is supplied with the acceptance corpus; an installed
# suite can name its copy through MERGE_PLAN_NATIVE_PAGE. Never embed vault prose.
# A named page that is not there is a broken premise. With none named and none at the
# default, the S09b legs run on a stand-in and say so: stopping here would leave every
# later leg unrun, the read-only proofs among them.
def native_premise(named, default):
    page = Path(named or default)
    if page.is_file(): return page, ''
    return None, 'MERGE_PLAN_NATIVE_PAGE names no file: ' + named if named else ''
absent_page = root / 'no-such-page.md'
check('S09b-premise-a a named page that is not there is a broken premise, never the stand-in', native_premise(str(absent_page), str(absent_page)) == (None, 'MERGE_PLAN_NATIVE_PAGE names no file: ' + str(absent_page)))
check('S09b-premise-b nothing named and nothing at the default takes the stand-in', native_premise(None, str(absent_page)) == (None, ''))
check('S09b-premise-c a named page that is there is the page read', native_premise(str(script), str(absent_page)) == (script, ''))
native_path, native_broken = native_premise(os.environ.get('MERGE_PLAN_NATIVE_PAGE'), str(here.parents[1] / 'fixture-vault/wiki/entities/FIRE.md'))
if native_broken:
    print('PROBE FAILED: ' + native_broken)
    sys.exit(2)
native_label = 'native FIRE'
if native_path is None:
    print('NOT APPLICABLE: S09b on the native FIRE page: MERGE_PLAN_NATIVE_PAGE is not set and that page never ships, so its legs run on a stand-in; set the variable to run them on the native text')
    native_label = 'stand-in'
    native_path = root / 'Stand-In.md'
    native_path.write_text('---\ntitle: "Stand-In"\ntype: entity\nconfidence: medium\naliases: [Stand-In Organisation]\n---\n\n## Definition\nA page in the shape of the native one.\n\n## Related\n- [[Other]]\n')
native_page = native_path.read_text()
native_rows = native_page.splitlines(keepends=True)
native_meta = yaml.safe_load(''.join(native_rows[1:independent_offset(native_rows) - 1]))
native_vault = root / 'native-vault'
native_target = native_vault / 'wiki/entities' / native_path.name
native_target.parent.mkdir(parents=True)
native_target.write_bytes(native_path.read_bytes())
native_alias_row = next(row.rstrip('\r\n') for row in native_rows if row.startswith('aliases: ['))
native_ledger = root / 'native-ledger.jsonl'
native_diff = root / 'native-alias.diff'
native_other = root / 'native-other.diff'
native_rel = native_target.relative_to(native_vault).as_posix()
def native_plan(spelling):
    changed = native_page.replace(native_alias_row, native_alias_row[:-1] + ', ' + spelling + ']', 1)
    make_diff(native_diff, native_page, changed, oldpath='a/' + native_rel, newpath='b/' + native_rel)
    make_diff(native_other, native_page, native_page.replace('## Related\n', '## Related\n- Additional related evidence.\n', 1), oldpath='a/' + native_rel, newpath='b/' + native_rel)
    vals = [event('run_open', 0, inbox=[])]
    for lane, path in (('LA', native_diff), ('LB', native_other)):
        obj = copy.deepcopy(claim)
        obj.update(name=native_path.stem, target=native_path.stem, type=native_meta['type'], confidence=native_meta['confidence'], base=m.digest(native_page.encode()), diff=str(path), diff_hash=m.digest(path.read_bytes()))
        vals += cycle(lane, claims=[obj])
    save(vals, native_ledger)
    proc = subprocess.run([sys.executable, '-B', str(script), '--vault', str(native_vault), '--ledger', str(native_ledger), '--union-dir', str(uniondir)], text=True, capture_output=True)
    if proc.stderr: print(proc.stderr, end='')
    return proc.returncode, proc.stdout, changed
rc, output, native_bad = native_plan(unsafe_alias)
check('S09b ' + native_label + ' reproduction: raw fallback is manual with no artefact or commands', rc == 0 and 'manual ' + native_path.stem in output and 'raw fallback' in output and 'member LA line' in output and 'union diff:' not in output and 'patch -F0' not in output)
try:
    bad_rows = native_bad.splitlines(keepends=True)
    yaml.safe_load(''.join(bad_rows[1:independent_offset(bad_rows) - 1]))
    yaml_rejected = False
except yaml.YAMLError: yaml_rejected = True
native_dry = subprocess.run(shlex.split(m.patch_command(native_vault, native_target, native_diff, root / 'native.rej')), text=True, capture_output=True)
check('S09b-native-control the invalid YAML still passes native patch dry-run on the unchanged fixture', yaml_rejected and native_dry.returncode == 0 and native_target.read_bytes() == native_path.read_bytes(), 'PyYAML rejected ' + str(yaml_rejected) + ' · native dry-run exit ' + str(native_dry.returncode))
rc, output, native_good = native_plan(json.dumps('Foo' + BS + 'qshared'))
native_patch = union_text(output)
native_composed = m.apply_memory(native_page, m.parse_diff(native_patch, native_vault.resolve())) if native_patch else ''
try:
    good_rows = native_composed.splitlines(keepends=True)
    good_aliases = yaml.safe_load(''.join(good_rows[1:independent_offset(good_rows) - 1]))['aliases']
except (ValueError, TypeError, KeyError, yaml.YAMLError): good_aliases = []
native_command = next((line for line in output.splitlines() if ' --dry-run ' in line), '')
native_dry = subprocess.run(shlex.split(native_command), text=True, capture_output=True) if native_command else None
check('S09b-valid-control ' + native_label + ' with valid encoding unions, parses and dry-runs', rc == 0 and 'apply-union ' + native_path.stem in output and good_aliases == native_meta['aliases'] + ['Foo' + BS + 'qshared'] and native_dry is not None and native_dry.returncode == 0 and native_target.read_bytes() == native_path.read_bytes())
parent_child = key_points('- parent\n  - child\n')
rc, output = outcome(lanes(parent_child, lambda t: t.replace('  - child\n', '- new parent\n  - child\n'), after('  - child\n', '- after\n')))
check('S10 a new parent above an existing child would re-parent it: manual', rc == 0 and placed(output, 'list item', 'takes existing line'))
rc, output = outcome(lanes(parent_child, after('  - child\n', '- first\n'), after('  - child\n', '- second\n')))
check('S10b additions after the complete nested block union', rc == 0 and unioned(output, parent_child, ['- first', '- second']))
rc, output = outcome(lanes(nested, *before_child))
check('S10c the qualified-child fixture is manual, naming both lines', rc == 0 and placed(output, 'list item', "'  - Only at temperature 0.'") and '- Treatment Y improves accuracy.' in output)
# S11: twenty added lines. Fences, Setext underlines and HTML starts are placed; %% and $$
# anywhere stay refused (the pattern the parser cannot place); inline spellings union.
matrix = [('```', 'fence'), ('~~~', 'fence'), ('- ```', 'fence'), ('%%', 'Obsidian comment'), ('- %%', 'Obsidian comment'), ('$$', 'maths block'), ('- $$ x $$', 'maths block'),
          ('===', 'Setext heading'), ('---', 'Setext heading'), ('<div>', 'HTML block'), ('- `code ``` span`', 'union'), ('- [link](https://example.org/%%)', 'Obsidian comment'), ('- `$$`', 'maths block'),
          ('- a <span>b</span>', 'union'), ('- === in text', 'union'), ('- --- in text', 'union'), ('- ~~~ in text', 'fence'), ('- ``` in text ```', 'union')]
for number, (line, want) in enumerate(matrix, 1):
    rc, output = outcome(lanes(base, after('Original.\n', line + '\n'), parents[1]))
    good = unioned(output, base, [line, '- second']) if want == 'union' else (guarded(output, want, 'member LA added line') if want in ('Obsidian comment', 'maths block') else placed(output, want, 'member LA added line'))
    check(f'S11-{number:02} added {line!r}: ' + ('unions' if want == 'union' else 'refused, naming ' + want), rc == 0 and good)
for number, marker in ((19, '```'), (20, '%% $$')):
    rc, output = outcome(lanes(base, lambda t, marker=marker: t.replace('[GPT-4o]', '[GPT-4o, ' + json.dumps(marker) + ']'), parents[1]))
    check(f'S11-{number:02} the frontmatter alias {marker!r} is outside the body guard: unions', rc == 0 and 'apply-union GPT' in output and json.dumps(marker) in union_text(output))
rule = key_points('Original.\n\n---\n')
rc, output = outcome(lanes(rule, *parents))
check('S12 a body thematic break is placed: the bullets union', rc == 0 and unioned(output, rule, ['- first', '- second']))
far_fence = base.replace('## Related\n', '## Related\n\n```\ncode\n```\n')
rc, output = outcome(lanes(far_fence, *two_links))
check('S13 a fence in a distant section no longer holds the target', rc == 0 and unioned(output, far_fence, [link('source-a').rstrip(), link('source-b').rstrip()], 'Appears in'))
far_comment = base.replace('## Related\n', '## Related\n\n%% note\n')
rc, output = outcome(lanes(far_comment, *two_links))
check('S13b a %% comment in a distant section still holds it: the page guard', rc == 0 and guarded(output, 'Obsidian comment'))
for number, lookalike in enumerate((chr(0xff40) * 3, chr(0xff5e) * 3, chr(0xff04) * 2, chr(0xff05) * 2, chr(0xff1c) + 'div' + chr(0xff1e), chr(0xff1d) * 3, chr(0xff0d) * 3), 1):
    rc, output = outcome(lanes(base, after('Original.\n', '- ' + lookalike + '\n'), parents[1]))
    check(f'S14-{number} the fullwidth look-alike {lookalike} is text: unions', rc == 0 and unioned(output, base, ['- ' + lookalike, '- second']))
vals = lanes(base.replace('Original.\n', 'Original.\n%% hidden\n'), *parents)
target.write_bytes(base.replace('Original.\n', 'Original.\n%% hidden\n').replace('\n', '\r\n').encode())
rc, output = outcome(vals)
target.write_text(base)
check('S15 a guarded CRLF page is manual with the guard and the byte re-check reasons', rc == 0 and guarded(output, 'Obsidian comment') and 'base moved during planning' in output)
headless = base[:base.index('# GPT')] + '- a\n'
rc, output = outcome(lanes(headless, after('- a\n', '- b\n'), after('- a\n', '- c\n')))
check('S16 bullets with no heading above them conflict', rc == 0 and 'conflict GPT' in output)
bodyless = base[:base.index('# GPT')]
rc, output = outcome(lanes(bodyless, lambda t: t.replace('[GPT-4o]', '[GPT-4o, A1]'), lambda t: t.replace('[GPT-4o]', '[GPT-4o, B1]')))
check('S16b alias appends on a bodyless page union', rc == 0 and '+aliases: [GPT-4o, A1, B1]' in union_text(output))
s17_cases = [
    ('flow', '"Foo' + BS + 'u0020shared"', 'Foo shared', 'Foo shared', 'manual'),
    ('block', '"Foo' + BS + 'u0020shared"', 'Foo shared', 'Foo shared', 'manual'),
    ('flow', "'Foo" + BS + "u0020shared'", 'Foo' + BS + 'u0020shared', 'Foo shared', 'apply-union'),
    ('block', "'Foo" + BS + "u0020shared'", 'Foo' + BS + 'u0020shared', 'Foo' + BS + 'u0020shared', 'manual'),
    ('flow', unsafe_alias, 'Foo' + BS + 'qshared', 'Foo' + BS + 'qshared', 'manual'),
    ('block', unsafe_alias, 'Foo' + BS + 'qshared', 'Foo' + BS + 'qshared', 'manual'),
]
for number, (form, spelling, decoded, appended, expected) in enumerate(s17_cases, 1):
    other_text = plain_other.replace('aliases: [Other-4o]', 'aliases:\n  - ' + spelling if form == 'block' else 'aliases: [' + spelling + ']')
    other_page.write_text(other_text)
    rc, output = outcome(lanes(base, lambda t, appended=appended: t.replace('[GPT-4o]', '[GPT-4o, ' + json.dumps(appended) + ']'), parents[1]))
    valid = ('multiple existing pages' in output and 'patch -F0' not in output) if expected == 'manual' else (appended in m.frontmatter(union_page(output, base)).get('aliases', []) and output.count('patch -F0') == 2)
    check(f'S17-{number} {form} spelling {spelling} decodes to {decoded!r}: {expected}', m.frontmatter(other_text).get('aliases') == [decoded] and rc == 0 and expected + ' GPT' in output and valid)
other_diff = root / 'S18-other.diff'
make_diff(other_diff, plain_other, plain_other.replace('Original.', 'Ordinary change.'), oldpath='a/wiki/models/Other.md', newpath='b/wiki/models/Other.md')
other_claim = copy.deepcopy(claim); other_claim.update(name='Other', target='Other', base=m.digest(plain_other.encode()), diff=str(other_diff), diff_hash=m.digest(other_diff.read_bytes()))
for letter, form in zip('abcdefg', ('[Alpha,]', '["unfinished]', '[[a], b]', '[{a: b}]', '[!tag a]', '[a, , b]', '[a] junk')):
    other_page.write_text(plain_other)
    vals = lanes(base.replace('[GPT-4o]', form), *parents); vals[2]['claims'].append(copy.deepcopy(other_claim))
    rc, output = outcome(vals)
    check(f'S18{letter} the unsupported list {form} is local: its target is manual while another applies', rc == 0 and 'manual GPT' in output and 'apply Other' in output and output.count('patch -F0') == 2)
other_page.unlink()
guarded_page = base.replace('Original.\n', 'Original.\n%% hidden\n')
rc, output = outcome(lanes(guarded_page, lambda t: t.replace('Original.\n', 'Changed prose.\n'), parents[1]))
check('S19 a competing prose edit on a guarded page is manual: the guard comes first', rc == 0 and guarded(output, 'Obsidian comment'))
fence_page = base.replace('Original.\n', 'Original.\n\n```\ncode\n```\n')
rc, output = outcome(lanes(fence_page, lambda t: t.replace('Original.\n', 'Changed prose.\n'), parents[1]))
check('S19b the same edit on a fenced page is ordinary conflict: the fence is placed, not guarded', rc == 0 and 'conflict GPT' in output and 'union page guard:' not in output)
for number, marker in enumerate(('- example ```', '   ===', '> 1. - <aside>', '- quoted %% example', '- quoted $$ example'), 1):
    page = base.replace('[GPT-4o]', json.dumps([marker]))
    rc, output = outcome(lanes(page, lambda t, marker=marker: t.replace(json.dumps([marker]), json.dumps([marker, marker + ' extra'])), parents[1]))
    check(f'S20-{number} the frontmatter value {marker!r} stays outside the body guard', rc == 0 and 'apply-union GPT' in output and 'union page guard:' not in output)
target.write_text(base)

# Round five: the A series and the LOW.
rc, output = outcome(lanes(parent_child, after('  - child\n', '- Y\n  - Y child\n'), after('  - child\n', '- Z\n')))
check('A01 an indented line added after an added item is judged by the line rule: conflict', rc == 0 and 'conflict GPT' in output)
rc, output = outcome(lanes(base, after('## Related\n', link('source-a')), after('## Related\n', link('source-b'))))
check('A02 additions at the end of the page union', rc == 0 and unioned(output, base, [link('source-a').rstrip(), link('source-b').rstrip()], 'Related'))
treatment = '- Treatment X improves accuracy.\n'
for ident, continuation in (('A03a', '\tOnly at temperature 0.\n'), ('A03b', ' Only at temperature 0.\n'), ('A03c', NBSP * 2 + 'Only at temperature 0.\n')):
    page = key_points(treatment + continuation)
    rc, output = outcome(lanes(page, *[lambda t, name=name, continuation=continuation: t.replace(continuation, '- Treatment ' + name + ' improves accuracy.\n' + continuation) for name in ('Y', 'Z')]))
    check(ident + ' a qualification continuing the item above (' + {'A03a': 'tab', 'A03b': 'one space', 'A03c': 'no-break spaces'}[ident] + ') would move to the new item: manual', rc == 0 and placed(output, 'list item', 'Only at temperature 0.'))
spaced = key_points(treatment + '\n  - Only at temperature 0.\n')
rc, output = outcome(lanes(spaced, *[lambda t, name=name: t.replace(treatment, treatment + '- Treatment ' + name + ' improves accuracy.\n') for name in ('Y', 'Z')]))
check('A03d a blank line before the existing child still lets the new item take it: manual', rc == 0 and placed(output, 'list item', 'Only at temperature 0.'))
rc, output = outcome(lanes(spaced, *[after('  - Only at temperature 0.\n', '- Treatment ' + name + ' improves accuracy.\n') for name in ('Y', 'Z')]))
composed = union_page(output, spaced)
check('A03e additions after the complete item, blank line and child included, union with the child kept under X', rc == 0 and unioned(output, spaced, ['- Treatment Y improves accuracy.', '- Treatment Z improves accuracy.']) and composed.index('  - Only at temperature 0.') < composed.index('- Treatment Y'))
fenced_child = key_points(treatment + '  ```\n  code\n  ```\n')
rc, output = outcome(lanes(fenced_child, *[lambda t, name=name: t.replace('  ```\n  code', '- Treatment ' + name + ' improves accuracy.\n  ```\n  code', 1) for name in ('Y', 'Z')]))
check("A04 an addition above an item's indented fence would take it in: manual", rc == 0 and placed(output, 'list item', "'  ```'"))
for ident, aliases in (('A05a', 'aliases: [' + unsafe_alias + ']'), ('A05b', 'aliases:\n  - ' + unsafe_alias)):
    rc, output = outcome(lanes(base.replace('aliases: [GPT-4o]', aliases), *parents))
    check(ident + ' a fallback item in the existing aliases is manual with its page line', rc == 0 and 'manual GPT' in output and 'union list refused:' in output and 'page line' in output)
rc, output = outcome(lanes(base, lambda t: t.replace('aliases: [GPT-4o]', 'aliases:\n  - GPT-4o\n  - ' + unsafe_alias), parents[1]))
check('A05c a fallback item in the proposed block aliases is manual with its member line', rc == 0 and 'manual GPT' in output and 'member LA line' in output)
for ident, spelling, decoded, unions in (('A06a', chr(0xe9), chr(0xe9), True), ('A06b', '"' + BS + 'u00e9"', chr(0xe9), True), ('A06c', chr(0xb0), chr(0xb0), True), ('A06d', '"' + BS + 'x41"', 'A', True), ('A06e', '"' + BS + 'N{DEGREE SIGN}"', None, False), ('A06f', "'O''Brien'", "O'Brien", True)):
    rc, output = outcome(lanes(base, lambda t, spelling=spelling: t.replace('[GPT-4o]', '[GPT-4o, ' + spelling + ']'), parents[1]))
    if unions: check(ident + ' the alias ' + spelling + ' decodes to ' + repr(decoded) + ' and unions', rc == 0 and 'apply-union GPT' in output and decoded in m.frontmatter(union_page(output, base)).get('aliases', []))
    else: check(ident + ' the alias ' + spelling + ' decodes to a control character: manual', rc == 0 and 'manual GPT' in output and 'control' in output)
for ident, form, escape, collides in (('A07', 'flow', 'x41', True), ('A07b', 'block', 'x41', True), ('A07c', 'flow', 'x42', False)):
    alias = '"' + BS + escape + '"'
    other_page.write_text(plain_other.replace('aliases: [Other-4o]', 'aliases: [' + alias + ']' if form == 'flow' else 'aliases:\n  - ' + alias))
    rc, output = outcome(lanes(base, lambda t: t.replace('[GPT-4o]', '[GPT-4o, "A"]'), parents[1]))
    if collides: check(ident + ' another page\'s ' + form + ' alias ' + alias + ' is A under YAML: appending A collides', rc == 0 and 'manual GPT' in output and 'multiple existing pages' in output and 'patch -F0' not in output)
    else: check(ident + ' the non-colliding ' + alias + ' (B) leaves the A append a union', rc == 0 and 'apply-union GPT' in output)
other_page.write_text(plain_other)
vals = lanes(base, *parents); vals[2]['claims'].append(copy.deepcopy(other_claim))
rc, output = outcome(vals)
dry = sum(' --dry-run ' in line for line in output.splitlines()); real = sum(line.startswith('after dry-run and base recheck: ') for line in output.splitlines())
check('LOW the dry-run count reads the commands that carry --dry-run: 2 dry, 2 real on two targets', rc == 0 and dry == real == 2, f'dry {dry} real {real}')
check('LOW-b a line-prefix count finds none on the same plan: the recorded dry 0 measured the wrong thing', sum(line.startswith('dry-run') for line in output.splitlines()) == 0 and dry == 2)
other_page.unlink()
rc, output = outcome(lifted)
check('LOW-c a held union contributes neither a dry-run nor a real command', rc == 0 and 'held until the full-page read:' in output and sum(' --dry-run ' in line for line in output.splitlines()) == 0 and sum(line.startswith('after dry-run and base recheck: ') for line in output.splitlines()) == 0)
target.write_text(base)
for leftover in (vault / 'wiki').rglob('*.md'):
    if leftover != target: leftover.unlink()

def manifest(directory):
    return {str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.rglob('*') if p.is_file()}

ro=root/'readonly';shutil.copytree(vault,ro)
ro_diff=ro/'update.diff';shutil.copyfile(diff,ro_diff)
ro_rows=copy.deepcopy(rows);ro_rows[2]['claims'][0].update(diff=str(ro_diff),diff_hash=m.digest(ro_diff.read_bytes()))
ro_ledger=ro/'ledger.jsonl';save(ro_rows,ro_ledger)
shutil.copyfile(script,ro/'merge_plan.py')
before=manifest(ro)
for p in ro.rglob('*'):p.chmod(0o555 if p.is_dir() else 0o444)
ro.chmod(0o555)
p=subprocess.run([sys.executable,'-B',str(ro/'merge_plan.py'),'--vault',str(ro),'--ledger',str(ro_ledger)],text=True,capture_output=True)
if p.stderr:print(p.stderr,end='')
check('M77 readonly plan executes',p.returncode==0 and 'apply GPT' in p.stdout,f'exit {p.returncode}')
check('M78 checksum manifest unchanged',before==manifest(ro) and len(before)==4,f'files {len(before)}')
p=subprocess.run([sys.executable,'-B',str(ro/'merge_plan.py'),'--vault',str(ro),'--resolved',str(ro_diff)],text=True,capture_output=True)
if p.stderr:print(p.stderr,end='')
check('D53 resolved release executes on the same read-only copy',p.returncode==0 and p.stdout.count('patch -F0')==2 and 'controls:' in p.stdout,f'exit {p.returncode}')
check('D54 resolved checksum manifest remains unchanged',before==manifest(ro),f'files {len(before)}')
altered=dict(before);altered['ledger.jsonl']='planted'
check('M79 checksum positive control',altered!=before)
patterns=[r'\.write(?:_text|_bytes)?\s*\(',r'\bopen\([^\n]*,[ ]*[\'\"][wax][^\'\"]*[\'\"]',r'\b(?:os|shutil)\.(?:replace|rename|remove|unlink|mkdir|makedirs|rmdir|copy|move|chmod)',r'\b(?:subprocess|os\.system|os\.popen)\b',r'\.(?:touch|unlink|mkdir|rename|chmod)\s*\(']
controls=['p.write_text(x)','open(p, "w")','os.replace(a,b)','subprocess.run(x)','p.unlink()']
source=script.read_text()
# The sole authorised write function is inspected separately. All other source
# still has a zero-write grep and the plan runs on a read-only copy above.
import ast
tree=ast.parse(source)
writer=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='emit_union')
writer_source='\n'.join(source.splitlines()[writer.lineno-1:writer.end_lineno])
source='\n'.join(line for i,line in enumerate(source.splitlines(),1) if not writer.lineno<=i<=writer.end_lineno)
check('M80a named write exception bounded',"path.open('x'" in writer_source and 'stream.write(patch)' in writer_source and 'outside the vault' in writer_source)
hits=[(pat,match.group()) for pat in patterns for match in re.finditer(pat,source)]
check('M80 source grep controls',all(re.search(pat,control) for pat,control in zip(patterns,controls)),f'controls {len(controls)}')
check('M81 source write grep zero',not hits,f'hits {len(hits)} {hits}')
check('T02 write controls: the bounded writer, every grep control firing, no other write',"path.open('x'" in writer_source and all(re.search(pat,control) for pat,control in zip(patterns,controls)) and not hits,f'controls {len(controls)} · hits {len(hits)}')
ro.chmod(0o755)
for p in ro.rglob('*'):p.chmod(0o755 if p.is_dir() else 0o644)
print(f'PASS {passed}/{passed+failed}' if not failed else f'FAIL {failed}/{passed+failed}')
sys.exit(bool(failed))
PY_MERGE_SUITE
