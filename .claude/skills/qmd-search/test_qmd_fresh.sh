#!/bin/sh
# Run from any directory. Only mktemp fixtures under --tmp-parent are written.
# Usage: sh test_qmd_fresh.sh [--stage DIR --vault BASELINE]
#                           [--real-qmd PATH --model LOCAL_GGUF]
# Installed mode skips build diff/baseline checks; all fixture behaviour legs run.
# --stage reads DIR/diffs and requires --vault as its read-only pre-install
# baseline, never search data. Without --stage, --vault is ignored.
# --script PATH permits a deliberately broken gate as a negative control.
# Default: stub logic legs. --real-qmd adds real indexing and vector-query legs
# with a copied local model, private HOME/config/cache/database and no download.
# --stub-embed replaces only embed in the real-index legs when the local runtime
# cannot embed. An unsuccessful embedding preflight also explicitly falls back
# to lexical legs. Semantic acceptance is SKIP, never PASS, in either case.
# Exit 0 = PASS; 1 = failed assertions; 2 = PROBE FAILED (broken test premise).
exec python3 -B - "$0" "$@" <<'PY_QMD_FRESH_SUITE'
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import time
from urllib.parse import unquote, urlsplit

suite = Path(sys.argv[1]).resolve()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--stage', type=Path, help='build directory containing diffs/')
parser.add_argument('--vault', type=Path, help='read-only pre-install baseline for --stage; ignored otherwise')
parser.add_argument('--script', type=Path, default=suite.with_name('qmd-fresh.sh'))
parser.add_argument('--tmp-parent', type=Path, default=suite.parent.parent)
parser.add_argument('--real-qmd', type=Path)
parser.add_argument('--model', type=Path)
parser.add_argument('--stub-embed', action='store_true')
args = parser.parse_args(sys.argv[2:])
gate = args.script.resolve()
live_check = suite.with_name('qmd-live-check.sh')
# Per-process hang bound, set by judgement, unmeasured; never a freshness age.
TIMEOUT = 240
SECOND = 1_000_000_000  # Nanoseconds per second, for deterministic fixture mtimes.
results = []
skips = []
scratch = None

class Premise(Exception):
    pass

def require(condition, reason):
    if not condition:
        raise AssertionError(reason)

