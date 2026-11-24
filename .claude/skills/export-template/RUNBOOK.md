# RUNBOOK — publish & maintain the SecondSelf framework

Turns the private vault into the public framework repo **github.com/HurricaHjz/SecondSelf** (renamed 2026-10-18 from `second-yourself`, and 2026-09-08 from `obsidian-llm-wiki-assistant`; GitHub redirects the old URLs), with
your knowledge kept local. Read top to bottom.

## A. Build the template
```bash
bash .claude/skills/export-template/export_template.sh template-export
```
Produces `template-export/` per `SPEC.md`.

## B. Verify (script prints most of this — confirm)
- Skills are discovered automatically. The public payload contains every discovered skill except professor-loop, whose standalone prerequisites are still being prepared (the owner's decision of 3 November 2026, answer 3g; its upgrade is set for v0.10.2, moved from v0.10.1 by his yes of 9 November 2026 so that v0.10.1 could ship the README). Verify both that professor-loop is absent and that an ordinary skill and export-template are present. Verify the vault's excluded skill is unchanged. The exclusion applies to build/push packaging, not to private source maintenance.
- **Suites — discover every test file the tree holds, account for dispatcher-owned helpers, run each independent entry and the build-side re-run; green means every invocation exits 0 with a recognised complete result, or with a closing line the loop does not recognise that the recap quotes and a reading by hand finds to be the suite's own zero-failure tally, and no discovery or scheduling probe remains** (never compare against a historical count — assertion totals grow). Adopt results are validated from their result record and closing line; incomplete, failed and probe-failed adopt results are non-green, and the adopt suite reports incomplete while its live consumer integration is outside the supplied grant. An accounted helper carries its parent's coverage state, not an additional pass.
  Run the block with its two-space indentation removed: the heredoc's terminator must start its line and Python reads indentation. Run it from the vault's root after building `template-export`, as today's loop runs in place, with `TMPDIR` naming an existing scratch directory. Retain the printed log folder for the recap. The loop discovers tests, obtains helper ownership from the dispatcher, supplies adopt arguments and includes the build-side export rerun and the build-side hands-off smoke. The test processes may write their private fixtures; the result validator reads evidence only.
  ```bash
  python3 -B - <<'ADOPT_EXPORT_RECAP'
  import collections
  import json
  import os
  from pathlib import Path
  import re
  import stat
  import subprocess
  import sys
  import tempfile

  sys.dont_write_bytecode = True
  root = Path.cwd().resolve()
  tmp = os.environ.get('TMPDIR')
  if not tmp or not Path(tmp).is_dir():
      print('PROBE FAILED: explicit existing TMPDIR required')
      raise SystemExit(2)
  logs = Path(tempfile.mkdtemp(prefix='suite-recap.', dir=tmp))
  print('suite logs: ' + str(logs))
  classes = ('SUITE PASS', 'SUITE FAILED', 'SUITE PROBE FAILED', 'SUITE INCOMPLETE')
  counts = collections.Counter({name: 0 for name in classes})
  results, delegated, unresolved, scheduling, by_hand = {}, {}, [], [], []
  adopt = root / '.claude/skills/adopt'
  register = adopt / 'test_register.py'
  validator = adopt / 'suite_results.py'
  prefix = '.claude/skills/adopt/'
  managed = {prefix + 'test_register.py': 'register', prefix + 'test_adopt.sh': 'register',
             prefix + 'test_generated_dates.py': 'generated-dates', prefix + 'test_o5.py': 'o5',
             prefix + 'test_fingerprint.py': 'fingerprint'}
  link_entry = prefix + 'test_link_roots.py'
  # Today's verdict tokens, unchanged: a suite's verdict is the last one in its merged log.
  TOKENS = re.compile(r'PASS [0-9]+/[0-9]+|FAIL [0-9]+/[0-9]+|[0-9]+ passed, [0-9]+ failed|'
                      r'[0-9]+/[0-9]+ passed|Ran [0-9]+ tests|^OK$', re.M)

  def no_scan(error):
      raise error

  try:
      discovered = []
      if not (root / '.claude').is_dir():
          raise ValueError('no .claude directory')
      for parent, dirs, files in os.walk(root / '.claude', onerror=no_scan, followlinks=False):
          dirs[:] = sorted(d for d in dirs if d != '__pycache__')
          for name in sorted(files):
              path = Path(parent) / name
              if re.fullmatch(r'test_.*\.(?:sh|py)', name) and stat.S_ISREG(path.lstat().st_mode):
                  discovered.append(path.relative_to(root).as_posix())
      discovered.sort()
  except (OSError, ValueError) as error:
      print('PROBE FAILED: discovery: ' + str(error))
      raise SystemExit(2)
  if not discovered:
      scheduling.append('no suites found')

  def capture(argv, directory, working, merged):
      directory.mkdir()
      scratch = directory / 'tmp'
      scratch.mkdir()
      env = dict(os.environ, TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1')
      (directory / 'command.json').write_text(json.dumps({'argv': argv, 'status': None}))
      try:
          process = subprocess.run(argv, cwd=working, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT if merged else subprocess.PIPE,
                                   text=True, errors='replace')
      except OSError as error:
          (directory / 'command.json').write_text(json.dumps({'argv': argv, 'status': None, 'error': str(error)}))
          raise
      if merged:
          (directory / 'log').write_text(process.stdout)
      else:
          (directory / 'stdout').write_text(process.stdout)
          (directory / 'stderr').write_text(process.stderr)
      (directory / 'command.json').write_text(json.dumps({'argv': argv, 'status': process.returncode}))
      return process

  owners = None
  if any(path.startswith(prefix) for path in discovered):
      try:
          inv = capture([sys.executable, '-B', str(validator), 'inventory', '--suite', 'register',
                         '--scope', 'all', '--producer', str(register)], logs / 'inventory', root, False)
          if inv.returncode != 0:
              raise ValueError('inventory command failed; see inventory logs')
          packet = json.loads(inv.stdout)
          if packet['suite'] != 'register' or packet['scope'] != 'all':
              raise ValueError('wrong inventory scope')
          owners = {}
          for family in packet['inventory']:
              for module in family['modules']:
                  if module['role'] == 'helper':
                      if module['path'] in managed or module['path'] == link_entry:
                          raise ValueError('independent entry declared as a helper')
                      owners.setdefault(module['path'], []).append(family['id'])
      except (OSError, ValueError, KeyError, TypeError) as error:
          owners = None
          scheduling.append('adopt inventory: ' + str(error))

  def legacy(log, rc, link_roots=False):
      found = TOKENS.findall(log)
      token = found[-1] if found else ''
      last = next((line.strip() for line in reversed(log.splitlines()) if line.strip()), '')
      seen = token or last or 'empty output'
      passed = re.fullmatch(r'PASS ([1-9][0-9]*)/([1-9][0-9]*)', token)
      if link_roots:
          failed = re.fullmatch(r'FAIL ([1-9][0-9]*)/([1-9][0-9]*)', token)
          if rc == 0 and passed and passed[1] == passed[2]:
              return 0, token
          if rc == 1 and failed and int(failed[1]) <= int(failed[2]):
              return 1, token
          if rc == 2 and re.search(r'^PROBE FAILED: ', log, re.M):
              return 2, last
          return 2, 'inconsistent link-roots verdict, exit ' + str(rc) + ': ' + seen
      if rc != 0:
          return 1, seen
      pair = re.fullmatch(r'([1-9][0-9]*) passed, 0 failed', token)
      ratio = re.fullmatch(r'([1-9][0-9]*)/([1-9][0-9]*) passed', token)
      ran = re.findall(r'^Ran ([0-9]+) tests? in ', log, re.M)
      unittest = token == 'OK' and bool(ran) and int(ran[-1]) > 0
      if (passed and passed[1] == passed[2]) or pair or (ratio and ratio[1] == ratio[2]) or unittest:
          return 0, token
      return 2, 'unrecognised or incomplete verdict, read by hand: ' + seen

  def invoke(label, argv, working, suite=None, producer=None, link_roots=False):
      directory = logs / ('suite-' + str(len(results) + 1))
      raw_status, states, detail = None, None, ''
      try:
          process = capture(argv, directory, working, suite is None)
          raw_status = process.returncode
          if suite is None:
              outcome, closing = legacy(process.stdout, raw_status, link_roots)
          else:
              command = [sys.executable, '-B', str(validator), 'validate', '--suite', suite,
                         '--scope', 'all', '--producer', str(producer), '--stdout', str(directory / 'stdout'),
                         '--status', str(raw_status), '--hook', 'absent']
              checked = capture(command, directory / 'validation', root, False)
              if checked.returncode != 0:
                  raise ValueError('result validation failed; see validation logs')
              value = json.loads(checked.stdout)
              outcome, closing, states = value['exit'], value['closing_line'], value['states']
              for name, field in (('unrun', 'unrun_ids'), ('failed', 'failed_ids'), ('probes', 'probe_keys')):
                  if value[field]:
                      detail += ' :: ' + name + ': ' + ', '.join(value[field])
              if type(outcome) is not int or outcome not in range(4) or outcome != raw_status:
                  raise ValueError('invalid validated exit')
              if type(states) is not dict:
                  raise ValueError('invalid validated states')
      except (OSError, ValueError, KeyError, TypeError) as error:
          outcome, closing = 2, 'probe: ' + str(error)
      category = classes[outcome]
      counts[category] += 1
      results[label] = {'class': category, 'status': raw_status, 'states': states}
      if closing.startswith('unrecognised'):
          by_hand.append(label)
      print(label + ' :: ' + category + ' :: ' + closing + detail)

  for relative in discovered:
      path = root / relative
      if relative.startswith(prefix):
          if owners is None:
              unresolved.append(relative)
              continue
          if relative in owners:
              delegated[relative] = owners[relative]
              continue
          if relative not in managed and relative != link_entry:
              unresolved.append(relative)
              scheduling.append('no adopt adapter or helper owner: ' + relative)
              continue
          argv = ([sys.executable, '-B', str(path)] if path.suffix == '.py'
                  else ['/bin/sh', str(path)])
          if relative == prefix + 'test_generated_dates.py':
              argv += ['--adopt-dir', str(adopt)]
          if relative in (prefix + 'test_o5.py', link_entry):
              argv += ['--build', str(adopt.parent)]
          suite = managed.get(relative)
          provider = register if suite == 'register' else path
          invoke(relative, argv, path.parent, suite, provider, relative == link_entry)
      else:
          argv = ([sys.executable, '-B', str(path)] if path.suffix == '.py'
                  else ['/bin/bash', str(path)])
          invoke(relative, argv, path.parent)

  states = results.get(prefix + 'test_register.py', {}).get('states') or {}
  for relative, family_ids in sorted(delegated.items()):
      state = ', '.join(family + '=' + states.get(family, 'coverage unknown') for family in family_ids)
      print(relative + ' :: accounted by test_register.py :: ' + state)
      if any(family not in states for family in family_ids):
          scheduling.append('unverified delegated coverage: ' + relative)
  for relative in unresolved:
      print(relative + ' :: unresolved scheduling; no test invoked')

  built = root / 'template-export/.claude/skills/export-template/test_export_template.sh'
  if built.is_file():
      invoke('build-side export rerun', ['/bin/bash', str(built)], built.parent)
  else:
      scheduling.append('build-side export suite absent')
  handsoff = root / 'template-export/.claude/skills/delegate/test_handsoff.sh'
  if handsoff.is_file():
      # test_handsoff.sh aims at another tree when HANDSOFF, HOOKS_DIR or LANE_PY is set, so the smoke runs without them
      invoke('build-side hands-off smoke', ['/usr/bin/env', '-u', 'HANDSOFF', '-u', 'HOOKS_DIR', '-u', 'LANE_PY',
                                            '/bin/bash', str(handsoff), '--leg', 'Kcdbad8e4'], handsoff.parent)
  else:
      scheduling.append('build-side hands-off suite absent')
  for reason in scheduling:
      print('PROBE FAILED: scheduling: ' + reason)
  print('discovered: %d; accounted helpers: %d; unresolved: %d' %
        (len(discovered), len(delegated), len(unresolved)))
  print('read by hand: ' + str(len(by_hand)) + ''.join('; ' + label for label in by_hand))
  print('invocations: ' + str(len(results)) + '; ' +
        '; '.join(name + ': ' + str(counts[name]) for name in classes))
  if sum(counts.values()) != len(results):
      raise SystemExit('PROBE FAILED: recap accounting')
  raise SystemExit(1 if counts['SUITE FAILED'] else
                   2 if scheduling or counts['SUITE PROBE FAILED'] else
                   3 if counts['SUITE INCOMPLETE'] else 0)
  ADOPT_EXPORT_RECAP
  ```
  Quote one `suite :: class :: closing line` entry per invocation, with any `unrun`, `failed` and `probes` IDs an adopt entry prints after it, so that a newly unrun obligation shows by name, and give the four class counts, which sum to the invocations. An unrecognised or empty verdict counts under SUITE PROBE FAILED and is listed under `read by hand`; read it from its retained log and quote its last line, as it is not a pass. Give the discovered-file count, each helper's owning family and coverage state, and every unresolved scheduling probe separately. Accounted helpers are not invocations or additional passes. A total carried from an earlier run is not a verification.
  The build-side re-run exists because the copy's premises differ from the vault's (`wiki/` is empty by
  construction): a guard can pass here and fail there; this line makes it repeat.
  A red hands-off smoke means the built tree cannot run the hands-off machinery: read its retained log, which names the missing hook or the module that does not load, fix the shipped-hook list or the strip, rebuild, and run the recap again.
- `template-export/wiki` & `/raw` hold only `.gitkeep` (no seed, no `index.md`/`log.md`); the demo is in
  `template-export/examples/seed/`.
- No personal leak: the payload gate below covers this, deriving your strings from the vault rather
  than asking you to recall them. Strings it cannot derive — an affiliation, a second handle, an ORCID
  — go one per line in `output/publish-gate-strings.txt` (owner-local, never shipped). The same gate
  keeps every credential value of 6 bytes or more that its parser extracts from `output/user-notes/credentials.env` out of the
  payload as literal bytes (floor set by judgement, unmeasured), reading the store at run time and naming a hit by its KEY, never its
  value; a shorter value, a case-changed copy or an encoded one (base64, URL-encoding) is not
  caught. Check by eye only
  that `template-export/wiki/user/` is empty.
- **Credential parsing limits:** the parser reads one `KEY=value` assignment per line, with an optional `export` prefix; blank lines and comment lines are skipped. It trims surrounding whitespace. A value beginning with a single or double quote ends at the first matching quote, treating a backslash and the following byte as a pair inside double quotes. All text after that closing quote is ignored. An unquoted value ends at whitespace followed by `#`; otherwise spaces and quotes within it are kept. The parser checks the extracted text as written and the additional backslash forms defined by `value_readings` in `publish_guard.py`. It does not expand `$`, run command substitutions, join quoted segments or continue values across lines, and does not cover every shell or dotenv interpretation. The 6-byte floor applies to each extracted reading: a quoted prefix below that floor is not checked even if ignored trailing text would make the full value longer.
- **Git-policy test** (the important one):
  ```bash
  cd template-export && git init -q && git add -A
  n=0; for p in wiki/log.md raw/x.md output/y.md wiki/sources/z.md; do git check-ignore -q "$p" && n=$((n + 1)); done
  [ "$n" = 4 ] && echo "content ignored ✓"   # one path per call: git refuses --quiet with several paths (exit 128)
  git ls-files | grep -qE 'CLAUDE.md|MANUAL.md|\.claude/skills/|examples/seed' && echo "framework tracked ✓"
  cd ..
  ```
- **Payload gate** (run it AFTER the git-policy test above, so it reads the index rather than the
  disk): `python3 .claude/skills/export-template/publish_guard.py template-export` → expect
  `check: clean` with a non-zero file count and its control tally, plus the `personal-strings:` line,
  which carries the credential count (`credentials: N value(s) checked`, or `no credential file`).
  Exit 1 lists the offending files: an absolute path into a machine home directory in any file, a
  non-text file outside `assets/`, a personal string in a file's name or bytes that
  `publish-allowlist.md` does not adjudicate for that file, or a credential value extracted from your store under the parsing limits above,
  named by its KEY and never printed. Exit 2 is a broken premise (unstaged tree, empty or partial
  build, git unusable, a vault, allowlist or credential store it cannot read or parse) and is never
  a pass.
- **setup.sh test**: in a copy, `bash setup.sh` creates `index.md`/`log.md`; `--with-example` loads the demo. In a clone it also removes the write bits from the tracked core files, a helper definition and `.claude/settings.json` staying writable; `--unlock` then `--lock` round-trips, and `git status` stays empty.
- **`audited:` policy (decided 2026-08-27)**: the `setup.sh` seeders stamp `audited:` at seed time (creation-with-assignment is the check, §4.6); the shipped example pages deliberately carry **none** — stamping them would backfill a badge nobody checked, and "absent = pre-rule" is their honest state. A future §4.1 field change must sweep both surfaces (CLAUDE.md §12, the emitting-surfaces rule).

## C. Publish (first time)
1. **github.com → New repository** → name `SecondSelf` → **Public** → do **not** add a README or
   licence (we ship them) → **Create repository**.
2. In Terminal:
   ```bash
   cd template-export
   git init -b main
   git add -A
   git commit -m "SecondSelf: framework v0.1"
   git remote add origin https://github.com/HurricaHjz/SecondSelf.git
   git push -u origin main
   ```
3. On GitHub → **Settings → tick "Template repository"**; add a description + topics
   (`obsidian`, `claude`, `second-brain`, `llm`, `knowledge-management`, `ai-research`).
4. The README images already ship (`assets/framework_demo.png`, `assets/hero.png`, `assets/three-parts.png` — tracked, referenced
   by `README.md`). To refresh one later, replace it under `assets/` at your vault root (where the README
   lives), then `--push` again. A new image also needs its `!/assets/<name>` line in the skill's `payload/gitignore.txt`:
   without it `publish.sh` stops at its README-image check, naming the image.
5. Tag the first release, since every copy's session check compares with the newest `v*` tag:
   `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`. `publish.sh` tags every later release.

> No `gh` CLI needed. Prefer a GUI? **GitHub Desktop**: File → Add local repo → `template-export` →
> Publish repository (untick "keep private").

## D. Maintain — push and pull (ONE direction at a time)
The framework round-trips with the repo (README.md, LICENSE.md + `assets/` at the vault root; the
build machinery in the skill's `payload/`). Keep your clone **outside the vault**; never sync both ways at
once. **Easiest:**
ask the agent to publish or update via the
`export-template` skill — it automates the steps and **pauses for your confirmation** before anything is
written publicly or back into your vault (see the skill's "Publish (push)" / "Update (pull)" flows). Manual
equivalents:

**No clone on this machine.** The repo exists on GitHub and this machine has never cloned it — the
ordinary state of a new or reimaged machine, and what the script reports as
`ERROR: <path> is not a git clone`. Clone it once, outside the vault, then proceed as this section:
`git clone https://github.com/<owner>/<repo>.git /path/to/<repo>`. §C is only for creating a repo that
does not exist yet.

**Push (vault → repo)** — you improved the framework locally and want to publish it. One chain, never the steps by
hand (known-issues 2026-09-08). (§C's first publish is the one
exception: no clone exists there yet, so there is nothing to pull, overlay or gate.)
```bash
bash .claude/skills/export-template/publish.sh --release <candidate> /path/to/SecondSelf
#   pull --ff-only → overlay → add -A → README images → drift check → payload gate → release gate → throttle gate → recap,
#   then STOPS: nothing committed, the recap in output/publish-recap.txt. Read it. Its last line is
#   `recap-digest <digest>` — the fingerprint of that recap and of the staged tree it describes.
bash .claude/skills/export-template/publish.sh --release <candidate> --publish "<your word>" --message "<message>" \
     --approved <digest> /path/to/SecondSelf    # only after you have read that recap
```
The second run neither pulls nor overlays: `--approved` is what binds your word to the recap you read, so it re-gates
the staged tree as it stands and exits 1 naming the first section that differs if the recap or that tree has moved
since. It then commits, makes the annotated release tag and pushes both in one atomic push; `--publish` refuses a release
that does not read `vX.Y.Z` and stops before the commit if that tag exists, and a failed push removes the local tag.
`publish.sh` exits 0 at the recap or after the push, 1 when a gate refuses, 2 on a broken premise and 3 when a
git step fails; nothing is committed on any non-zero exit, and a STOP leaves the clone staged and uncommitted
(`git -C <repo> reset -q`). `export_template.sh --push` is the overlay step it runs, and stays usable on its own for an
overlay with no publish.
`--push` overlays vault-owned files (CLAUDE.md, MANUAL.md, `README.md`/`LICENSE.md` + `assets/`,
the publishable skills under `.claude/skills/**` (the exception is listed in §B), the hooks `payload/shipped-hooks.txt` names, `.obsidian` config, `examples/seed`) **and** the build machinery from the skill's
`payload/` (setup.sh, .gitignore, .gitattributes, `.claude/settings.json`, `.claude/core-paths`, `.github/`), leaving `.git/` untouched. (`--sync` is an alias.)

**Pull (repo → vault)** — the repo has a newer framework (another machine, a merged PR) and you want it:
```bash
bash .claude/skills/export-template/export_template.sh --pull /path/to/SecondSelf            # preview — writes nothing
bash .claude/skills/export-template/export_template.sh --pull /path/to/SecondSelf --apply    # apply (+ --with-graph for colours)
```
A public user's copy is itself a clone, so there the path is the vault and the update is a git fast-forward to the newest
commit of the branch it follows, git's own refusals standing (SKILL.md, "Update (pull)"). This route is the copying pull, for a vault beside a clone: it
refuses a vault that is itself a clone of the release, and it prints stale skills and agents in place of deleting them.
`--pull` previews which framework files differ, then (with `--apply`) copies CLAUDE.md, MANUAL.md,
`README.md`/`LICENSE.md` + `assets/`, the skills and the shipped hooks into your vault and refreshes the `payload/`
machinery (the repo's `.claude/settings.json` goes to `payload/settings.json` alone) — **never** touching your knowledge (`wiki/ raw/ output/` and your own `assets/` media) or `.obsidian` config. It copies
skills per-name — including `export-template` itself; replacing the running script mid-pull is Unix-safe (the old inode stays open).

### If the GitHub repo gets renamed
GitHub redirects the old URL so pushes keep working, but fix the name promptly — a redirect dies if the
old name is ever re-registered. Three steps, in order:
1. **Detect:** the push output prints a `remote:` moved notice, or
   `gh repo view <owner>/<old-name> --json nameWithOwner` resolves to the new name.
2. **Re-point the clone:** `git -C /path/to/<clone> remote set-url origin
   https://github.com/<owner>/<new-name>.git`, then verify with `git fetch --dry-run`.
3. **Sweep the live framework files** for the old name (README.md, CITATION.cff, this RUNBOOK, SKILL.md, SPEC.md,
   `payload/setup.sh` — enumerate with `grep -r` first; after replacing, verify zero standalone old-name
   hits remain plus a positive new-name control). Log the sweep as `framework`; it ships on the next
   publish. Historical layers (wiki pages, log entries, archived quotes) keep the old name — history
   stays as written.

## Golden rules
- Edit the framework in the **vault**, not in the repo (else `--push` can't carry your change across).
- **Pull before you push** — keeps `payload/` current and avoids clobbering remote edits (merged PRs).
- **One direction per run:** `--pull` and `--push` never happen together.
- Never `git add` knowledge (`wiki/**`, `index.md`, `log.md`, `raw/**`, `output/**`); the `.gitignore`
  blocks it — don't force past it.
- Never ship personal data; keep the demo clearly deletable (`setup.sh --reset`).
