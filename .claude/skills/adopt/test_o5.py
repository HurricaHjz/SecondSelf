#!/usr/bin/env python3
"""Executable O5 contracts, with disposable fixtures and stdout-only results.

Fixture construction/removal is the brief's explicit test exception. Evaluators
run against a read-only fixture, with a complete before/after checksum manifest.
These are acceptance tests for the proposed interface, not a replacement build.
"""
import argparse
import base64
import copy
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import uuid
from unittest.mock import patch
from contextlib import nullcontext


STAMP = '2026-01-02T12:00:00Z'
MODEL = 'fixture-model-v1'
# Recommendation only: set by judgement, unmeasured; the owner did not set a count.
HOW_TO_MINIMUM = 2


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, 'PROBE FAILED: ' + message + '\n')


def manifest(root):
    result = {}
    for parent, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories + files):
            path = Path(parent) / name
            item = {'mode': stat.S_IMODE(path.lstat().st_mode)}
            if path.is_symlink():
                item['link'] = os.readlink(path)
            elif path.is_file():
                item['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            else:
                item['directory'] = True
            result[str(path.relative_to(root))] = item
    return result


def permissions(root, readonly):
    paths = sorted(root.rglob('*'), key=lambda p: len(p.parts), reverse=readonly)
    for path in paths:
        if not path.is_symlink():
            path.chmod((0o500 if path.is_dir() else 0o400) if readonly else
                       (0o700 if path.is_dir() else 0o600))
    root.chmod(0o500 if readonly else 0o700)


class Fixture:
    def __init__(self, root, modules):
        # Canonical root: a temporary folder may sit behind a symbolic link.
        root = Path(root).resolve(strict=True)
        self.root, self.m = root, modules
        D, W, S = modules['D'], modules['W'], modules['S']
        vault, home = root / 'vault', root / 'home'
        vault.mkdir()
        home.mkdir()
        self.ctx = D.Context(vault, home, root / 'locks')
        tree = home / 'tree'
        tree.mkdir()
        (tree / 'SKILL.md').write_text('---\nname: fixture-skill\n---\nCheck the fixture.\n')
        permissions(tree, True)
        carrier = home / 'carrier'
        carrier.symlink_to(tree, target_is_directory=True)
        self.doc = W.seed_document(STAMP)
        self.doc['schema_version'] = 1
        # Frozen v1 data has page layout 1 only; the current seed starts at a later layout.
        self.doc['page']['layout_version'] = 1
        self.doc['policy']['freshness_rule_version'] = 1
        self.doc['policy'].pop('how_to_successes_required', None)
        self.doc['policy'].pop('owner_identity', None)
        self.doc['policy']['model_targets'] = [{'model_id': MODEL, 'release_date': '2026-01-01',
                                              'evidence_refs': ['model-release']}]
        pin = {'type': 'registry-version', 'ecosystem': 'npm', 'package': 'fixture-skill',
               'version': '1.0.0', 'sha256': D.sha(b'fixture package')}
        install = {'id': 'fixture-install', 'publisher': {'identity': 'Fixture publisher', 'evidence_refs': []},
                   'source': {'kind': 'local-build', 'uri': 'fixture:local', 'evidence_refs': []},
                   'pin': pin, 'update_policy': {'mode': 'manual', 'acceptance_check_ids': [],
                   'revert_resource_ids': [], 'notes': ''}, 'resource_ids': ['tree', 'carrier'], 'notes': []}
        resource = {'id': 'tree', 'owner': {'type': 'installation', 'id': install['id']},
                    'role': 'skill-tree', 'type': 'skill-tree',
                    'locator': {'root': 'absolute', 'path': str(tree)},
                    'expected': {'sha256': S.tree_hash(tree), 'entry': 'SKILL.md', 'references': [],
                    'carrier_id': 'carrier', 'pin_sha256': D.digest(pin)},
                    'check_ids': ['skill-content', 'skill-invocation']}
        wrapper = {'id': 'carrier', 'owner': {'type': 'installation', 'id': install['id']},
                   'role': 'carrier', 'type': 'carrier', 'locator': {'root': 'absolute', 'path': str(carrier)},
                   'expected': {'skill_name': 'fixture-skill', 'level': 'auto', 'kind': 'symlink',
                   'target_resource_id': 'tree', 'declaration': ''}, 'check_ids': ['carrier-load']}
        self.resource = resource
        self.comparison = {'model_id': MODEL, 'model_release_date': '2026-01-01',
                           'release_evidence_refs': ['model-release'], 'applicability_evidence_refs': ['old-task'],
                           'evaluated_at': STAMP, 'rule_version': 1, 'result': 'pass', 'reasons': []}
        self.skill = {'resource_id': 'tree', 'candidate': {'installation_id': install['id'],
                      'pin_sha256': D.digest(pin), 'skill_tree_sha256': resource['expected']['sha256'],
                      'version_label': '1.0.0', 'version_date': '2026-01-02',
                      'date_basis': 'relevant-file-revision', 'date_evidence_refs': ['version-date']},
                      'comparisons': [self.comparison], 'applicability_evidence': ['old-task']}
        self.row = {'id': 'fixture-skill', 'name': 'Fixture skill', 'kind': 'skill',
                    'installation_ids': [install['id']],
                    'level': {'base': 'auto', 'conditions': [], 'decision_refs': []},
                    'reference_use': 'Read within the existing grant.',
                    'routes': [{'job_id': 'fixture-job', 'route': 'use-directly', 'status': 'implemented',
                    'reason': 'Fixture', 'decision_refs': []}],
                    'lifecycle': {'state': 'prepared', 'changed_at': STAMP, 'reason': 'Fixture', 'decision_refs': []},
                    'resource_bindings': [{'role': r['role'], 'resource_id': r['id']} for r in (resource, wrapper)],
                    'record_links': [], 'acceptance': {'check_ids': [], 'evidence_refs': [],
                    'criterion': 'exact-fixture', 'human_required': False},
                    'freshness': {'status': 'applicable', 'skills': [self.skill]}, 'run_needs': [],
                    'output_judge': {'kind': 'objective-check', 'criterion': 'exact-fixture', 'evidence_refs': []},
                    'notes': [], 'provenance': []}
        self.doc.update(rows=[self.row], installations=[install], resources=[resource, wrapper],
                        jobs=[{'id': 'fixture-job', 'label': 'Fixture', 'definition': 'A real fixture task', 'notes': []}])
        self.evidence('model-release', {'type': 'model-release', 'model_id': MODEL,
                      'release_date': '2026-01-01'}, kind='captured-source')
        self.evidence('version-date', {'type': 'version-date', 'resource_id': 'tree',
                      'pin_sha256': D.digest(pin), 'tree_sha256': resource['expected']['sha256'],
                      'version_date': '2026-01-02'}, kind='captured-source')
        self.bind_old_task()

    def evidence(self, eid, subject, body=None, kind='scripted', result='pass', at=STAMP,
                 judge='fixture-owner'):
        D = self.m['D']
        payload = {'subject': subject, 'result': result, **(body or {})}
        path = self.ctx.vault / 'evidence' / (eid + '.json')
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(D.encoded(payload))
        method = ({'judge': judge, 'criterion': 'exact-fixture', 'description': 'Fixture judgement'}
                  if kind == 'human' else {'check_id': 'fixture', 'implementation_sha256': D.sha(b'fixture check'),
                                          'description': 'Fixture check with controls'})
        record = {'id': eid, 'kind': kind, 'observed_at': at, 'subject': subject,
                  'artefact': {'locator': {'root': 'absolute', 'path': str(path)}, 'sha256': D.sha(path.read_bytes())},
                  'result': result, 'method': method, 'limitations': ['Synthetic fixture; no model invoked.']}
        self.doc['evidence'] = [e for e in self.doc['evidence'] if e['id'] != eid] + [record]
        return eid

    def bind_old_task(self):
        D, R, F = self.m['D'], self.m['R'], self.m['F']
        expanded = D.operational_definition(self.doc, self.row)
        for skill in self.row['freshness']['skills']:
            i, binding = next((i, b) for i, b in enumerate(expanded['bindings'])
                              if b['resource_id'] == skill['resource_id'])
            resource = binding['resource_definition']
            subject = {**R.row_subject(self.doc, self.row, binding, i, 'skill-invocation'),
                       'type': 'task-check', 'model_id': MODEL,
                       'fixture_sha256': D.sha(b'old single-task evidence'), 'criterion_id': 'exact-fixture'}
            observation = R.observation(self.doc, self.row, resource, self.ctx)
            human = self.row['output_judge']['kind'] == 'owner'
            self.evidence(skill['applicability_evidence'][0], subject,
                          {'observation_sha256': D.digest(F.qualification_observation(resource, observation)),
                           'positive_control': True, 'negative_control': True, 'criterion': 'exact-fixture',
                           **({'human_judge': 'fixture-owner'} if human else {})},
                          kind='human' if human else 'scripted')

    def scope(self, resource_id='tree'):
        D = self.m['D']
        resource = next(r for r in self.doc['resources'] if r['id'] == resource_id)
        skill = next(s for s in self.row['freshness']['skills'] if s['resource_id'] == resource_id)
        return D.digest({'kind': 'skill-assurance-v2', 'register_id': self.doc['register_id'],
                         'row_id': self.row['id'], 'resource_id': resource_id,
                         'resource_definition_sha256': D.digest(resource),
                         'pin_sha256': skill['candidate']['pin_sha256'],
                         'skill_tree_sha256': skill['candidate']['skill_tree_sha256'],
                         'model_id': MODEL, 'model_release_date': self.comparison['model_release_date'],
                         'criterion': self.row['acceptance']['criterion'], 'judge': self.row['output_judge']})

    def v2(self, tier='claimed', route='comparison'):
        self.doc['schema_version'] = 2
        self.doc['policy']['freshness_rule_version'] = 2
        self.doc['policy']['how_to_successes_required'] = HOW_TO_MINIMUM
        self.doc['policy']['owner_identity'] = 'fixture-owner'
        self.comparison.update(rule_version=2, tier=tier, proof_route=route,
                               claim_evidence_refs=['author-claim'], events=[])
        self.evidence('author-claim', {'type': 'skill-claim', 'scope_sha256': self.scope(),
                      'author_identity': 'Fixture publisher', 'published_uri': 'https://example.test/claim',
                      'published_at': '2026-01-02T09:00:00Z'}, {'output': 'The author claims support for the fixture model.'},
                      kind='publisher-claim')
        self.event('claim', 'unproven', 'claimed', evidence_refs=['author-claim'])

    def event(self, action, before, after, **details):
        item = {'id': 'event-' + str(len(self.comparison['events']) + 1), 'action': action,
                'from_tier': before, 'to_tier': after, 'at': STAMP, 'reason': 'Fixture transition', **details}
        self.comparison['events'].append(item)
        return item

    def frozen_task(self, eid='frozen-task', content=b'fixture input\n', definition=None):
        task = {'task_id': 'task-a', 'job_id': 'fixture-job',
                'definition': definition or self.doc['jobs'][0]['definition'],
                'invocation': 'Check the supplied input.', 'criterion': 'exact-fixture',
                'inputs': [{'name': 'input.txt', 'media_type': 'text/plain',
                            'content_base64': base64.b64encode(content).decode('ascii')}]}
        digest = self.m['D'].digest(task)
        self.evidence(eid, {'type': 'skill-task', 'scope_sha256': self.scope(),
                      'task_id': 'task-a', 'task_sha256': digest}, {'task': task},
                      kind='captured-source', at='2026-01-02T09:30:00Z')
        return {'task_id': 'task-a', 'task_evidence_ref': eid, 'task_sha256': digest}

    def run(self, eid, mode, result='pass', at=STAMP, task=None, run_id=None):
        task = task or self.frozen_task()
        return self.evidence(eid, {'type': 'skill-run', 'scope_sha256': self.scope(), 'task_id': 'task-a',
                             **task, 'run_id': run_id or eid, 'mode': mode}, {'output': ('all fixture checks met' if mode == 'with-skill'
                             else 'one fixture check missed'),
                             'criterion': 'exact-fixture', 'positive_control': True, 'negative_control': True},
                             result=result, at=at)

    def paired(self, verdict='supports', human=False, judge='fixture-owner'):
        task = self.frozen_task()
        self.run('with-skill', 'with-skill', at='2026-01-02T10:00:00Z')
        self.run('without-skill', 'without-skill', result='fail', at='2026-01-02T11:00:00Z')
        self.evidence('judgement', {'type': 'skill-comparison', 'scope_sha256': self.scope(), 'task_id': 'task-a',
                      **task,
                      'with_skill_evidence_ref': 'with-skill', 'without_skill_evidence_ref': 'without-skill'},
                      {'output': 'Compared both outputs against the criterion.', 'verdict': verdict,
                       'criterion': 'exact-fixture', 'positive_control': True, 'negative_control': True,
                       **({'human_judge': judge} if human else {})},
                      kind='human' if human else 'scripted', judge=judge)
        return {**task, 'with_skill_evidence_ref': 'with-skill',
                'without_skill_evidence_ref': 'without-skill', 'judgement_evidence_ref': 'judgement', 'verdict': verdict}

    def evaluate(self):
        return self.m['F'].evaluate(self.doc, self.row, self.ctx, MODEL)

    def acceptance(self):
        D, R = self.m['D'], self.m['R']
        expanded = D.operational_definition(self.doc, self.row)
        self.row['acceptance']['evidence_refs'] = [b['resource_id'] + '-' + check
            for b in expanded['bindings'] for check in b['resource_definition']['check_ids']
            if check not in D.PURE_CHECKS]
        for i, binding in enumerate(D.operational_definition(self.doc, self.row)['bindings']):
            resource = binding['resource_definition']
            for check in resource['check_ids']:
                if check not in D.PURE_CHECKS:
                    self.evidence(resource['id'] + '-' + check,
                        R.row_subject(self.doc, self.row, binding, i, check),
                        {'observation_sha256': D.digest(R.observation(self.doc, self.row, resource, self.ctx)),
                         'positive_control': True, 'negative_control': True, 'criterion': 'exact-fixture'})

    def dependency(self):
        """A second installation reached only through a run-needs carrier."""
        D, S = self.m['D'], self.m['S']
        tree = self.ctx.home / 'dependency-tree'
        tree.mkdir()
        (tree / 'SKILL.md').write_text('---\nname: dependency-skill\n---\nCheck the dependency.\n')
        permissions(tree, True)
        carrier = self.ctx.home / 'dependency-carrier'
        carrier.symlink_to(tree, target_is_directory=True)
        install = copy.deepcopy(self.doc['installations'][0])
        install['id'] = 'dependency-install'
        install['resource_ids'] = ['dependency-tree', 'dependency-carrier']
        install['pin']['package'] = 'dependency-skill'
        resource = copy.deepcopy(self.resource)
        resource.update(id='dependency-tree', owner={'type': 'installation', 'id': install['id']},
                        locator={'root': 'absolute', 'path': str(tree)})
        resource['expected'].update(sha256=S.tree_hash(tree), carrier_id='dependency-carrier',
                                    pin_sha256=D.digest(install['pin']))
        wrapper = copy.deepcopy(self.doc['resources'][1])
        wrapper.update(id='dependency-carrier', owner=resource['owner'],
                       locator={'root': 'absolute', 'path': str(carrier)})
        wrapper['expected'].update(skill_name='dependency-skill', target_resource_id=resource['id'])
        skill = copy.deepcopy(self.skill)
        skill.update(resource_id=resource['id'], applicability_evidence=['dependency-old-task'])
        skill['candidate'].update(installation_id=install['id'], pin_sha256=D.digest(install['pin']),
                                 skill_tree_sha256=resource['expected']['sha256'],
                                 date_evidence_refs=['dependency-date'])
        skill['comparisons'][0]['applicability_evidence_refs'] = ['dependency-old-task']
        self.doc['installations'].append(install)
        self.doc['resources'].extend([resource, wrapper])
        self.row['run_needs'].append({'role': 'carrier', 'resource_id': wrapper['id']})
        self.row['freshness']['skills'].append(skill)
        self.evidence('dependency-date', {'type': 'version-date', 'resource_id': resource['id'],
                      'pin_sha256': skill['candidate']['pin_sha256'],
                      'tree_sha256': skill['candidate']['skill_tree_sha256'], 'version_date': '2026-01-02'},
                      kind='captured-source')

    def exception(self, eid, resource_id='tree', route='use-directly', date_reason=None,
                  scope=None, judge='fixture-owner'):
        return self.evidence(eid, {'type': 'skill-exception', 'scope_sha256': scope or self.scope(resource_id),
            'route': route}, {'output': 'The owner accepts the stated uncertainty.',
            'suggestion': 'Try this skill for the fixture task.', 'human_judge': judge,
            'accepted_uncertainties': ['missing-claim'] + ([date_reason] if date_reason else [])},
            kind='human', judge=judge)

    def active_v1(self):
        self.acceptance()
        self.bind_old_task()
        self.prepared_doc = copy.deepcopy(self.doc)
        D, R = self.m['D'], self.m['R']
        checks = R.prove(self.doc, self.row, self.ctx)
        self.row['lifecycle'] = {'state': 'active', 'changed_at': STAMP, 'reason': 'Historical fixture',
            'decision_refs': [], 'activation': {'id': str(uuid.uuid4()), 'register_id': self.doc['register_id'],
            'row_id': self.row['id'], 'definition_sha256': D.digest(D.expansion(self.doc, self.row)),
            'verified_at': STAMP, 'checks': checks, 'freshness_evaluation': [{'model_id': MODEL, 'result': 'pass'}],
            'evidence_refs': sorted(c['evidence_ref'] for c in checks if 'evidence_ref' in c)}}
        validator = getattr(self.m['G'], 'validate_v1', D.validate)
        validator(self.doc)


def tier(result, expected):
    assert isinstance(result, dict), 'O5 evaluator must return a tier-labelled assessment, got ' + repr(result)
    assert result['tier'] == expected, (result, expected)
    assert result['control_hits'] > 0, 'tier result lacks a positive control'


def refusal(f, call, reason=None):
    try:
        call()
    except f.m['D'].Problem as exc:
        assert exc.code == 1, 'expected a completed assurance refusal, got ' + str(exc)
        assert reason is None or reason in str(exc), 'wrong refusal reason: ' + str(exc)
        return
    raise AssertionError('promotion accepted without the required O5 record')


def configure(f, case):
    if case == 'migration':
        f.active_v1()
        return
    f.v2()
    if case == 'claimed':
        pass
    elif case in ('comparison', 'drop-proven', 'bad-pair', 'taste', 'taste-other-human',
                  'changed-input', 'changed-definition', 'judgement-input', 'writer-transition'):
        if case in ('taste', 'taste-other-human'):
            f.row['output_judge']['kind'] = 'owner'
            # Regenerate the claim for the changed judgement scope.
            f.v2()
        pair = f.paired(human=case in ('taste', 'taste-other-human'))
        if case == 'bad-pair':
            pair['without_skill_evidence_ref'] = 'with-skill'
        if case in ('changed-input', 'changed-definition', 'judgement-input'):
            changed = f.frozen_task('changed-task',
                content=b'changed fixture input\n' if case != 'changed-definition' else b'fixture input\n',
                definition='A different real fixture task' if case == 'changed-definition' else None)
            assert changed['task_id'] == pair['task_id'] == 'task-a'
            assert changed['task_sha256'] != pair['task_sha256']
            if case == 'judgement-input':
                original = next(e for e in f.doc['evidence'] if e['id'] == 'judgement')
                body = json.loads(Path(original['artefact']['locator']['path']).read_text())
                f.evidence('changed-judgement', {**original['subject'], **changed},
                           {k: v for k, v in body.items() if k not in ('subject', 'result')})
                pair['judgement_evidence_ref'] = 'changed-judgement'
            else:
                f.run('changed-baseline', 'without-skill', result='fail',
                      at='2026-01-02T11:00:00Z', task=changed)
                pair['without_skill_evidence_ref'] = 'changed-baseline'
                # Keep the judgement's pair references valid: only task content differs.
                original = next(e for e in f.doc['evidence'] if e['id'] == 'judgement')
                body = json.loads(Path(original['artefact']['locator']['path']).read_text())
                f.evidence('judgement', {**original['subject'],
                           'without_skill_evidence_ref': 'changed-baseline'},
                           {k: v for k, v in body.items() if k not in ('subject', 'result')})
        if case == 'taste-other-human':
            original = next(e for e in f.doc['evidence'] if e['id'] == 'judgement')
            body = json.loads(Path(original['artefact']['locator']['path']).read_text())
            f.evidence('other-judgement', original['subject'],
                       {**{k: v for k, v in body.items() if k not in ('subject', 'result')},
                        'human_judge': 'fixture-other-person'}, kind='human', judge='fixture-other-person')
            pair['judgement_evidence_ref'] = 'other-judgement'
        f.event('comparison', 'claimed', 'proven', comparison=pair)
        f.comparison['tier'] = 'proven'
        if case == 'drop-proven':
            f.run('bad-use', 'with-skill', result='fail')
            f.event('drop', 'proven', 'claimed', evidence_refs=['bad-use'], decision_refs=[])
            f.comparison['tier'] = 'claimed'
    elif case in ('checked-runs', 'too-few-runs', 'duplicate-runs'):
        f.comparison['proof_route'] = 'how-to'
        refs = [f.run('checked-' + str(n), 'with-skill') for n in range(HOW_TO_MINIMUM)]
        if case == 'too-few-runs':
            refs = refs[:-1]
        if case == 'duplicate-runs':
            refs[-1] = f.run('checked-repeat', 'with-skill', run_id=refs[0])
            assert len(set(refs)) == HOW_TO_MINIMUM, 'distinct evidence records required'
        f.event('checked-runs', 'claimed', 'proven', evidence_refs=refs, successful_run_count=len(refs))
        f.comparison['tier'] = 'proven'
    elif case == 'drop-claimed':
        f.run('bad-use', 'with-skill', result='fail')
        f.event('drop', 'claimed', 'unproven', evidence_refs=['bad-use'], decision_refs=[])
        f.comparison['tier'] = 'unproven'
    elif case == 'no-record':
        f.comparison['tier'] = 'proven'
    elif case == 'unhelpful-comparison':
        f.event('comparison', 'claimed', 'claimed', comparison=f.paired('does-not-support'))
    elif case in ('render', 'schema', 'claimed-use', 'important-use'):
        pass
    elif case in ('unproven', 'old-date', 'unproven-owner') or case.startswith('owner-'):
        f.comparison.update(tier='unproven', events=[], claim_evidence_refs=[])
        if case in ('old-date', 'owner-old-date', 'owner-date-unacknowledged'):
            f.skill['candidate']['version_date'] = '2025-12-31'
            f.evidence('version-date', {'type': 'version-date', 'resource_id': 'tree',
                'pin_sha256': f.skill['candidate']['pin_sha256'],
                'tree_sha256': f.skill['candidate']['skill_tree_sha256'], 'version_date': '2025-12-31'},
                kind='captured-source')
        if case == 'owner-unknown-date':
            f.skill['candidate'].update(version_date={'status': 'unknown', 'reason': 'No candidate date captured.'},
                                       date_basis='unknown', date_evidence_refs=[])
        if case.startswith('owner-closure'):
            f.dependency()
        if case == 'unproven-owner' or case.startswith('owner-'):
            f.delivery_route = 'take-pattern' if case in ('owner-pattern', 'owner-route-mismatch') else 'use-directly'
            f.row['routes'][0]['route'] = 'internalise' if f.delivery_route == 'take-pattern' else f.delivery_route
            date_reason = ('old-date' if case == 'owner-old-date' else
                           'unknown-date' if case == 'owner-unknown-date' else None)
            f.exception('owner-exception', route='use-directly' if case == 'owner-route-mismatch' else f.delivery_route,
                        date_reason=date_reason,
                        scope=f.m['D'].digest({'different_subject': True}) if case == 'owner-wrong-subject' else None,
                        judge='fixture-other-person' if case == 'owner-other-human' else 'fixture-owner')
            f.decision_refs = ['owner-exception']
            if case.startswith('owner-closure') and case != 'owner-closure-missing':
                f.exception('dependency-exception', 'dependency-tree',
                            scope=f.scope() if case == 'owner-closure-mismatch' else None)
                f.decision_refs.append('dependency-exception')
    else:
        raise ValueError('unknown case ' + case)
    if case in ('claimed-use', 'important-use', 'unproven-owner') or case.startswith('owner-'):
        f.acceptance()
    f.bind_old_task()
    if case in ('claimed', 'claimed-use', 'important-use'):
        # Remove local freshness proof after every construction step; resource
        # acceptance evidence remains valid and is not a model task comparison.
        f.comparison['applicability_evidence_refs'] = []
        f.skill['applicability_evidence'] = []
        f.doc['evidence'] = [e for e in f.doc['evidence'] if e['subject']['type'] != 'task-check']
        if case != 'claimed':
            f.acceptance()
    if (case in ('claimed-use', 'important-use', 'unproven-owner') or case.startswith('owner-')) and f.m['W'].seed_document()['schema_version'] == 2:
        # Exercise the actual closed document, generated page and receipt loader.
        D = f.m['D']
        D.validate(f.doc)
        raw, page = D.encoded(f.doc), f.m['render'].render(f.doc)
        for path, content in ((f.ctx.data, raw), (f.ctx.page, page), (f.ctx.receipt, D.encoded({
                'register_id': f.doc['register_id'], 'revision': f.doc['revision'],
                'data_sha256': D.sha(raw), 'page_sha256': D.sha(page), 'transaction_id': str(uuid.uuid4())}))):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        assert D.load_current(f.ctx)[0] == f.doc


REFUSALS = {'no-record': None, 'bad-pair': None, 'too-few-runs': None,
            'duplicate-runs': 'O5_RUN_ID_REUSED', 'changed-input': 'O5_TASK_MISMATCH',
            'changed-definition': 'O5_TASK_MISMATCH', 'judgement-input': 'O5_TASK_MISMATCH',
            'taste-other-human': 'O5_OWNER_MISMATCH'}
OWNER_REFUSALS = {'owner-wrong-subject': 'O5_EXCEPTION_COVERAGE',
                  'owner-closure-missing': 'O5_EXCEPTION_COVERAGE',
                  'owner-closure-mismatch': 'O5_EXCEPTION_COVERAGE',
                  'owner-route-mismatch': 'O5_EXCEPTION_ROUTE',
                  'owner-date-unacknowledged': 'O5_EXCEPTION_DATE',
                  'owner-other-human': 'O5_OWNER_MISMATCH'}


def fixture_controls(f, case):
    """Verify the premises separately from the absent v2 implementation."""
    checked = 0
    records = {e['id']: e for e in f.doc['evidence']}
    for record in records.values():
        raw = Path(record['artefact']['locator']['path']).read_bytes()
        assert f.m['D'].sha(raw) == record['artefact']['sha256']
        body = json.loads(raw)
        assert body['subject'] == record['subject'] and body['result'] == record['result']
        if record['subject']['type'] == 'skill-task':
            assert f.m['D'].digest(body['task']) == record['subject']['task_sha256']
            for item in body['task']['inputs']:
                assert base64.b64decode(item['content_base64'], validate=True)
        checked += 1
    if case in ('claimed', 'claimed-use', 'important-use'):
        assert not any(e['subject']['type'] in ('task-check', 'skill-run', 'skill-comparison')
                       for e in records.values()), 'local task proof survived claimed-use construction'
        assert not f.skill['applicability_evidence'] and not f.comparison['applicability_evidence_refs']
        if case != 'claimed':
            assert f.m['R'].prove(f.doc, f.row, f.ctx), 'resource acceptance control absent'
    if case in REFUSALS and f.m['W'].seed_document()['schema_version'] == 1:
        assert f.evaluate() == ['old-task'], 'native task control fails before the v2 discriminator'
    if case == 'duplicate-runs':
        refs = f.comparison['events'][-1]['evidence_refs']
        assert len(set(refs)) == HOW_TO_MINIMUM
        assert len({records[e]['subject']['run_id'] for e in refs}) == 1
    if case == 'taste-other-human':
        wrong = records['other-judgement']
        assert wrong['kind'] == 'human' and wrong['method']['judge'] != f.doc['policy']['owner_identity']
    if case.startswith('owner-closure'):
        expanded = f.m['D'].operational_definition(f.doc, f.row)
        ids = {b['resource_id'] for b in expanded['bindings'] if b['resource_definition']['type'] == 'skill-tree'}
        assert ids == {'tree', 'dependency-tree'} and f.scope() != f.scope('dependency-tree')
        assert f.m['R'].prove(f.doc, f.row, f.ctx)
        if f.m['W'].seed_document()['schema_version'] == 1:
            assert set(f.evaluate()) == {'old-task', 'dependency-old-task'}
    assert checked > 0
    print('FIXTURE_CONTROL ' + json.dumps({'case': case, 'valid_envelopes': checked,
          'task_records': sum(e['subject']['type'] == 'skill-task' for e in records.values()),
          'local_task_proofs': sum(e['subject']['type'] == 'task-check' for e in records.values()),
          'skills': len(f.row['freshness']['skills'])}, sort_keys=True))


def check_case(f, case, build):
    if case in REFUSALS:
        refusal(f, f.evaluate, REFUSALS[case])
    elif case == 'migration':
        upgrade = getattr(f.m['G'], 'upgrade_freshness', None)
        assert callable(upgrade), 'O5 typed schema migration is absent'
        source = copy.deepcopy(f.doc)
        changed = upgrade(source, at=STAMP)
        assert source == f.doc, 'migration mutated its input'
        assert changed['schema_version'] == 2 and changed['policy']['freshness_rule_version'] == 2
        assert changed['policy']['owner_identity'] is None, 'migration invented an owner identity'
        c = changed['rows'][0]['freshness']['skills'][0]['comparisons'][0]
        assert c['tier'] == 'unproven' and c['events'] == [], 'old pass invented O5 proof'
        assert changed['evidence'] == source['evidence'], 'migration lost old evidence'
        assert changed['rows'][0]['lifecycle']['state'] == 'prepared'
        assert 'activation' not in changed['rows'][0]['lifecycle'], 'v1 activation survived the changed rule'
        prepared = upgrade(f.prepared_doc, at=STAMP)
        assert prepared['rows'][0]['lifecycle'] == f.prepared_doc['rows'][0]['lifecycle']
        live_copy = json.loads(INSTANCE_DATA.read_text())
        legacy = upgrade(live_copy, at=STAMP)
        assert legacy['rows'] == live_copy['rows'], 'legacy import facts changed'
        assert legacy['migration'] == live_copy['migration'], 'source coverage changed'
        assert legacy['policy']['extensions'] == live_copy['policy']['extensions']
        assert upgrade(legacy, at=STAMP) == legacy, 'migration is not idempotent'
        print('MIGRATION_CONTROL ' + json.dumps({'legacy_rows': len(legacy['rows']), 'managed_rows': len(changed['rows'])}))
    elif case == 'writer-transition':
        final_event = f.comparison['events'].pop()
        f.comparison['tier'] = 'claimed'
        before = copy.deepcopy(f.doc)
        request = {'operation': 'record-freshness', 'changes': {'row_id': f.row['id'], 'resource_id': 'tree',
                   'model_id': MODEL, 'event': final_event}, 'expect_data': f.m['D'].digest(before),
                   'expect_revision': before['revision'], 'at': STAMP, 'commit_id': str(uuid.uuid4()),
                   'proposal_sha256': '0' * 64}
        result = f.m['W'].transformed(f.ctx, before, request)
        assert before == f.doc, 'writer preview mutated old data'
        assert result['rows'][0]['freshness']['skills'][0]['comparisons'][0]['tier'] == 'proven'
        assert result['rows'][0]['lifecycle']['state'] == 'prepared', 'assurance promotion activated a row'
        assert result['revision'] == before['revision'] + 1
        forged = copy.deepcopy(request)
        del forged['changes']['event']['comparison']['without_skill_evidence_ref']
        try:
            f.m['W'].transformed(f.ctx, before, forged)
        except f.m['D'].Problem as exc:
            assert exc.code in (1, 2)
        else:
            raise AssertionError('writer accepted a promotion without both outcomes')
        assert before == f.doc, 'refused writer preview changed its input'
    elif case == 'render':
        page = f.m['render'].render(f.doc).decode()
        assert 'claimed' in page and MODEL in page, 'generated page lacks exact-model tier'
        assert 'comparison pending' in page.lower(), 'generated page lacks the evidence gap'
    elif case == 'schema':
        f.m['D'].validate(f.doc)
        bad = copy.deepcopy(f.doc)
        bad['rows'][0]['freshness']['skills'][0]['comparisons'][0]['tier'] = 'trusted'
        try:
            f.m['D'].validate(bad)
        except f.m['D'].Problem as exc:
            assert exc.code == 2
        else:
            raise AssertionError('unknown assurance tier accepted')
    elif case in ('claimed-use', 'important-use', 'unproven-owner') or case.startswith('owner-'):
        V, D = f.m['V'], f.m['D']
        kwargs = {}
        if case == 'important-use':
            assert 'importance' in inspect.signature(V.resolve).parameters, 'important-use advice input is absent'
            kwargs['importance'] = 'important'
        owner = case == 'unproven-owner' or case.startswith('owner-')
        if owner:
            assert 'freshness_decision_refs' in inspect.signature(V.resolve).parameters, 'plural owner exception coverage input is absent'
            assert 'route' in inspect.signature(V.resolve).parameters, 'explicit use/pattern route input is absent'
            kwargs.update(freshness_decision_refs=f.decision_refs, route=f.delivery_route)
        with (nullcontext() if f.m['W'].seed_document()['schema_version'] == 2 else
              patch.object(V, 'load_current', return_value=(f.doc, D.encoded(f.doc)))):
            if case == 'unproven-owner':
                refusal(f, lambda: V.resolve(f.ctx, f.row['id'], MODEL), 'O5_EXCEPTION_COVERAGE')
            if case in OWNER_REFUSALS:
                refusal(f, lambda: V.resolve(f.ctx, f.row['id'], MODEL, **kwargs), OWNER_REFUSALS[case])
                return
            view = V.resolve(f.ctx, f.row['id'], MODEL, **kwargs)
            assert view.get('assurance_tier') == ('unproven' if owner else 'claimed'), 'ordinary view missing the expected assurance_tier'
            assert view['state'] == 'prepared-delivery'
            if owner:
                assert view['freshness_decision_refs'] == sorted(f.decision_refs), 'consent coverage missing from view/cache'
                assert view['route'] == f.delivery_route
            if case == 'important-use':
                assert view['testing_recommended'] is True, 'test suggestion omitted'
            # A fallback model must not inherit this result through its cache.
            try:
                V.resolve(f.ctx, f.row['id'], 'different-model', cached=view, **kwargs)
            except D.Problem:
                pass
            else:
                raise AssertionError('cached tier crossed model identity')
    else:
        expected = {'claimed': 'claimed', 'comparison': 'proven', 'checked-runs': 'proven',
                    'drop-proven': 'claimed', 'drop-claimed': 'unproven', 'taste': 'proven',
                    'unhelpful-comparison': 'claimed', 'unproven': 'unproven', 'old-date': 'unproven'}[case]
        result = f.evaluate()
        tier(result, expected)
        if case == 'checked-runs':
            assert result['skills'][0]['checked_successes'] == HOW_TO_MINIMUM
        if case == 'comparison':
            pair = f.comparison['events'][-1]['comparison']
            pair['without_skill_evidence_ref'] = pair['with_skill_evidence_ref']
            refusal(f, f.evaluate)


INSTANCE_DATA = None
CASES = ('claimed', 'comparison', 'taste', 'checked-runs', 'drop-proven', 'drop-claimed',
         'no-record', 'bad-pair', 'too-few-runs', 'duplicate-runs', 'unhelpful-comparison',
         'writer-transition', 'migration', 'render', 'schema', 'unproven', 'old-date',
         'claimed-use', 'important-use', 'unproven-owner',
         'changed-input', 'changed-definition', 'judgement-input', 'taste-other-human',
         'owner-wrong-subject', 'owner-pattern', 'owner-route-mismatch', 'owner-old-date',
         'owner-unknown-date', 'owner-date-unacknowledged', 'owner-other-human',
         'owner-closure', 'owner-closure-missing', 'owner-closure-mismatch')


def main():
    parser = Parser(description=__doc__)
    parser.add_argument('--build', required=True, type=Path)
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--instance-data', type=Path,
                        help='frozen instance register data; default: the staged build-relative '
                             'compatibility fixture (the historical layout-1 tuple)')
    args = parser.parse_args()
    if not os.environ.get('TMPDIR') or not Path(os.environ['TMPDIR']).is_dir():
        print('PROBE FAILED: explicit existing TMPDIR required')
        return 2
    try:
        build = args.build.resolve(strict=True)
    except OSError as exc:
        print('PROBE FAILED: ' + str(exc))
        return 2
    if not (build / 'adopt/adopt_freshness.py').is_file():
        print('PROBE FAILED: missing staged freshness module')
        return 2
    global INSTANCE_DATA
    INSTANCE_DATA = args.instance_data or build / 'fixtures/instance-layout1/.claude/adopt/capability-register.json'
    if not INSTANCE_DATA.is_file():
        print('PROBE FAILED: frozen instance data not found: ' + str(INSTANCE_DATA) +
              ' (pass --instance-data in an installed position)')
        return 2
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(build / 'adopt'))
    modules = {key: importlib.import_module(name) for key, name in {
        'D': 'adopt_data', 'W': 'adopt_register', 'S': 'adopt_snapshot', 'R': 'adopt_resources',
        'F': 'adopt_freshness', 'G': 'adopt_migrate', 'V': 'adopt_manifest', 'render': 'adopt_render'}.items()}
    root = Path(subprocess.check_output(['/usr/bin/mktemp', '-d', os.path.join(os.environ['TMPDIR'], 'adopt.XXXXXXXX')], text=True).strip()).resolve(strict=True)
    failed, total, broken = 0, 0, False
    try:
        control_dir = root / 'control'
        control_dir.mkdir()
        control = Fixture(control_dir, modules)
        # A native v1 control proves that the staged premise really qualifies.
        if modules['W'].seed_document()['schema_version'] == 1:
            assert control.evaluate() == ['old-task']
            print('CONTROL native v1 qualification refs=1')
        assert modules['D'].control() > 0 and modules['S'].controls() > 0
        total += 1
        print('PASS decoder and typed snapshot controls')
        for case in (args.case,) if args.case else CASES:
            case_dir = root / case
            case_dir.mkdir()
            f = Fixture(case_dir, modules)
            configure(f, case)
            permissions(case_dir, True)
            before = manifest(case_dir)
            fixture_controls(f, case)
            total += 1
            try:
                check_case(f, case, build)
                print('PASS ' + case)
            except (AssertionError, modules['D'].Problem) as exc:
                failed += 1
                print('FAIL ' + case + ': ' + str(exc))
            finally:
                after = manifest(case_dir)
                total += 1
                same = before == after and any(k.endswith('SKILL.md') for k in before)
                failed += int(not same)
                print(('PASS ' if same else 'FAIL ') + case + ' complete read-only fixture manifest')
                print('NO_WRITE ' + json.dumps({'case': case, 'before': before, 'after': after}, sort_keys=True))
                permissions(case_dir, False)
        # Literal source grep, with its own planted controls on this run.
        pattern = re.compile(r'\b(?:write_text|write_bytes|mkdir|unlink|chmod|rmtree|Popen)\s*\(|\bos\.(?:write|replace|remove|rename)\s*\(|\bsubprocess\.|\.open\([^\n]*["\x27][wax]|\bopen\([^\n]*,[ ]*["\x27][wax]')
        hits = {name: [(n, line.strip()) for n, line in enumerate((build / 'adopt' / name).read_text().splitlines(), 1)
                       if pattern.search(line)] for name in ('adopt_freshness.py', 'adopt_migrate.py', 'adopt_render.py',
                       'adopt_data.py', 'adopt_resources.py', 'adopt_manifest.py', 'adopt_snapshot.py') +
                       (('adopt_compat_v1.py',) if modules['W'].seed_document()['schema_version'] == 2 else ())}
        planted = ["path.write_text('control')", 'os.replace(a, b)', "open(path, 'w')"]
        controls = sum(bool(pattern.search(line)) for line in planted)
        total += 1
        ok = not any(hits.values()) and controls == len(planted)
        failed += int(not ok)
        print(('PASS ' if ok else 'FAIL ') + 'source write grep with positive controls')
        print('SOURCE_SCAN ' + json.dumps({'hits': hits, 'control_hits': controls}, sort_keys=True))
    except Exception as exc:
        broken = True
        failed += 1
        total += 1
        print('PROBE FAILED: ' + type(exc).__name__ + ': ' + str(exc))
    finally:
        permissions(root, False)
        shutil.rmtree(root)
    print(f'FAIL {failed}/{total}' if failed or broken else f'PASS {total}/{total}')
    return 2 if broken else int(bool(failed))


if __name__ == '__main__':
    sys.exit(main())