def run(argv, **kwargs):
    payload = kwargs.pop('input', None)
    with subprocess.Popen(argv, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, start_new_session=True, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(payload, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)

def checked(argv, **kwargs):
    result = run(argv, **kwargs)
    if result.returncode:
        raise Premise(f'{Path(argv[0]).name} exited {result.returncode}: '
                      f'{result.stdout}\n{result.stderr}')
    return result

def leg(name, action):
    try:
        detail = action() or ''
        results.append(True)
        print(f'PASS {name}' + (f': {detail}' if detail else ''), flush=True)
    except Premise:
        raise
    except (AssertionError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        results.append(False)
        print(f'FAIL {name}: {exc}', flush=True)

def skip(name, reason):
    skips.append(name)
    print(f'SKIP {name}: {reason}', flush=True)

STUB = r'''import json, os, sys
from pathlib import Path
root = Path(os.environ['FIXTURE_VAULT'])
state = Path(os.environ['FIXTURE_STATE'])
command = sys.argv[1]
with (state / 'calls').open('a') as log:
    log.write(command + '\n')
if command == os.environ.get('FAIL_QMD'):
    print('planted qmd failure', file=sys.stderr)
    sys.exit(1)
if command == 'update':
    docs = {str(p.relative_to(root)): p.read_text()
            for tree in ('wiki', 'raw') for p in (root / tree).rglob('*.md')}
    (state / 'pending.json').write_text(json.dumps(docs))
elif command == 'embed':
    (state / 'index.json').write_bytes((state / 'pending.json').read_bytes())
    if os.environ.get('EDIT_DURING_EMBED'):
        page = root / 'wiki' / 'base.md'
        page.write_text('CONTROLANTLER changed DURINGEMBED\n')
elif command == 'search':
    docs = json.loads((state / 'index.json').read_text())
    print(json.dumps([{'file': name, 'body': body} for name, body in docs.items()
                      if sys.argv[2].lower() in body.lower()]))
elif command == 'query':
    assert sys.argv[2].startswith('vec: ') and '--no-rerank' in sys.argv
    (state / 'query-args.json').write_text(json.dumps(sys.argv[1:]))
    if os.environ.get('CHANGE_DURING_QUERY'):
        Path(os.environ['CHANGE_DURING_QUERY']).write_text('Changed during the vector query\n')
    if 'QUERY_OUTPUT' in os.environ:
        print(os.environ['QUERY_OUTPUT'])
        sys.exit(0)
    docs = json.loads((state / 'index.json').read_text())
    # All indexed wiki pages are candidates. Tests must compare exact paths and
    # bodies, since an unrelated hit cannot prove creation, editing or deletion.
    print(json.dumps([{'file': str(root / name), 'body': body} for name, body in docs.items()
                      if name.startswith('wiki/')]))
else:
    print('unexpected fixture command', file=sys.stderr)
    sys.exit(2)
'''

def executable(path, body):
    path.write_text(body)
    path.chmod(0o755)

class Fixture:
    serial = 0

    def __init__(self, real=False, stub_embed=None):
        Fixture.serial += 1
        self.base = scratch / f'case-{Fixture.serial}'
        self.root = self.base / "vault's notes"
        self.cache = self.base / 'cache'
        self.state = self.base / 'state'
        self.bin = self.base / 'bin'
        self.home = self.base / 'home'
        self.config = self.base / 'config'
        for path in (self.root / 'wiki', self.root / 'raw', self.cache,
                     self.state, self.bin, self.home, self.config):
            path.mkdir(parents=True, exist_ok=True)
        (self.root / 'wiki/base.md').write_text('CONTROLANTLER original page\n')
        (self.root / 'raw/control.md').write_text('RAWCONTROL source\n')
        self.env = {'PATH': str(self.bin) + os.pathsep + os.environ.get('PATH', os.defpath),
                    'HOME': str(self.home), 'XDG_CACHE_HOME': str(self.cache),
                    'XDG_CONFIG_HOME': str(self.config), 'QMD_CONFIG_DIR': str(self.config),
                    'INDEX_PATH': str(self.cache / 'index.sqlite'),
                    'CLAUDE_PROJECT_DIR': str(self.root), 'PWD': str(self.root),
                    'TMPDIR': str(self.base), 'FIXTURE_VAULT': str(self.root),
                    'FIXTURE_STATE': str(self.state), 'LC_ALL': 'C',
                    'PYTHONDONTWRITEBYTECODE': '1'}
        self.real = real
        self.stub_embed = args.stub_embed if stub_embed is None else stub_embed
        if real:
            self.env.update(QMD_FORCE_CPU='1', QMD_EMBED_PARALLELISM='1')
            if not self.stub_embed:
                self.env['QMD_EMBED_MODEL'] = str(model_copy)
            # Local paths only; neither URI resolution nor GPU setup needs a download.
            (self.config / 'index.yml').write_text(
                ('' if self.stub_embed else 'models:\n  embed: ' + json.dumps(str(model_copy)) + '\n') +
                'collections:\n' +
                ''.join(f'  {name}:\n    path: {json.dumps(str(self.root / name))}\n'
                        '    pattern: "**/*.md"\n' for name in ('wiki', 'raw')))
            wrapper = ('import os, subprocess, sys\nfrom pathlib import Path\n'
                       'with (Path(os.environ["FIXTURE_STATE"]) / "calls").open("a") as f:\n'
                       '    f.write(sys.argv[1] + "\\n")\n'
                       + ('if sys.argv[1] == "embed":\n    sys.exit(0)\n' if self.stub_embed else '') +
                       # Pin the default config name so an ancestor's project
                       # config cannot override the private fixture database.
                       f'r = subprocess.run([{str(args.real_qmd.resolve())!r}, "--index", "index"] + sys.argv[1:], '
                       'text=True, capture_output=True)\n'
                       'with (Path(os.environ["FIXTURE_STATE"]) / "diagnostics").open("a") as f:\n'
                       '    f.write(r.stdout + r.stderr)\n'
                       'sys.stdout.write(r.stdout)\nsys.stderr.write(r.stderr)\n'
                       'sys.exit(r.returncode)\n')
        else:
            wrapper = STUB
        executable(self.bin / 'qmd', '#!' + sys.executable + '\n' + wrapper)

    @property
    def stamp(self):
        if self.env.get('INDEX_PATH'):
            return Path(self.env['INDEX_PATH'] + '.vault-refresh-stamp')
        return Path(self.env.get('XDG_CACHE_HOME', str(self.home / '.cache'))) / 'qmd/vault-refresh-stamp'

    @property
    def lock(self):
        if self.env.get('INDEX_PATH'):
            return Path(self.env['INDEX_PATH'] + '.vault-refresh.lock')
        return self.stamp.with_name('vault-refresh.lock')

    def calls(self):
        path = self.state / 'calls'
        return path.read_text().splitlines() if path.exists() else []

    def clear_calls(self):
        (self.state / 'calls').write_text('')

    def gate(self, expected=0, script=gate):
        result = run(['/bin/sh', str(script)], env=self.env, cwd=self.root)
        diagnostic = self.state / 'diagnostics'
        detail = diagnostic.read_text() if result.returncode != expected and diagnostic.exists() else ''
        require(result.returncode == expected,
                f'exit {result.returncode}, expected {expected}: {result.stdout} {result.stderr}{detail}')
        require(len(result.stdout.splitlines()) == 1 and not result.stderr,
                f'expected one stdout line, got {result.stdout!r} {result.stderr!r}')
        if expected:
            require('semantic index is not current' in result.stdout, result.stdout)
        if expected == 2:
            require(result.stdout.startswith('PROBE FAILED: '), result.stdout)
        return result.stdout.strip()

    def search(self, word):
        result = checked([str(self.bin / 'qmd'), 'search', word, '--json'],
                         env=self.env, cwd=self.root)
        try:
            return json.loads(result.stdout)
        except ValueError:
            # Some qmd versions print an explicit empty-result sentence in JSON mode.
            if result.stdout.strip() == 'No results found.':
                return []
            raise

    def older_stamp(self):
        # Keep the stamp strictly behind subsequent edits without sleeping.
        old = time.time_ns() - SECOND
        os.utime(self.stamp, ns=(old, old))

    def vectors(self, phrase):
        # Result limit equals the wiki corpus size, so deletion assertions do
        # not mistake truncation for absence. Full bodies establish edit content.
        limit = len(list((self.root / 'wiki').rglob('*.md'))) + 1  # Include a stale deleted row.
        result = checked([str(self.bin / 'qmd'), 'query', 'vec: ' + phrase, '--no-rerank',
                          '--json', '--full', '--full-path', '-c', 'wiki', '-n', str(limit)],
                         env=self.env, cwd=self.root)
        return json.loads(result.stdout)

def refresh_count(f, expected):
    calls = [c for c in f.calls() if c in ('update', 'embed')]
    require(calls == expected, f'refresh calls {calls}, expected {expected}')

def temporal_legs(real=False, stub_embed=None):
    f = Fixture(real, stub_embed)
    label = ('real-index, stub embed' if f.stub_embed else 'real') if real else 'stub'

    def missing():
        require(not f.stamp.exists(), 'fixture stamp unexpectedly exists')
        message = f.gate()
        refresh_count(f, ['update', 'embed'])
        require(f.search('CONTROLANTLER'), 'control page absent after refresh')
        require(f.stamp.is_file() and not f.lock.exists(), 'stamp/lock state wrong')
        return message + '; control page found'
    leg(label + ' missing stamp forces full refresh', missing)

    def create():
        f.clear_calls()
        f.older_stamp()
        (f.root / 'wiki' / "new page's title.md").write_text('PLANTEDORCHID new page\n')
        require(not f.search('PLANTEDORCHID'), 'negative control already indexed')
        require(f.search('CONTROLANTLER'), 'positive control missing before catch-up')
        f.gate()
        refresh_count(f, ['update', 'embed'])
        hits = f.search('PLANTEDORCHID')
        require(hits, 'new page absent after catch-up')
        return f'before=0 with control; after={len(hits)}; one update then embed'
    leg(label + ' new page appears only after catch-up', create)

    def edit():
        f.clear_calls()
        f.older_stamp()
        (f.root / 'wiki' / "new page's title.md").write_text('EDITEDORCHID replacement\n')
        require(not f.search('EDITEDORCHID') and f.search('PLANTEDORCHID'),
                'stale edit controls failed')
        f.gate()
        refresh_count(f, ['update', 'embed'])
        require(f.search('EDITEDORCHID') and not f.search('PLANTEDORCHID'),
                'edit was not reflected')
        return 'new text found; old text absent with new-text control'
    leg(label + ' search edit search catches the edit', edit)

    def delete():
        f.clear_calls()
        f.older_stamp()
        # Make only the parent directory newer than the stamp after deletion.
        old = f.stamp.stat().st_mtime_ns - SECOND
        for p in [f.root / 'wiki', f.root / 'raw', *f.root.rglob('*.md')]:
            os.utime(p, ns=(old, old))
        (f.root / 'wiki' / "new page's title.md").unlink()
        require(f.search('EDITEDORCHID'), 'deletion control absent before catch-up')
        f.gate()
        refresh_count(f, ['update', 'embed'])
        require(not f.search('EDITEDORCHID') and f.search('CONTROLANTLER'),
                'deletion or positive control failed')
        return 'deleted hit=0; surviving control found; directory mtime caught deletion'
    leg(label + ' deleted page disappears', delete)

    def fresh():
        f.clear_calls()
        before = f.stamp.stat().st_mtime_ns
        message = f.gate()
        refresh_count(f, [])
        require(f.search('CONTROLANTLER'), 'fresh index control missing')
        require(f.stamp.stat().st_mtime_ns == before, 'fresh stamp changed')
        return message + '; refresh calls=0, search control found'
    leg(label + ' fresh search starts no refresh', fresh)
    return f

MAPPING = {
    'qmd-search-skill.diff': ('.claude/skills/qmd-search/SKILL.md',),
    'claude-search.diff': ('CLAUDE.md',),
    'ingest-qmd.diff': ('.claude/skills/ingest/SKILL.md',),
    'deep-lint-qmd.diff': ('.claude/skills/deep-lint/SKILL.md', 'CLAUDE.md'),
    'settings-stop-qmd.diff': ('.claude/settings.json',),
    'hook-load-status.diff': ('wiki/developments/hook-load-reduction-design.md',),
}

def flat_name(path):
    return path.removeprefix('.claude/')

def manifest(root):
    records = {}
    for p in [root, *sorted(root.rglob('*'))]:
        meta = p.lstat()
        records[str(p.relative_to(root))] = (
            stat.S_IMODE(meta.st_mode), meta.st_mtime_ns,
            hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory')
    return records

def immutable_vault(f):
    for p in f.root.rglob('*'):
        p.chmod(0o555 if p.is_dir() else 0o444)
    f.root.chmod(0o555)
    before = manifest(f.root)
    f.stamp.unlink()
    f.clear_calls()
    f.gate()
    refresh_count(f, ['update', 'embed'])
    require(f.search('CONTROLANTLER'), 'read-only positive control missing')
    require(before == manifest(f.root), 'read-only source manifest changed')
    return len(before)

def vector_state(f):
    # Read vector bookkeeping for active documents, never the live database.
    with sqlite3.connect(Path(f.env['INDEX_PATH']).as_uri() + '?mode=ro', uri=True) as db:
        require(db.execute("SELECT name FROM sqlite_master WHERE name='vectors_vec'").fetchone(),
                'embedding succeeded without a vector table')
        rows = db.execute('SELECT d.path, d.hash, COUNT(cv.seq), MAX(cv.total_chunks) '
                          'FROM documents d JOIN content_vectors cv ON cv.hash = d.hash '
                          "WHERE d.active = 1 AND d.collection = 'wiki' GROUP BY d.path, d.hash").fetchall()
    require(rows and all(count >= expected > 0 for _, _, count, expected in rows),
            'active wiki embeddings are missing or incomplete')
    return {name: (digest, count) for name, digest, count, _ in rows}

def semantic_lifecycle(f):
    control = f.root / 'wiki/base.md'
    control_phrase = 'Astronomers compare distant stars using the observatory telescope'
    control.write_text(control_phrase + '\n')
    f.gate()
    planted = f.root / "wiki/marine's notes.md"
    first = 'Underwater gardens shelter colourful fish beside the coral reef'
    edited = 'Polar researchers measure ancient ice layers beneath the frozen glacier'

    def hit(rows, page, phrase=None):
        for row in rows:
            identifier = row['file']
            if identifier.startswith('qmd://'):
                # A deleted page has no full path; qmd returns its virtual path.
                uri = urlsplit(identifier)
                same = uri.netloc == 'wiki' and unquote(uri.path.lstrip('/')) == str(page.relative_to(f.root / 'wiki'))
            else:
                same = (f.root / identifier).resolve() == page
            if same and (phrase is None or phrase in row.get('body', '')):
                return True
        return False

    def surviving_control():
        require(hit(f.vectors(control_phrase), control, control_phrase), 'semantic control missing')

    surviving_control()
    f.clear_calls(); f.older_stamp(); planted.write_text(first + '\n')
    require(not hit(f.vectors(first), planted), 'planted page already indexed before catch-up')
    surviving_control()
    f.gate(); refresh_count(f, ['update', 'embed'])
    require(hit(f.vectors(first), planted, first), 'semantic creation catch-up missed exact page/body')
    creation = vector_state(f) if f.real else None
    if creation is not None:
        require(planted.name in creation and control.name in creation, 'created/control vectors missing')

    f.clear_calls(); f.older_stamp(); planted.write_text(edited + '\n')
    require(hit(f.vectors(first), planted, first), 'stale semantic edit control missing')
    require(not hit(f.vectors(edited), planted, edited), 'edit appeared before catch-up')
    f.gate(); refresh_count(f, ['update', 'embed'])
    require(hit(f.vectors(edited), planted, edited) and not hit(f.vectors(first), planted, first),
            'semantic edit did not replace the indexed body')
    after_edit = vector_state(f) if f.real else None
    if after_edit is not None:
        require(planted.name in after_edit and after_edit[planted.name][0] != creation[planted.name][0],
                'edit did not replace active vector hash')
    surviving_control()

    f.clear_calls(); f.older_stamp(); planted.unlink()
    require(hit(f.vectors(edited), planted, edited), 'stale semantic deletion control missing')
    f.gate(); refresh_count(f, ['update', 'embed'])
    require(not hit(f.vectors(edited), planted), 'deleted page remains a semantic result')
    surviving_control()
    after_delete = vector_state(f) if f.real else None
    if after_delete is not None:
        require(planted.name not in after_delete and control.name in after_delete,
                'deleted vectors remain active or control vectors lost')

    f.clear_calls(); before = f.stamp.stat().st_mtime_ns
    f.gate(); refresh_count(f, []); surviving_control()
    require(f.stamp.stat().st_mtime_ns == before, 'unchanged semantic repeat restamped')
    states = ('; active vector chunks create/edit/delete=' +
              '/'.join(str(sum(v[1] for v in state.values()))
                       for state in (creation, after_edit, after_delete))) if f.real else '; stub contract only'
    return ('vector-only query: creation before=0/after=1, edited body replaced, deletion hits=0, '
            'surviving control found throughout, unchanged refreshes=0' + states)

def raw_only_case(script=gate):
    f = Fixture(); f.gate()
    # Establish a demonstrably fresh baseline, with every source entry older
    # than the stamp. A raw overwrite then changes neither wiki nor raw directory.
    old = f.stamp.stat().st_mtime_ns - SECOND
    for tree in ('wiki', 'raw'):
        for p in [f.root / tree, *(f.root / tree).rglob('*')]:
            os.utime(p, ns=(old, old))
    wiki_before = manifest(f.root / 'wiki')
    f.clear_calls(); f.gate(script=script); refresh_count(f, [])
    require(f.search('RAWCONTROL'), 'fresh raw baseline positive control missing')
    raw = f.root / 'raw/control.md'
    raw.write_text('RAWEDIT source changed\n')
    # The stamp is already in the past; use a clock-independent strict ordering.
    newer = f.stamp.stat().st_mtime_ns + 1  # One nanosecond is the smallest ns timestamp step.
    os.utime(raw, ns=(newer, newer))
    hits = checked(['find', str(f.root / 'wiki'), str(f.root / 'raw'),
                    '-newer', str(f.stamp), '-print']).stdout.splitlines()
    require(hits == [str(raw)], f'raw trigger is not isolated: {hits}')
    require(manifest(f.root / 'wiki') == wiki_before, 'wiki changed in raw-only leg')
    f.clear_calls(); f.gate(script=script); refresh_count(f, ['update', 'embed'])
    require(f.search('RAWEDIT') and not f.search('RAWCONTROL'), 'raw-only edit not indexed')
    require(manifest(f.root / 'wiki') == wiki_before, 'raw refresh changed wiki')
    return 'fresh baseline refreshes=0 with raw control; newer entries=1 (raw file only); edit found'

def live_fixture():
    f = Fixture()
    phrase = 'Seagrass meadows provide shelter for young fish near the coast'
    page = f.root / "wiki/notes/newest page's title.md"
    page.parent.mkdir()
    page.write_text('---\ntitle: Metadata must never become the query\n---\n'
                    '# A heading that is not the body\n\n```text\n'
                    'A fenced example is not the body\n```\n\n' + phrase + '.\n')
    other = f.root / 'wiki/other' / page.name
    other.parent.mkdir(); other.write_text('An unrelated page has the same basename\n')
    (f.root / 'wiki/log.md').write_text('The excluded log is newer than the page\n')
    now = time.time_ns()
    for p in (f.root / 'wiki').rglob('*.md'):
        os.utime(p, ns=(now - SECOND, now - SECOND))
    os.utime(page, ns=(now, now))
    # The log is deliberately newest, but is outside the indexed-page contract.
    os.utime(f.root / 'wiki/log.md', ns=(now + SECOND, now + SECOND))
    f.gate(); f.clear_calls()
    return f, page, phrase

def check_live(f, expected, arguments=None, cwd=None, env=None, script=live_check):
    result = run(['/bin/sh', str(script), *(arguments or [])],
                 env=env or f.env, cwd=cwd or f.root)
    require(result.returncode == expected and not result.stderr,
            f'live checker exit={result.returncode}, expected={expected}: {result.stdout} {result.stderr}')
    if expected == 2:
        require('PROBE FAILED: ' in result.stdout and 'PASS live' not in result.stdout, result.stdout)
    else:
        require(result.stdout.splitlines()[-1].startswith('PASS ' if expected == 0 else 'FAIL '), result.stdout)
    return result.stdout

def live_success():
    f, page, phrase = live_fixture()
    output = check_live(f, 0)
    command = json.loads((f.state / 'query-args.json').read_text())
    require(command[0:2] == ['query', 'vec: ' + phrase] and
            all(flag in command for flag in ('--no-rerank', '--json', '--full-path')),
            'checker did not issue the expected vector-only body query')
    require(json.dumps(str(page.relative_to(f.root))) in output, 'wrong newest page selected')
    require(f.calls() == ['query'], 'live check refreshed or used lexical search')
    f.clear_calls(); check_live(f, 0, [str(f.root)], cwd=f.base)
    require(f.calls() == ['query'], 'explicit-root control used extra qmd commands')
    fallback = dict(f.env); del fallback['CLAUDE_PROJECT_DIR']
    check_live(f, 0, env=fallback)
    f.env['QUERY_OUTPUT'] = json.dumps([{'file': './' + str(page.relative_to(f.root))}])
    check_live(f, 0)
    return 'newest body phrase; log excluded; apostrophe path; argument/env/cwd roots; only vector query'

def live_failures():
    f, page, _ = live_fixture()
    index = f.state / 'index.json'
    original = index.read_bytes()
    docs = json.loads(original); del docs[str(page.relative_to(f.root))]
    index.write_text(json.dumps(docs))
    require('matches=0' in check_live(f, 1), 'unrelated basename mistaken for newest page')
    index.write_text('{}'); check_live(f, 2)
    index.write_bytes(original); check_live(f, 0)
    for payload in ('not-json', '{}', '[{"file": null}]'):
        f.env['QUERY_OUTPUT'] = payload; check_live(f, 2)
    # Neither a same-basename result from another vault nor an unresolved URI
    # establishes physical identity, even if its title/snippet is convincing.
    for wrong in (str(f.base / 'other-vault' / page.relative_to(f.root)),
                  'qmd://wiki/' + str(page.relative_to(f.root / 'wiki'))):
        f.env['QUERY_OUTPUT'] = json.dumps([{'file': wrong}]); check_live(f, 1)
    del f.env['QUERY_OUTPUT']
    f.env['FAIL_QMD'] = 'query'; check_live(f, 2); del f.env['FAIL_QMD']
    check_live(f, 0)
    f.env['CHANGE_DURING_QUERY'] = str(page)
    require('changed during acceptance' in check_live(f, 2), 'concurrent page change passed')
    # Exercise the production timeout branch with a shorter fixture-only bound.
    timeout_copy = scratch / 'quick-live-check.sh'
    source = live_check.read_text()
    anchor = 'MIN_WORDS, MAX_WORDS, LIMIT, TIMEOUT = 4, 24, 20, 240\n'
    require(source.count(anchor) == 1, 'timeout test anchor missing or ambiguous')
    executable(timeout_copy, source.replace(anchor, anchor.replace('240', '0.1')))
    # Delay and test timeout: set by judgement, unmeasured; neither is production configuration.
    slow, _, _ = live_fixture()
    executable(slow.bin / 'qmd', '#!' + sys.executable + '\nimport time\ntime.sleep(2)\n')
    require('query process group stopped' in check_live(slow, 2, script=timeout_copy), 'timeout passed')
    return 'missing target fails with unrelated control; empty/malformed/failed/racing/timed-out queries exit 2'

def live_premises():
    f, page, _ = live_fixture()
    check_live(f, 2, ['too', 'many']); require(not f.calls(), 'invalid arguments invoked qmd')
    (f.root / '.qmd-off').touch(); check_live(f, 2)
    require(not f.calls(), 'off marker invoked qmd'); (f.root / '.qmd-off').unlink()
    empty_path = f.base / 'python-only'; empty_path.mkdir()
    (empty_path / 'python3').symlink_to(sys.executable)
    env = dict(f.env, PATH=str(empty_path)); check_live(f, 2, env=env)
    require(not f.calls(), 'absent qmd control invoked qmd')
    check_live(f, 2, env=dict(f.env, PATH=str(f.base / 'no-python')))
    for body in ('---\ntitle: No closing frontmatter\n', '# Heading only\n'):
        page.write_text(body); check_live(f, 2)
    require(not f.calls(), 'unusable phrase invoked qmd')
    empty_root = f.base / 'empty-vault'; empty_root.mkdir()
    check_live(f, 2, [str(empty_root)])
    (empty_root / 'wiki').mkdir(); check_live(f, 2, [str(empty_root)])
    control, _, _ = live_fixture(); check_live(control, 0)
    return 'arguments, off, absent qmd/Python, unusable phrase, missing/empty wiki rejected; healthy control passes'

exit_code = 0
try:
    if not gate.is_file() or not live_check.is_file():
        raise Premise('gate or live checker missing')
    if args.stage and args.vault is None:
        raise Premise('--stage requires a --vault baseline')
    if args.stage and (not (args.stage / 'diffs').is_dir() or not args.vault.is_dir()):
        raise Premise('--stage diffs directory or --vault baseline missing')
    if args.stub_embed:
        if not args.real_qmd or args.model:
            raise Premise('--stub-embed requires --real-qmd and no --model')
    elif bool(args.real_qmd) != bool(args.model):
        raise Premise('--real-qmd and --model must be supplied together')
    if not shutil.which('rg'):
        raise Premise('rg is required for controlled verification')
    if args.stage and not shutil.which('patch'):
        raise Premise('patch is required for stage verification')
    scratch = Path(checked(['mktemp', '-d', str(args.tmp_parent.resolve() / '.qmd-fresh-tests.XXXXXX')]).stdout.strip())
    baselines = {}
    if args.stage:
        baselines = {path: (args.vault / path).read_bytes() for paths in MAPPING.values() for path in paths}
        flat = scratch / 'flat'
        flat.mkdir()
        patched = {}

        def patches():
            for relative, data in baselines.items():
                target = flat / flat_name(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            for name in MAPPING:
                patch = (args.stage / 'diffs' / name).read_text()
                # Only headers change; all copies have no .claude path component.
                patch = re.sub(r'(?m)^(--- a/|\+\+\+ b/)\.claude/', r'\1', patch)
                checked(['patch', '-p1', '--dry-run', '--batch', '--fuzz=0'], cwd=flat, input=patch)
                checked(['patch', '-p1', '--batch', '--fuzz=0'], cwd=flat, input=patch)
            patched.update({p: (flat / flat_name(p)).read_text() for p in baselines})
            require(all('.claude' not in p.parts for p in flat.rglob('*')), 'non-flat fixture')
            return f'{len(MAPPING)} dry-runs passed with patch -p1 --dry-run --batch --fuzz=0'
        leg('proposed diffs dry-run on flat copies', patches)
        if len(patched) != len(baselines):
            raise Premise('diff baselines did not all patch')

        def stop():
            old = json.loads(baselines['.claude/settings.json'])
            new = json.loads(patched['.claude/settings.json'])
            expected = copy.deepcopy(old)
            entries = expected['hooks']['Stop']
            removed = [e for e in entries if any('qmd update' in h.get('command', '') for h in e['hooks'])]
            require(len(removed) == 1 and len(removed[0]['hooks']) == 1, 'Stop positive control changed')
            entries.remove(removed[0])
            require(new == expected, 'settings change exceeds the single qmd Stop entry')
            before = [h['command'] for e in old['hooks']['Stop'] for h in e['hooks']
                      if re.search(r'\bqmd\b', h.get('command', ''))]
            after = [h['command'] for e in new['hooks']['Stop'] for h in e['hooks']
                     if re.search(r'\bqmd\b', h.get('command', ''))]
            require(len(before) == 1 and not after, 'qmd Stop hook remains')
            # Run only the qmd branch in an isolated dispatcher. Other Stop commands
            # are structurally identical and are never executed against the vault.
            control = Fixture()
            for command in before:
                checked(['/bin/sh', '-c', command], env=control.env, cwd=control.root)
            refresh_count(control, ['update', 'embed'])
            changed = Fixture()
            for command in after:
                checked(['/bin/sh', '-c', command], env=changed.env, cwd=changed.root)
            require(not changed.calls(), 'turn end launched qmd')
            return f'qmd processes=0; retired-hook control=2; other {len(entries)} Stop entries unchanged'
        leg('turn end starts no qmd process', stop)

        def wording():
            old = baselines['.claude/skills/qmd-search/SKILL.md'].decode()
            require(old.count('## Refresh on write') == 1, 'CONTROL+ Refresh on write missing')
            skill = patched['.claude/skills/qmd-search/SKILL.md']
            require('## Refresh on write' not in skill and '## Refresh before search' in skill,
                    'refresh section was not replaced')
            retired = re.compile(r'once per write operation|refreshing embeddings on every page change|'
                                 r'refresh belongs in a|inline only where not|qmd refresh if enabled|'
                                 r'\), qmd refresh;')
            require(not any(retired.search(text) for text in patched.values()), 'retired duty remains')
            old_route = [line for line in baselines['CLAUDE.md'].decode().splitlines()
                         if line.startswith('| `/deep-lint`')]
            new_route = [line for line in patched['CLAUDE.md'].splitlines()
                         if line.startswith('| `/deep-lint`')]
            require(len(old_route) == len(new_route) == 1 and 'qmd refresh;' in old_route[0] and
                    new_route[0] == old_route[0].replace('qmd refresh;', 'qmd status reporting;'),
                    'deep-lint routing summary not corrected exactly')
            for p in ('.claude/skills/ingest/SKILL.md', '.claude/skills/deep-lint/SKILL.md', 'CLAUDE.md'):
                require('qmd-fresh.sh' in patched[p], f'gate missing in {p}')
            require('a created/updated page refreshes its `confidence` (stamping `audited:`, §4.6)' in
                    patched['CLAUDE.md'], 'confidence duty changed')
            return 'retired duty matches=0; CONTROL+ old heading=1, old routing duty=1; status route and confidence present'
        leg('contract wording sweep with positive control', wording)
    else:
        skip('build diff and baseline checks', '--stage not supplied; fixture behaviour legs still run')

    temporal_legs()

    leg('raw-only changes trigger refresh with unchanged wiki', raw_only_case)

    def raw_mutation():
        text = gate.read_text()
        anchors = [line for line in text.splitlines(keepends=True) if line.startswith('    qf_newer=$(find ')]
        require(len(anchors) == 1 and ' "$qf_root/raw"' in anchors[0],
                'raw-scan mutation anchor missing or ambiguous')
        anchor = anchors[0]
        mutant = scratch / 'wiki-only-gate.sh'
        executable(mutant, text.replace(anchor, anchor.replace(' "$qf_root/raw"', '')))
        try:
            raw_only_case(mutant)
        except AssertionError as error:
            require('refresh calls []' in str(error), 'mutant failed for an unrelated reason: ' + str(error))
            return 'gate omitting raw rejected: no refresh after isolated raw edit; original gate control passed'
        raise AssertionError('gate omitting raw passed the raw-only leg')
    leg('raw-only negative control rejects wiki-only freshness scan', raw_mutation)
    leg('stub semantic assertion lifecycle controls', lambda: semantic_lifecycle(Fixture()))
    leg('live checker selects newest page and queries only vectors', live_success)
    leg('live checker rejects wrong results and failed queries', live_failures)
    leg('live checker broken premises exit 2', live_premises)

    def disabled():
        f = Fixture(); (f.root / '.qmd-off').touch()
        message = f.gate(1)
        require('.qmd-off present' in message and not f.calls() and not f.stamp.exists(), message)
        (f.root / '.qmd-off').unlink(); f.gate(); refresh_count(f, ['update', 'embed'])
        return message + '; marker-removal control refreshed'
    leg('disabled qmd takes plain route without qmd calls', disabled)

    def absent():
        f = Fixture(); f.env['PATH'] = str(f.base / 'empty-path')
        message = f.gate(1)
        require('qmd absent' in message and not f.calls(), message)
        return message + '; installed-qmd control covered by refresh legs'
    leg('absent qmd takes plain route', absent)

    def held_lock():
        f = Fixture(); f.gate(); f.clear_calls(); f.lock.mkdir()
        marker = f.lock / 'holder'; marker.write_text('another session')
        message = f.gate(1)
        require('refresh lock held' in message and marker.read_text() == 'another session', message)
        refresh_count(f, [])
        marker.unlink(); f.lock.rmdir(); f.older_stamp(); f.gate()
        refresh_count(f, ['update', 'embed'])
        return message + '; lock preserved; release control refreshed'
    leg('held lock falls back even with a fresh stamp', held_lock)

    for failed_command in ('update', 'embed'):
        def failure(command=failed_command):
            f = Fixture(); f.gate(); f.clear_calls(); f.older_stamp()
            before = f.stamp.stat().st_mtime_ns
            f.env['FAIL_QMD'] = command
            message = f.gate(1)
            refresh_count(f, ['update'] if command == 'update' else ['update', 'embed'])
            require('refresh failed' in message, message)
            require(f.stamp.stat().st_mtime_ns == before and not f.lock.exists()
                    and not Path(str(f.stamp) + '.new').exists(), 'failed refresh promoted or leaked state')
            del f.env['FAIL_QMD']; f.clear_calls(); f.gate()
            refresh_count(f, ['update', 'embed'])
            return message + '; old stamp retained; retry control succeeded'
        leg(f'{failed_command} failure takes plain route', failure)

    def mid_refresh():
        f = Fixture(); f.env['EDIT_DURING_EMBED'] = '1'; f.gate()
        require(not f.search('DURINGEMBED') and f.search('CONTROLANTLER'), 'mid-refresh control failed')
        del f.env['EDIT_DURING_EMBED']; f.clear_calls(); f.gate()
        refresh_count(f, ['update', 'embed'])
        require(f.search('DURINGEMBED'), 'start stamp missed a mid-refresh edit')
        return 'next search catches the edit made after update'
    leg('stamp precedes work and promotes only after success', mid_refresh)

    def premises():
        f = Fixture(); shutil.rmtree(f.root / 'raw')
        require('raw directory missing' in f.gate(2) and not f.calls(), 'missing tree passed')
        f = Fixture(); executable(f.bin / 'find', '#!/bin/sh\nprintf "planted scan failure\\n" >&2\nexit 1\n')
        f.stamp.touch()
        require('freshness scan failed' in f.gate(2) and not f.calls(), 'scan error passed')
        f = Fixture(); f.lock.write_text('not a directory')
        require('lock could not be created' in f.gate(2), 'lock premise passed')
        f = Fixture(); f.env['INDEX_PATH'] = 'relative.sqlite'
        require('must be absolute' in f.gate(2), 'relative index accepted')
        return 'missing tree, failed scan, non-directory lock, relative database all exit 2'
    leg('broken premises never report clean', premises)

    def cache_paths():
        for xdg in (True, False):
            f = Fixture(); del f.env['INDEX_PATH']
            if not xdg:
                del f.env['XDG_CACHE_HOME']
            f.gate(); refresh_count(f, ['update', 'embed'])
            require(f.stamp.is_file(), 'cache stamp in wrong directory')
            f.clear_calls(); f.gate(); refresh_count(f, [])
        return 'XDG and HOME defaults: catch-up control followed by zero refresh'
    leg('cache paths match qmd defaults and isolate explicit database', cache_paths)

    def mutation():
        mutant = scratch / 'exit-zero.sh'; executable(mutant, '#!/bin/sh\nexit 0\n')
        f = Fixture(); f.gate(); f.older_stamp()
        (f.root / 'wiki/planted.md').write_text('MUTATIONCATCH planted after stamp\n')
        require(not f.search('MUTATIONCATCH') and f.search('CONTROLANTLER'), 'mutation controls failed')
        result = checked(['/bin/sh', str(mutant)], env=f.env, cwd=f.root)
        require(result.returncode == 0 and not f.search('MUTATIONCATCH'), 'mutant did not expose stale result')
        f.gate(); require(f.search('MUTATIONCATCH'), 'real gate did not repair the negative control')
        return 'exit-0 replacement misses planted page; real gate finds it'
    leg('negative control rejects exit-0 gate', mutation)

    real_fixture = None
    semantic_fixture = None
    semantic_name = 'real semantic creation edit deletion and unchanged repeat'
    if args.real_qmd:
        if not args.real_qmd.is_file():
            raise Premise('real qmd missing')
        if not args.stub_embed:
            if not args.model.is_file():
                raise Premise('local embedding model missing')
            with args.model.open('rb') as source:
                if source.read(4) != b'GGUF':
                    raise Premise('local model is not GGUF')
            model_copy = scratch / args.model.name
            shutil.copyfile(args.model, model_copy)
        unavailable = '--stub-embed requested: embeddings replaced; vector acceptance cannot run'
        real_vectors = False
        if not args.stub_embed:
            probe = Fixture(real=True)
            checked([str(probe.bin / 'qmd'), 'update'], env=probe.env, cwd=probe.root)
            try:
                embedding = run([str(probe.bin / 'qmd'), 'embed'], env=probe.env, cwd=probe.root)
                if embedding.returncode == 0:
                    # A zero exit without active vectors is a failure, not an unavailable runtime.
                    leg('real embedding preflight has complete active vectors', lambda: vector_state(probe))
                    real_vectors = results[-1]
                    unavailable = 'embedding reported success without complete vectors (failed assertion above)'
                else:
                    diagnostic = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', embedding.stdout + embedding.stderr)
                    reasons = [line.strip() for line in diagnostic.splitlines()
                               if re.search(r'error|failed|not available|cannot', line, re.I)]
                    unavailable = (f'local embedding preflight exited {embedding.returncode}: ' +
                                   ('; '.join(dict.fromkeys(reasons)) or ' '.join(diagnostic.split())))
            except subprocess.TimeoutExpired:
                unavailable = f'local embedding preflight exceeded the {TIMEOUT}s process bound'
        method = ('real qmd update/search, explicitly stubbed embed; semantic leg skipped' if not real_vectors else
                  'real qmd update/embed/vector query; copied local GGUF; CPU requested, prebuilt binaries only')
        print('ISOLATION: ' + method + '; private HOME, XDG_CACHE_HOME, XDG_CONFIG_HOME, '
              'QMD_CONFIG_DIR and INDEX_PATH', flush=True)
        if real_vectors:
            real_fixture = temporal_legs(real=True, stub_embed=False)
            semantic_fixture = Fixture(real=True, stub_embed=False)
            leg(semantic_name, lambda: semantic_lifecycle(semantic_fixture))
        else:
            skip(semantic_name, unavailable)
            real_fixture = temporal_legs(real=True, stub_embed=True)
    else:
        print('ISOLATION: stub qmd on PATH; private HOME/config/cache/database; '
              'real qmd legs not requested', flush=True)
        skip(semantic_name, '--real-qmd and --model not supplied; no real embedding attempted')

    def no_writes():
        f = Fixture(); f.gate()
        count = immutable_vault(f)
        real_count = immutable_vault(real_fixture) if real_fixture else 0
        # A controlled source grep: all file-mutating shell commands must target
        # only the named cache variables. This complements the runtime manifest.
        expression = r'\b(mkdir|rmdir|touch|mv|rm|cp|tee|install|truncate|dd)\b'
        scan = run(['rg', '-n', expression, str(gate)])
        require(scan.returncode == 0, 'write-pattern positive control did not hit')
        allowed = ('rm -f "$qf_stamp.new"', 'rmdir "$qf_lock"', 'mkdir -p "$qf_cache"',
                   'mkdir "$qf_lock"', 'touch "$qf_stamp.new"', 'mv -f "$qf_stamp.new" "$qf_stamp"')
        code_hits = [line for line in scan.stdout.splitlines()
                     if not line.split(':', 1)[1].lstrip().startswith('#')]
        unexpected = [line for line in code_hits if not any(item in line for item in allowed)]
        require(not unexpected, 'unapproved write-pattern targets: ' + repr(unexpected))
        planted = scratch / 'write-control.sh'
        planted.write_text('touch "$qf_root/wiki/planted.md"\n')
        control = run(['rg', '-n', expression, str(planted)])
        require(control.returncode == 0 and len(control.stdout.splitlines()) == 1,
                'planted source-write grep missed its control')
        checker_fixture, _, _ = live_fixture()
        for p in [checker_fixture.root, *checker_fixture.root.rglob('*')]:
            p.chmod(0o555 if p.is_dir() else 0o444)
        checker_before = manifest(checker_fixture.root)
        check_live(checker_fixture, 0)
        require(manifest(checker_fixture.root) == checker_before, 'live checker changed source manifest')
        python_writes = (expression + r'|\.(write_text|write_bytes|unlink|mkdir|rmdir|rename|replace|'
                         r'chmod|utime|touch)\s*\(|\bopen\([^\n]*[\x22\x27][wax]')
        checker_scan = run(['rg', '-n', python_writes, str(live_check)])
        require(checker_scan.returncode == 1, 'live checker write-pattern hit or scan failure: ' +
                checker_scan.stdout + checker_scan.stderr)
        planted.write_text('Path("wiki/planted.md").write_text("planted")\n')
        checker_control = run(['rg', '-n', python_writes, str(planted)])
        require(checker_control.returncode == 0 and len(checker_control.stdout.splitlines()) == 1,
                'live-checker write-pattern positive control failed')
        vector_manifest_count = 0
        if semantic_fixture:
            for p in [semantic_fixture.root, *semantic_fixture.root.rglob('*')]:
                p.chmod(0o555 if p.is_dir() else 0o444)
            before = manifest(semantic_fixture.root)
            require(semantic_fixture.vectors('Astronomers compare distant stars'), 'read-only vector control absent')
            check_live(semantic_fixture, 0)
            require(before == manifest(semantic_fixture.root), 'real vector/checker source manifest changed')
            vector_manifest_count = len(before)
        baseline_detail = ''
        if args.stage:
            require(all((args.vault / p).read_bytes() == data for p, data in baselines.items()),
                    'live baseline changed during suite; result needs a new baseline')
            baseline_detail = f'; live baseline byte changes=0 across {len(baselines)} files'
        return (f'read-only manifest entries={count}, real={real_count}; changes=0; '
                f'cache-only write hits={len(code_hits)}, unapproved=0, planted source-write hit=1; '
                f'live checker manifest entries={len(checker_before)}, real vectors={vector_manifest_count}; '
                'checker source writes=0 with planted Python write hit=1' + baseline_detail)
    leg('no source writes: read-only manifests and controlled source grep', no_writes)
    exit_code = 0 if all(results) else 1
except (Premise, OSError, subprocess.TimeoutExpired) as exc:
    print(f'PROBE FAILED: {exc}', flush=True)
    results.append(False)
    exit_code = 2
finally:
    if scratch is not None:
        try:
            for p in scratch.rglob('*'):
                if p.is_dir():
                    p.chmod(0o755)
            shutil.rmtree(scratch)
        except OSError as exc:
            print(f'PROBE FAILED: fixture cleanup failed: {exc}', flush=True)
            results.append(False)
            exit_code = 2
    failures = results.count(False)
    print(f'SKIPS: {len(skips)} (excluded from the pass count)')
    print(f'FAIL {failures}/{len(results)}' if failures else f'PASS {len(results)}/{len(results)}')
sys.exit(exit_code)
PY_QMD_FRESH_SUITE
