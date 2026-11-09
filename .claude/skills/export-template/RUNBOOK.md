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
- **Suites — run every one the tree holds (discovered from the tree), then the build-side re-run; green = `0 failed` printed by each suite itself** (never compare against a historical count — assertion totals grow):
  ```bash
  n=0; L=$(mktemp -d); while IFS= read -r t; do n=$((n+1)); d=$(dirname "$t"); f=$(basename "$t")
    case "$f" in *.py) (cd "$d" && python3 "$f") ;; *) (cd "$d" && bash "$f") ;; esac > "$L/$n.log" 2>&1 || echo "SUITE FAILED: $t"
    echo "$t :: $(grep -E -o 'PASS [0-9]+/[0-9]+|FAIL [0-9]+/[0-9]+|[0-9]+ passed, [0-9]+ failed|[0-9]+/[0-9]+ passed|Ran [0-9]+ tests|^OK$' "$L/$n.log" | tail -1)"
  done < <(find .claude -type f \( -name 'test_*.sh' -o -name 'test_*.py' \) -not -path '*/__pycache__/*' | sort)
  echo "suites run: $n"; [ "$n" -gt 0 ] || echo "PROBE FAILED: no suites found"
  ```
  Quote the `suite :: verdict` lines in the recap and sum them there, visibly; an empty verdict is a suite whose
  result line the parser did not recognise, to be read by hand, never a pass. A total carried from an earlier run
  is not a verification.
  ```bash
  (cd template-export/.claude/skills/export-template && bash test_export_template.sh) || echo "SUITE FAILED: export suite INSIDE the build"
  ```
  The build-side re-run exists because the copy's premises differ from the vault's (`wiki/` is empty by
  construction): a guard can pass here and fail there; this line makes it repeat.
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
   lives), then `--push` again.
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
#   pull --ff-only → overlay → add -A → drift check → payload gate → release gate → throttle gate → recap,
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
