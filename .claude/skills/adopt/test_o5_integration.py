"""Native O5 writer, recovery and binding tests; only disposable fixtures mutate."""
import copy
import importlib
import json
from pathlib import Path
import uuid
from test_o5 import Fixture, configure, STAMP, MODEL, manifest, permissions


def run(t):
    try:
        _run(t)
    finally:
        for root in t.ROOT.glob('o5-*'):
            permissions(root, False)


def _run(t):
    modules = {key: importlib.import_module(name) for key, name in {
        'D': 'adopt_data', 'W': 'adopt_register', 'S': 'adopt_snapshot', 'R': 'adopt_resources',
        'F': 'adopt_freshness', 'G': 'adopt_migrate', 'V': 'adopt_manifest', 'render': 'adopt_render'}.items()}
    D, W, F, R, G, V = (modules[k] for k in ('D', 'W', 'F', 'R', 'G', 'V'))
    start = t.COUNT

    def fresh(name, case='comparison'):
        root = t.ROOT / ('o5-' + name)
        root.mkdir()
        f = Fixture(root, modules)
        configure(f, case)
        return f

    def persist(f, v1=False):
        if v1:
            from adopt_compat_v1 import validate, render
        else:
            validate, render = D.validate, modules['render'].render
        validate(f.doc)
        raw, page = D.encoded(f.doc), render(f.doc)
        receipt = D.encoded({'register_id': f.doc['register_id'], 'revision': f.doc['revision'],
            'data_sha256': D.sha(raw), 'page_sha256': D.sha(page), 'transaction_id': str(uuid.uuid4())})
        for path, content in ((f.ctx.data, raw), (f.ctx.page, page), (f.ctx.receipt, receipt)):
            W.publish(path, content)
            W.archive(f.ctx, content)

    def promotion(name):
        f = fresh(name)
        event = f.comparison['events'].pop()
        f.comparison['tier'] = 'claimed'
        f.acceptance()
        persist(f)
        request = W.proposal(f.ctx, 'record-freshness', {'row_id': f.row['id'], 'resource_id': 'tree',
                            'model_id': MODEL, 'event': event})
        return f, request

    f, request = promotion('writer')
    before = manifest(f.root)
    preview = W.preview(f.ctx, request)
    t.check(manifest(f.root) == before and 'proven' in preview['page_diff'] and
            preview['shared_resource_rows'] == [f.row['id']], 'O5 preview is read-only and names shared users')
    t.check(preview['invalidated_resource_evidence'] == [{'row_id': f.row['id'],
            'evidence_refs': sorted(f.row['acceptance']['evidence_refs'])}],
            'O5 prepared preview names resource evidence invalidated by changed assurance')
    result = W.commit(f.ctx, request)
    page = modules['render'].render(result).decode()
    t.check('with skill with-skill (pass)' in page and 'without skill without-skill (fail)' in page and
            'judgement judgement (pass): supports' in page,
            'O5 page labels both captured outcomes and the judgement result')
    t.check(result['rows'][0]['lifecycle']['state'] == 'prepared' and result['revision'] == f.doc['revision'] + 1,
            'O5 native writer promotes once without activation')
    t.refuses(lambda: W.commit(f.ctx, request), 'O5 stale request refused', codes=(3,), ctx=f.ctx)
    replay = W.proposal(f.ctx, 'record-freshness', request['changes'])
    t.refuses(lambda: W.commit(f.ctx, replay), 'O5 repeated event ID refused', ctx=f.ctx)
    for variant in ('omit', 'forge'):
        altered = copy.deepcopy(result['rows'])
        assessment = altered[0]['freshness']['skills'][0]['comparisons'][0]
        if variant == 'omit':
            assessment['events'].pop()
            assessment['tier'] = 'claimed'
        else:
            assessment['events'][0]['reason'] = 'Unreviewed replacement'
        t.refuses(lambda: W.commit(f.ctx, W.proposal(f.ctx, 'edit', {'rows': altered})),
                  'O5 ordinary edit ' + variant + ' history refused', ctx=f.ctx)
    altered = copy.deepcopy(result['rows'])
    altered[0]['freshness']['skills'][0]['comparisons'][0]['events'] = []
    reconcile = W.proposal(f.ctx, 'reconcile-data', {'typed_changes': {'rows': altered}},
                           [D.sha(x) for x in W.tuple_bytes(f.ctx)])
    t.refuses(lambda: W.commit(f.ctx, reconcile), 'O5 reconciliation cannot omit history', ctx=f.ctx)

    f, request = promotion('timezone')
    request['at'] = STAMP
    request['changes']['event']['at'] = '2026-01-02T11:30:00-01:00'
    request['proposal_sha256'] = D.digest({k: v for k, v in request.items() if k != 'proposal_sha256'})
    t.refuses(lambda: W.commit(f.ctx, request), 'O5 future event with an earlier clock spelling refuses', ctx=f.ctx)
    request['changes']['event']['at'] = '2026-01-02T13:00:00+01:00'
    request['proposal_sha256'] = D.digest({k: v for k, v in request.items() if k != 'proposal_sha256'})
    t.check(W.commit(f.ctx, request)['rows'][0]['freshness']['skills'][0]['comparisons'][0]['tier'] == 'proven',
            'O5 equivalent RFC 3339 offset permits same-instant recording')

    f, request = promotion('shared-installation')
    path = f.ctx.home / 'other-input'
    path.write_bytes(b'Shared installation input')
    resource = t.resource('other-input', 'file', path,
        {'sha256': D.sha(path.read_bytes()), 'use': 'Fixture read'}, ['file-content', 'input-use'],
        f.doc['installations'][0]['id'])
    other = t.normal_row('other-row', [resource])
    other['installation_ids'] = []
    f.doc['resources'].append(resource)
    f.doc['rows'].append(other)
    f.doc['jobs'].append({'id': 'other-row-job', 'label': 'Other', 'definition': 'Other fixture use', 'notes': []})
    persist(f)
    request = W.proposal(f.ctx, 'record-freshness', request['changes'])
    t.check([b['resource_id'] for b in D.expansion(f.doc, other)['bindings']] == ['other-input'],
            'O5 shared-installation control uses a different resource')
    t.check(W.preview(f.ctx, request)['shared_resource_rows'] == sorted([f.row['id'], other['id']]),
            'O5 G7 preview includes other resource users of the same installation')

    for phase in ('before-data', 'after-data'):
        f, request = promotion('revocation-' + phase)
        record = D.index(f.doc, 'evidence')['without-skill']
        path = f.ctx.locate(record['artefact']['locator'])
        original, before = path.read_bytes(), W.tuple_bytes(f.ctx)
        def interrupt(point):
            if point == phase:
                if phase == 'after-data':
                    raise RuntimeError('fixture interrupted publication')
                path.write_bytes(original + b' ')
        if phase == 'before-data':
            t.refuses(lambda: W.commit(f.ctx, request, hook=interrupt),
                      'O5 prepared promotion revalidates baseline before publication', ctx=f.ctx)
            t.check(W.tuple_bytes(f.ctx) == before, 'O5 failed final gate leaves committed tuple unchanged')
        else:
            try:
                W.commit(f.ctx, request, hook=interrupt)
            except RuntimeError:
                pass
            t.check(f.ctx.pending.is_file(), 'O5 interrupted promotion leaves a durable journal')
            path.write_bytes(original + b' ')
            t.refuses(lambda: W.recover(f.ctx), 'O5 prepared promotion recovery rechecks baseline', ctx=f.ctx)
            path.write_bytes(original)
            t.check(W.recover(f.ctx) == 'new', 'O5 exact restored baseline permits recovery')

    f = fresh('active-drop', 'claimed-use')
    active = W.commit(f.ctx, W.proposal(f.ctx, 'activate', {'row_ids': [f.row['id']], 'reason': 'Fixture activation'}))
    f.run('poor-use', 'with-skill', result='fail')
    event = {'id': 'drop-event', 'action': 'drop', 'from_tier': 'claimed', 'to_tier': 'unproven',
             'at': STAMP, 'reason': 'Objective poor use', 'evidence_refs': ['poor-use'], 'decision_refs': []}
    records = D.index(f.doc, 'evidence')
    changes = {'row_id': f.row['id'], 'resource_id': 'tree', 'model_id': MODEL, 'event': event,
               'evidence': [records['poor-use'], records['frozen-task']]}
    t.refuses(lambda: W.commit(f.ctx, W.proposal(f.ctx, 'record-freshness', changes)),
              'O5 active assurance needs explicit deactivation', ctx=f.ctx)
    changes['deactivate_row_ids'] = [f.row['id']]
    request = W.proposal(f.ctx, 'record-freshness', changes)
    t.check(W.preview(f.ctx, request)['invalidated_proofs'] == [f.row['id']], 'O5 preview names invalidated activation')
    dropped = W.commit(f.ctx, request)
    t.check(dropped['rows'][0]['lifecycle']['state'] == 'prepared' and
            F.evaluate(dropped, dropped['rows'][0], f.ctx, MODEL)['tier'] == 'unproven',
            'O5 atomic evidence/drop explicitly deactivates and retains the claim')
    old_claim = copy.deepcopy(f.comparison['events'][0])
    old_claim['id'] = 'replayed-claim'
    t.refuses(lambda: W.commit(f.ctx, W.proposal(f.ctx, 'record-freshness', {
        'row_id': f.row['id'], 'resource_id': 'tree', 'model_id': MODEL, 'event': old_claim})),
        'O5 prior claim cannot silently repromote after a drop', ctx=f.ctx)

    for case in ('unproven-owner', 'owner-pattern', 'owner-closure'):
        f = fresh('activation-' + case, case)
        selected = [{'model_id': MODEL, 'route': f.delivery_route, 'freshness_decision_refs': f.decision_refs}]
        changes = {'row_ids': [f.row['id']], 'reason': 'Exact fixture consent',
                   'freshness_decisions': {f.row['id']: selected}}
        active = W.commit(f.ctx, W.proposal(f.ctx, 'activate', changes))
        t.check(active['rows'][0]['lifecycle']['activation']['freshness_evaluation'][0]['tier'] == 'unproven',
                'O5 ' + case + ' activation retains tier and selected consent')
        view = V.resolve(f.ctx, f.row['id'], MODEL, route=f.delivery_route, freshness_decision_refs=f.decision_refs)
        t.check(view['assurance_tier'] == 'unproven' and view['state'] == 'active', 'O5 ' + case + ' real-loader active delivery')
        bad = copy.deepcopy(active)
        bad['policy']['owner_identity'] = 'another-owner'
        t.refuses(lambda: W.commit(f.ctx, W.proposal(f.ctx, 'edit', {'policy': bad['policy']})),
                  'O5 owner identity change invalidates activation', ctx=f.ctx)
        consent = D.index(active, 'evidence')[f.decision_refs[0]]
        original = f.ctx.locate(consent['artefact']['locator']).read_bytes()
        def revoke(point):
            if point == 'before-data':
                f.ctx.locate(consent['artefact']['locator']).write_bytes(original + b' ')
        t.refuses(lambda: W.commit(f.ctx, W.proposal(f.ctx, 'edit', {}), hook=revoke),
                  'O5 ' + case + ' consent rechecked at publication', ctx=f.ctx)
        f.ctx.locate(consent['artefact']['locator']).write_bytes(original)
        t.check(V.resolve(f.ctx, f.row['id'], MODEL, route=f.delivery_route,
                freshness_decision_refs=f.decision_refs) == view, 'O5 restored consent positive control')

    f = fresh('bindings')
    t.check(f.evaluate()['tier'] == 'proven', 'O5 exact frozen comparison positive control')
    frozen = D.index(f.doc, 'evidence')['frozen-task']
    baseline_digest = D.digest(D.expansion(f.doc, f.row))
    for eid in ('frozen-task', 'without-skill', 'judgement'):
        bad = copy.deepcopy(f.doc)
        D.index(bad, 'evidence')[eid]['result'] = 'unknown'
        t.check(D.digest(D.expansion(bad, bad['rows'][0])) != baseline_digest,
                'O5 transitive activation evidence includes ' + eid)
        t.refuses(lambda: F.evaluate(bad, bad['rows'][0], f.ctx, MODEL), 'O5 revoked ' + eid + ' refuses')
    for variant in ('missing', 'cycle', 'duplicate'):
        bad = copy.deepcopy(f.doc)
        if variant == 'missing':
            D.index(bad, 'evidence')['with-skill']['subject']['task_evidence_ref'] = 'absent'
        elif variant == 'cycle':
            D.index(bad, 'evidence')['with-skill']['subject']['task_evidence_ref'] = 'judgement'
        else:
            bad['rows'][0]['freshness']['skills'][0]['comparisons'][0]['claim_evidence_refs'] *= 2
        t.refuses(lambda: D.validate(bad), 'O5 evidence reference ' + variant + ' refused')
    t.check(len([r for r in D.expansion(f.doc, f.row)['evidence'] if r['id'] == 'frozen-task']) == 1,
            'O5 shared frozen reference deduplicates without a false cycle')
    for variant, value in (('boolean', True), ('zero', 0)):
        bad = copy.deepcopy(f.doc)
        bad['policy']['how_to_successes_required'] = value
        t.refuses(lambda: D.validate(bad), 'O5 invalid threshold ' + variant)
    frozen = D.index(f.doc, 'evidence')['frozen-task']
    f.evidence('frozen-task', frozen['subject'], {}, kind='captured-source', at=frozen['observed_at'])
    t.refuses(f.evaluate, 'O5 missing frozen capture is a broken premise', codes=(2,))
    f = fresh('threshold', 'checked-runs')
    t.check(f.evaluate()['skills'][0]['checked_successes'] == len(f.comparison['events'][-1]['evidence_refs']),
            'O5 count derives from checked run IDs')
    f.doc['policy']['how_to_successes_required'] += 1
    t.refuses(f.evaluate, 'O5 raised threshold invalidates existing promotion')

    f = fresh('new-promotion', 'drop-proven')
    pair = f.paired()
    # New evidence IDs and distinct run IDs must postdate the recorded drop.
    task = f.frozen_task('new-frozen')
    f.run('new-with', 'with-skill', at='2026-01-02T13:00:00Z', task=task)
    f.run('new-without', 'without-skill', result='fail', at='2026-01-02T14:00:00Z', task=task)
    f.evidence('new-judgement', {'type': 'skill-comparison', 'scope_sha256': f.scope(), **task,
        'with_skill_evidence_ref': 'new-with', 'without_skill_evidence_ref': 'new-without'},
        {'output': 'Both outputs compared.', 'verdict': 'supports', 'criterion': 'exact-fixture',
         'positive_control': True, 'negative_control': True}, at='2026-01-02T15:00:00Z')
    event = f.event('comparison', 'claimed', 'proven', comparison={**task,
        'with_skill_evidence_ref': 'new-with', 'without_skill_evidence_ref': 'new-without',
        'judgement_evidence_ref': 'new-judgement', 'verdict': 'supports'})
    event['at'] = '2026-01-02T15:00:00Z'
    f.comparison['tier'] = 'proven'
    t.check(f.evaluate()['tier'] == 'proven', 'O5 fresh post-drop comparison promotes again')
    event['comparison'] = pair
    t.refuses(f.evaluate, 'O5 old pair cannot repromote after a drop')

    f = fresh('taste-drop', 'taste')
    task = f.frozen_task()
    f.evidence('taste-rejection', {'type': 'skill-run', 'scope_sha256': f.scope(), **task,
        'run_id': 'taste-rejected-run', 'mode': 'with-skill'},
        {'output': 'The owner rejects this use.', 'criterion': 'exact-fixture', 'human_judge': 'fixture-owner'},
        kind='human', result='fail')
    f.event('drop', 'proven', 'claimed', evidence_refs=['taste-rejection'], decision_refs=[])
    f.comparison['tier'] = 'claimed'
    t.check(f.evaluate()['tier'] == 'claimed', 'O5 captured owner rejection drops taste assurance')
    f.doc['policy']['owner_identity'] = None
    t.refuses(f.evaluate, 'O5 null owner identity cannot support taste evidence')

    f = fresh('partial-how-to', 'checked-runs')
    checked = f.comparison['events'][-1]
    second = checked['evidence_refs'].pop()
    checked.update(to_tier='claimed', successful_run_count=1)
    f.comparison['tier'] = 'claimed'
    t.check(f.evaluate()['skills'][0]['checked_successes'] == 1, 'O5 partial checked batch stays claimed')
    f.event('checked-runs', 'claimed', 'proven', evidence_refs=[second], successful_run_count=1)
    f.comparison['tier'] = 'proven'
    t.check(f.evaluate()['tier'] == 'proven', 'O5 distinct checked batches accumulate to the policy threshold')

    for revoke in (False, True):
        f = fresh('maintenance-' + str(revoke).lower(), 'unproven-owner')
        M = importlib.import_module('adopt_maintenance')
        plan = {'id': 'maintenance-consent', 'expect_data': D.sha(f.ctx.data.read_bytes()),
                'scope': [str(f.ctx.home / 'tree')], 'before': modules['S'].snapshot(f.ctx.home),
                'declaration': [], 'steps': [], 'changes': {}, 'allowed_roots': [],
                'freshness_decisions': {f.row['id']: [{'model_id': MODEL, 'route': f.delivery_route,
                                                     'freshness_decision_refs': f.decision_refs}]}}
        def maintenance_hook(phase, coordinator):
            if phase == 'reserved':
                held, _ = D.load_current(f.ctx)
                proposed = {'row_id': f.row['id'], 'resource_id': 'tree', 'model_id': MODEL,
                            'event': {'id': 'held-event', 'action': 'claim', 'from_tier': 'unproven',
                                      'to_tier': 'claimed', 'at': STAMP, 'reason': 'Held fixture',
                                      'evidence_refs': ['author-claim']}}
                t.refuses(lambda: W.commit(f.ctx, W.proposal(f.ctx, 'record-freshness', proposed)),
                          'O5 reservation blocks tier recording', ctx=f.ctx)
            if revoke and phase == 'verifying':
                rec = D.index(f.doc, 'evidence')['owner-exception']
                path = f.ctx.locate(rec['artefact']['locator'])
                path.write_bytes(path.read_bytes() + b' ')
        if revoke:
            t.refuses(lambda: M.run(f.ctx, plan, D.digest(plan), hook=maintenance_hook),
                      'O5 maintenance release rechecks selected consent')
            t.check(bool(D.load_current(f.ctx)[0]['maintenance']), 'O5 failed consent retains maintenance hold')
        else:
            result = M.run(f.ctx, plan, D.digest(plan), hook=maintenance_hook)
            t.check(result['state'] == 'prepared' and not D.load_current(f.ctx)[0]['maintenance'],
                    'O5 explicit unproven consent permits checked maintenance release')

    from adopt_compat_v1 import SCHEMA as schema_v1
    t.check(D.read_json(Path(__file__).with_name('register-schema-v1.json')) == schema_v1,
            'O5 frozen v1 schema and local reference resolver match the published archive')

    for phase in ('before-data', 'after-data'):
        f = fresh('upgrade-' + phase, 'migration')
        persist(f, v1=True)
        old_tuple = W.tuple_bytes(f.ctx)
        request = W.proposal(f.ctx, 'upgrade-freshness')
        t.check(W.preview(f.ctx, request)['invalidated_proofs'] == [f.row['id']], 'O5 v1 activation invalidation preview')
        def stop(point):
            if point == phase:
                raise RuntimeError('fixture interrupted upgrade')
        try:
            W.commit(f.ctx, request, hook=stop)
        except RuntimeError:
            pass
        t.check(f.ctx.pending.is_file(), 'O5 upgrade interruption is journalled ' + phase)
        t.refuses(lambda: W.proposal(f.ctx, 'upgrade-freshness'), 'O5 pending upgrade refuses second proposal')
        outcome = W.recover(f.ctx)
        t.check(outcome == ('old' if phase == 'before-data' else 'new'), 'O5 versioned upgrade recovery ' + phase)
        if outcome == 'old':
            t.check(W.tuple_bytes(f.ctx) == old_tuple, 'O5 rollback restores byte-exact v1 tuple')
            W.commit(f.ctx, W.proposal(f.ctx, 'upgrade-freshness'))
        upgraded, _ = D.load_current(f.ctx)
        t.check(upgraded['revision'] == f.doc['revision'] + 1 and upgraded['rows'][0]['lifecycle']['state'] == 'prepared',
                'O5 upgrade writer increments once and removes old activation')
        t.check(all((f.ctx.objects / D.sha(raw)).read_bytes() == raw for raw in old_tuple),
                'O5 upgrade archives exact old data receipt and page')
        t.check(G.upgrade_freshness(upgraded, at=STAMP) == upgraded, 'O5 upgraded transform is idempotent')

    f = fresh('upgrade-drift', 'migration')
    persist(f, v1=True)
    f.ctx.page.write_bytes(f.ctx.page.read_bytes() + b'\n')
    t.refuses(lambda: W.proposal(f.ctx, 'upgrade-freshness'), 'O5 v1 page drift refuses upgrade')
    persist(f, v1=True)
    receipt = D.read_json(f.ctx.receipt)
    receipt['data_sha256'] = '0' * 64
    f.ctx.receipt.write_bytes(D.encoded(receipt))
    t.refuses(lambda: W.proposal(f.ctx, 'upgrade-freshness'), 'O5 v1 receipt drift refuses upgrade')

    ctx = t.fixture('o5-upgrade-non-skill')
    doc, _ = D.load_current(ctx)
    row = t.add_cli(doc, ctx, 'plain-tool')
    doc['schema_version'] = 1
    # Frozen v1 data has page layout 1 only; the current seed starts at a later layout.
    doc['page']['layout_version'] = 1
    doc['policy']['freshness_rule_version'] = 1
    doc['policy'].pop('owner_identity')
    doc['policy'].pop('how_to_successes_required')
    t.bind_evidence(doc, ctx)
    checks = R.prove(doc, row, ctx)
    row['lifecycle'] = {'state': 'active', 'changed_at': STAMP, 'reason': 'Historical fixture', 'decision_refs': [],
        'activation': {'id': str(uuid.uuid4()), 'register_id': doc['register_id'], 'row_id': row['id'],
            'definition_sha256': D.digest(D.expansion(doc, row)), 'verified_at': STAMP, 'checks': checks,
            'freshness_evaluation': [], 'evidence_refs': sorted(c['evidence_ref'] for c in checks if 'evidence_ref' in c)}}
    G.validate_v1(doc)
    upgraded = G.upgrade_freshness(doc, at=STAMP)
    t.check(upgraded['rows'][0]['freshness'] == row['freshness'] and
            upgraded['rows'][0]['lifecycle']['state'] == 'prepared' and 'activation' not in upgraded['rows'][0]['lifecycle'],
            'O5 non-skill upgrade preserves non-applicability and invalidates the old activation')
    print('O5_INTEGRATION ' + json.dumps({'assertions': t.COUNT - start}), flush=True)
