#!/usr/bin/env python3
"""Fixture roots behind a symbolic link: the snapshot grant guard and the O5 fixture.

The test builds its own symbolic link inside a fresh temporary folder, so its result
does not depend on whether the machine's temporary folder passes through one. It
writes only that disposable folder, which it removes, and reports on stdout.

Run: python3 -B test_link_roots.py --build BUILD_DIR
Exit 0 on PASS, 1 on FAIL, 2 on PROBE FAILED (a broken premise, never a clean result).
"""
import argparse
import copy
import hashlib
import importlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys


class Premise(Exception):
    pass


def premise(ok, what):
    if not ok:
        raise Premise(what)


def describe(exc):
    return type(exc).__name__ + ': ' + str(exc)


def attempt(call):
    """Return (value, None) or (None, error). A broken premise propagates; any other
    error, including one the module under test should not raise, is the case's result."""
    try:
        return call(), None
    except Premise:
        raise
    except Exception as exc:
        return None, exc


def tree_manifest(root):
    """Every entry under root, without following links: mode, link text or content hash."""
    result = {}
    for parent, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories + files):
            path = Path(parent) / name
            info = path.lstat()
            item = {'mode': stat.S_IMODE(info.st_mode)}
            if stat.S_ISLNK(info.st_mode):
                item['link'] = os.readlink(path)
            elif stat.S_ISREG(info.st_mode):
                item['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            else:
                item['directory'] = True
            result[str(path.relative_to(root))] = item
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', required=True, type=Path)
    args = parser.parse_args()
    if not os.environ.get('TMPDIR') or not Path(os.environ['TMPDIR']).is_dir():
        print('PROBE FAILED: explicit existing TMPDIR required')
        return 2
    try:
        build = args.build.resolve(strict=True)
    except OSError as exc:
        print('PROBE FAILED: ' + str(exc))
        return 2
    adopt = build / 'adopt'
    if not all((adopt / name).is_file() for name in ('adopt_snapshot.py', 'test_o5.py')):
        print('PROBE FAILED: build lacks adopt_snapshot.py or test_o5.py')
        return 2
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(adopt))
    modules = {key: importlib.import_module(name) for key, name in {
        'D': 'adopt_data', 'W': 'adopt_register', 'S': 'adopt_snapshot', 'R': 'adopt_resources',
        'F': 'adopt_freshness', 'G': 'adopt_migrate', 'V': 'adopt_manifest', 'render': 'adopt_render'}.items()}
    o5 = importlib.import_module('test_o5')
    loaded = [Path(m.__file__).resolve().parent for m in list(modules.values()) + [o5]]
    if any(parent != adopt for parent in loaded):
        print('PROBE FAILED: modules not loaded from the build under test')
        return 2
    D, R, S = modules['D'], modules['R'], modules['S']
    results = []

    def record(name, ok, detail=''):
        results.append(bool(ok))
        print(('PASS ' if ok else 'FAIL ') + name + (': ' + detail if detail else ''), flush=True)

    def expect_true(name, call, otherwise):
        value, error = attempt(call)
        record(name, error is None and value is True,
               describe(error) if error else ('' if value is True else otherwise))

    def expect_refusal(name, call, message):
        _, error = attempt(call)
        ok = isinstance(error, D.Problem) and message in str(error)
        record('control: ' + name + ' is refused', ok, '' if ok else describe(error) if error else 'accepted')

    def expect_acceptance(name, call):
        _, error = attempt(call)
        record('positive control: ' + name + ' is accepted', error is None, describe(error) if error else '')

    build_before = tree_manifest(build)
    scratch = Path(subprocess.check_output(['/usr/bin/mktemp', '-d', os.path.join(os.environ['TMPDIR'], 'adopt.XXXXXXXX')], text=True).strip())
    try:
        real = scratch.resolve(strict=True)
        print('ENVIRONMENT temporary folder behind a symbolic link: ' +
              ('yes' if str(scratch).rstrip('/') != str(real) else 'no'), flush=True)
        target = real / 'link-target'
        target.mkdir()
        alias = real / 'via-link'
        alias.symlink_to(target, target_is_directory=True)
        plain = real / 'plain'
        plain.mkdir()
        outside = real / 'outside'
        outside.mkdir()
        (outside / 'SKILL.md').write_text('---\nname: outside\n---\nNot granted.\n')
        premise(alias.is_symlink() and alias.resolve(strict=True) == target,
                'constructed link does not resolve to its target')
        premise(plain.resolve(strict=True) == plain and target.resolve(strict=True) == target,
                'constructed plain folders are not canonical')

        # Discriminating cases: the O5 fixture hashes its skill tree through the guard.
        for label, base in (('not under a link', plain), ('under a link', alias)):
            root = base / 'fixture'
            root.mkdir()
            canonical = root.resolve(strict=True)
            premise((root != canonical) == (base is alias), 'fixture root placement premise')

            def build_fixture(root=root, tree=canonical / 'home' / 'tree'):
                f = o5.Fixture(root, modules)
                o5.configure(f, 'comparison')
                return (f.resource['locator']['path'] == str(tree) and
                        f.resource['expected']['sha256'] == S.tree_hash(tree) and
                        f.evaluate()['tier'] == 'proven')
            expect_true('O5 fixture root ' + label + ' builds, hashes its canonical tree and evaluates proven',
                        build_fixture, 'fixture built but its tree locator, hash or tier differs')

        # Production-convention fixture: built canonically, then addressed through the link.
        observed_root = target / 'observed'
        observed_root.mkdir()
        f = o5.Fixture(observed_root, modules)
        prod_home = alias / 'home-through-link'
        (prod_home / '.claude/skills/demo').mkdir(parents=True)
        (prod_home / '.claude/skills/demo/SKILL.md').write_text('---\nname: demo\n---\nDemo.\n')
        # Controls: a tree whose internal link leaves every grant, and links to ungranted folders.
        escape_root = plain / 'escape-root'
        escape_root.symlink_to(outside, target_is_directory=True)
        escape_tree = plain / 'tree-with-escape'
        escape_tree.mkdir()
        (escape_tree / 'SKILL.md').write_text('---\nname: escape\n---\nEscapes.\n')
        (escape_tree / 'escape').symlink_to(outside, target_is_directory=True)
        aliased_escape = target / 'aliased-escape'
        aliased_escape.mkdir()
        (aliased_escape / 'SKILL.md').write_text('---\nname: aliased\n---\nEscapes.\n')
        (aliased_escape / 'escape').symlink_to(outside, target_is_directory=True)
        aliased_tree = target / 'aliased-tree'
        aliased_tree.mkdir()
        (aliased_tree / 'SKILL.md').write_text('---\nname: aliased-tree\n---\nInside.\n')
        for path in (outside, escape_tree, aliased_escape, aliased_tree):
            o5.permissions(path, True)
        doc = copy.deepcopy(f.doc)
        for item in doc['resources']:
            relative = Path(item['locator']['path']).relative_to(observed_root.resolve(strict=True))
            item['locator']['path'] = str(alias / 'observed' / relative)
        resources = {item['id']: item for item in doc['resources']}
        premise(set(resources) == {'tree', 'carrier'} and
                all(Path(item['locator']['path']).parent.resolve(strict=True) !=
                    Path(item['locator']['path']).parent for item in resources.values()),
                'rewritten resource locators do not pass through the link')

        fixtures_before = tree_manifest(real)
        # Production callers: Context and snapshot resolve home strictly; observation grants
        # every resource locator, which inventory resolves strictly.
        expect_true('production: snapshot of a home reached through a link is accepted and canonical',
                    lambda: S.snapshot(prod_home)['scope']['home'] == str(prod_home.resolve(strict=True)),
                    'snapshot scope home is not canonical')

        def observe():
            content = R.observation(doc, doc['rows'][0], resources['tree'], f.ctx)
            R.observation(doc, doc['rows'][0], resources['carrier'], f.ctx)
            return content['sha256'] == f.resource['expected']['sha256']
        expect_true('production: resource observation through absolute locators under a link is accepted',
                    observe, 'observed tree hash differs')

        grant = 'resolved root target not granted'
        external = 'external symlink target not granted'
        expect_refusal('a root that links to an ungranted folder', lambda: S.tree_hash(escape_root), grant)
        expect_refusal('the same root when the grant covers only its parent',
                       lambda: S.tree_hash(escape_root, [plain]), grant)
        expect_refusal('a tree whose internal link leaves every grant', lambda: S.tree_hash(escape_tree), external)
        expect_refusal('a granted root under a link whose internal link leaves every grant',
                       lambda: S.tree_hash(alias / 'aliased-escape', [alias / 'aliased-escape']), external)
        expect_refusal('a root under a link with no grant (the guard itself is unchanged)',
                       lambda: S.tree_hash(alias / 'aliased-tree'), grant)
        expect_acceptance('the linked root once its target is granted', lambda: S.tree_hash(escape_root, [outside]))
        expect_acceptance('the escaping tree once its link target is granted',
                          lambda: S.tree_hash(escape_tree, [outside]))
        expect_acceptance('the root under a link once it is itself granted',
                          lambda: S.tree_hash(alias / 'aliased-tree', [alias / 'aliased-tree']))

        fixtures_after = tree_manifest(real)
        record('no-write: guard and observation calls left every fixture entry unchanged',
               fixtures_before == fixtures_after and bool(fixtures_before))
    except Premise as exc:
        print('PROBE FAILED: ' + str(exc))
        return 2
    except Exception as exc:
        print('PROBE FAILED: fixture setup ' + describe(exc))
        return 2
    finally:
        o5.permissions(scratch.resolve(strict=True), False)
        shutil.rmtree(scratch)
    record('no-write: build directory unchanged by this test',
           tree_manifest(build) == build_before and bool(build_before))
    # Literal source grep of the guard module, with its own planted controls on this run.
    pattern = re.compile(r'\b(?:write_text|write_bytes|mkdir|unlink|chmod|rmtree|Popen)\s*\(|'
                         r'\bos\.(?:write|replace|remove|rename)\s*\(|\bsubprocess\.|'
                         r'\.open\([^\n]*["\x27][wax]|\bopen\([^\n]*,[ ]*["\x27][wax]')
    hits = [n for n, line in enumerate((adopt / 'adopt_snapshot.py').read_text().splitlines(), 1)
            if pattern.search(line)]
    planted = ["path.write_text('control')", 'os.replace(a, b)', "open(path, 'w')"]
    controls = sum(bool(pattern.search(line)) for line in planted)
    record('no-write: adopt_snapshot.py source has no write call (planted controls ' +
           str(controls) + '/' + str(len(planted)) + ')', not hits and controls == len(planted),
           '' if not hits else 'lines ' + str(hits))
    failed = results.count(False)
    print(f'FAIL {failed}/{len(results)}' if failed else f'PASS {len(results)}/{len(results)}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
