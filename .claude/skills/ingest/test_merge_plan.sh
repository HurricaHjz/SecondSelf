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

vault = root / 'vault'; (vault / 'wiki' / 'models').mkdir(parents=True)
target = vault / 'wiki' / 'models' / 'GPT.md'
base = '---\ntitle: GPT\ntype: model\nconfidence: medium\naliases: [GPT-4o]\n---\n# GPT\n\n## Key Points\nOriginal.\n\n## Appears in\n\n## Related\n'
target.write_text(base)
new = base.replace('Original.','Original.\nAdded.')
diff = root / 'update.diff'
rel = 'wiki/models/GPT.md'

def make_diff(path, old, new, oldpath='a/' + rel, newpath='b/' + rel):
    path.write_text(''.join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile=oldpath, tofile=newpath)))
    return path

make_diff(diff, base, new)
claim = {'name':'GPT', 'type':'model', 'kind':'update','target':'GPT','source':'one.md','from':'one-page','facts':[{'fact':'Added.','locator':'Results'}], 'confidence':'medium','base':m.digest(base.encode()),'diff':str(diff),'diff_hash':m.digest(diff.read_bytes())}
scores = 'scores: fab 0 plant 0 cov 0 tier 0 struct 0 integ 0 lang 0 anom 0 claims 0'

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
minus=copy.deepcopy(rows);minus[-1]['scores']=scores.replace('plant 0','plant -')
leg('M61 unscored plant',minus,2,'unscored plant or claims')
minus[-1]['scores']=scores.replace('claims 0','claims -')
leg('M62 unscored claims',minus,2,'unscored plant or claims')
plant=copy.deepcopy(rows);plant[-1]['scores']=scores.replace('plant 0','plant 1')
leg('M63 plant quarantines entire lane',plant,0,'quarantined GPT')

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
out=leg('U20 links outside allowed heading conflict',union_rows(link('source-a'),link('source-b'),'## Key Points'),0,'conflict GPT',('--union-dir',uniondir))
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
ro.chmod(0o755)
for p in ro.rglob('*'):p.chmod(0o755 if p.is_dir() else 0o644)
print(f'PASS {passed}/{passed+failed}' if not failed else f'FAIL {failed}/{passed+failed}')
sys.exit(bool(failed))
PY_MERGE_SUITE
