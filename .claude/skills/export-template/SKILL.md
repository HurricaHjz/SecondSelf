---
name: export-template
description: >
  Sync THIS LLM-Wiki framework with its public GitHub repo, ONE direction per run: --push (vault → repo)
  publishes your framework; --pull (repo → vault) updates your framework from a newer repo version. Also
  builds a standalone content-free copy. Use when the user says "publish/export the framework", "update
  the public repo", "pull the latest framework", or "make the base template". Push shows the diff and
  commits+pushes only after you confirm; pull previews first and writes nothing until --apply. Ships the
  engine (CLAUDE.md, MANUAL.md, skills, graph config) + a tracked demo in examples/seed/, an MIT LICENSE +
  README + setup.sh + a .gitignore that TRACKS the framework and IGNORES all knowledge; strips all
  wiki/raw content + personal data; keeps the AI/LLM-research specialisation. Never copies your knowledge;
  the build dir is deleted after publishing. Full runbook: the RUNBOOK.md in this skill folder.
user-invocable: true
---

# export-template — produce / sync the shareable framework repo

## Goal
Turn this private vault into the public **SecondSelf** framework — **without any knowledge** (no
wiki pages, raw sources, logs, or personal data) but **with** the engine (CLAUDE.md, MANUAL.md, the
skills, the graph config), an empty folder skeleton, a tracked **demo** (`examples/seed/`), a **setup.sh**
bootstrap, an **MIT** licence + README, and a **.gitignore that tracks the framework and ignores all
content**. Keeps the AI/LLM-research specialisation.

> Authoritative runbook + target tree: `RUNBOOK.md` + `SPEC.md` in this skill folder. The human-facing docs
> — **README.md, LICENSE.md + the `assets/` screenshot — live at the vault root** (visible, the
> canonical source); the build machinery (setup.sh, .gitignore/.gitattributes, the shipped settings file, the demo) lives in `payload/`
> here. No separate kit folder, and no build copy is left in the vault after a publish.

## Triggers
`/export-template` · "publish the framework" · "make/refresh the base template" · "update the public repo".

## Choosing the operation — ASK by default
**If the user's words already name the direction, just do it** — don't ask, and don't make them recite flags:
- "publish" / "push" / "export/share the framework" / "update the public repo" → **push**.
- "pull" / "update my framework from git" / "get the latest framework" → **pull**.
- "build/make the template" / "a content-free copy" → **fresh build**.

**Otherwise** (a bare `/export-template`, "sync my framework", "use export-template") **do not guess** —
ask with `AskUserQuestion`:
1. **Direction:** *Push — publish my framework → GitHub* · *Pull — update my framework ← GitHub* ·
   *Build — a standalone content-free copy*.
2. **Then the sub-option for that choice:**
   - **push** → confirm the repo-clone path (and remind them you will show the diff and wait for an OK).
   - **pull** → *Preview only (writes nothing)* vs *Preview then apply*; and *also pull the colour scheme?*
     (`--with-graph`, default **no**).

The user can always skip the questions by stating it directly ("push, message 'tighten lint'", "pull and
apply with graph"). Honour any options they give; only ask for the ones they left unspecified.

## Three operations — ONE direction per run
**Never sync both ways at once.** Each invocation does exactly one of the following; passing `--pull` and
`--push` together is a hard error.

**`--push <repo>` — vault → repo (publish).** Overlays the vault-owned framework (CLAUDE.md, MANUAL.md,
`README.md`/`LICENSE.md` + `assets/`, `.claude/skills/**` (every publishable skill, incl. export-template), the calendar's hook
and its suite under `.claude/hooks/`, `.obsidian` config, the seed demo) **plus** the build machinery from this skill's
`payload/` (.gitignore/.gitattributes, setup.sh, `.claude/settings.json`)
into your existing clone — leaving `.git/` and all knowledge untouched. Then run the **guided publish
flow** below. (`--sync` is a back-compat alias.)
```bash
bash .claude/skills/export-template/export_template.sh --push /path/to/SecondSelf
```

The hooks that ship are those `payload/shipped-hooks.txt` names, the calendar's among them, and the machinery also
packages `.claude/core-paths` and `.github/`.

**`--pull <repo>` — repo → vault (update from a newer version).** Two routes, by what `<repo>` is. A user's copy
**is** a clone of the release, so there `<repo>` is the vault itself: `--pull` fetches, **previews**
the files git would change and **writes nothing**; `--apply` then fast-forwards to the newest commit of the branch it
follows (see "Update (pull)" below).
A vault beside a separate clone takes the copying pull: it `git pull`s your clone, then **previews**
exactly which framework files would change and **writes nothing**. Re-run with `--apply` to copy the repo's
framework into your vault (incl. `README.md`/`LICENSE.md` + `assets/` at the vault root) and
refresh the `payload/` machinery; the repo's `.claude/settings.json` goes to `payload/settings.json` alone, so your own
settings file is never written. Add `--with-graph` to also pull `.obsidian/graph.json` (the colour scheme);
`app.json`/appearance/core-plugins are **never** pulled.
```bash
bash .claude/skills/export-template/export_template.sh --pull /path/to/SecondSelf            # preview
bash .claude/skills/export-template/export_template.sh --pull /path/to/SecondSelf --apply    # apply
```

**Fresh build (no flag)** — a standalone content-free copy (the very first publish, or inspection):
```bash
bash .claude/skills/export-template/export_template.sh template-export
```

## Where the publish files live
The professor-loop skill is excluded from public builds while its standalone prerequisites are being prepared (the owner's decision of 3 November 2026, answer 3g; its upgrade is set for v0.10.2, moved from v0.10.1 by his yes of 9 November 2026 so that v0.10.1 could ship the README). Build and push remove any previous generated copy of that skill from the destination. The source skill remains local. Other skills continue to be discovered automatically.

- **At the vault root** — `README.md`, `LICENSE.md`, `CITATION.cff` + the `assets/` screenshot
  (canonical and visible; edit them in place).
- **`payload/` (in this skill)** — the build machinery: setup.sh, `.gitignore`/`.gitattributes`
  (kept as inert `*.txt`), `settings.json` (shipped as `.claude/settings.json`; updates may
  replace it, so a user's own settings go in `.claude/settings.local.json`, and an approval
  that lands in its `permissions.allow` list stays until a release changes that file),
  `core-paths.txt` (shipped as `.claude/core-paths`: the core, one git pathspec a line) and
  `github/` (shipped as `.github/`: the issue forms), plus the seed demo.

Both round-trip: **push reads** from these locations; **`pull --apply` writes** back to them (the root docs →
the vault root, the machinery → `payload/`), so a repo-side edit flows home on the next pull and is never
clobbered by a push. The only thing deleted after a publish is the build dir (`template-export/`); the root
files and `payload/` always stay. A vault updated by an older exporter, whose pull did not know a newer root file,
needs no second pull: a push keeps the clone's copy of that file and says so, the next ordinary pull brings it to
the vault root, and only a fresh build stops on it, naming that pull.

## Publish (push) — guided; the agent automates, you confirm
When the user wants to publish/update the public repo (`/export-template publish`, "push the latest
framework"), do it end-to-end but **pause once for confirmation before anything goes public**:
**Run the chain, never its steps (2026-09-08).** `bash .claude/skills/export-template/publish.sh --release <candidate> <repo>`
runs steps 1 and 2 as one `&&` chain — pull, overlay, stage, drift check, payload gate, release gate, throttle gate —
prints the recap, writes it to `output/publish-recap.txt` and STOPS there with nothing committed. Its last line is
`recap-digest <digest>`: the fingerprint of that recap and of the staged tree it describes, which step 4 hands back.
Step 3 stays yours — the script never asks. Every failed step ends it non-zero (1 = a gate refused, 2 = a broken
premise, 3 = a git step failed), so failed gates cannot be passed over (known-issues 2026-09-08).
A STOP leaves the clone with the overlay staged and uncommitted
(`git -C <repo> reset -q` clears the index). The numbered steps below are what it runs, and what to read when it stops.
Suite: `test_publish_sh.sh`.
1. **Pull-then-overlay:** `bash .claude/skills/export-template/export_template.sh --push <repo>`.
   First do `git -C <repo> pull --ff-only` (so you never clobber unpulled remote edits), then the overlay.
   (For the very first publish, do a fresh build + create the GitHub repo instead — RUNBOOK §C.)
2. **Stage + review:**
   ```bash
   git -C <repo> add -A
   git -C <repo> --no-pager diff --cached --stat     # summary of what changed
   git -C <repo> --no-pager diff --cached            # full diff (skip only if very large)
   ```
   **Show the user** this and state plainly what will be published.
   **Drift check (2026-09-06):** before the recap, compare every staged file that also exists in the vault with its
   vault copy (`cmp -s` per path from `git diff --cached --name-only`; files the export transforms differ by design, and a
   file with `vault-local` blocks is compared after the same strip) and list any other difference with both mtimes. A difference means the
   vault changed after the overlay (a concurrent session can edit a shipped file between overlay and commit): re-overlay and re-gate, or name the exclusion in the recap. Never commit a tree you have not compared.
   `publish.sh` makes this comparison itself and derives the by-design classes from `export_template.sh` — the paths
   `apply_fixes()` rewrites and the conditional-compile marker whose blocks it strips — plus the files packaged from
   the skill's `payload/`; it runs a marked file through `strip_vault_local.py`, the export's own strip, before it
   compares, names every exemption in the recap and stops on anything else.
   **Writing a marker (`vault-local`, in Markdown):** an inline block goes exactly from its first marker to its last, so
   the begin marker sits straight after the last word that ships and the fragment carries the space it needs inside the
   markers; a block alone on its lines goes with those lines. A re-wrap must keep a marker whole: a split marker halts
   the export.
   **Payload gate (mandatory, before the recap, AFTER `git add -A`):**
   `python3 .claude/skills/export-template/publish_guard.py <repo>` must exit 0. It reads the
   staged tree from git's INDEX (the bytes a commit writes) and runs four probes: an absolute
   path into a machine home directory in ANY file, binary content included; any non-text file
   outside `assets/`, the payload's declared media directory; any string identifying you —
   the agent name, your git name, email local-part and handle, every component of the vault's
   absolute path, your machine account, plus any line in `output/publish-gate-strings.txt` —
   in a file's name or its bytes; and any credential value the parser extracts from your credential store
   (`output/user-notes/credentials.env`, `KEY=value` lines), in a file's name or its bytes. The
   store is read at run time and never copied: a credential finding names the KEY and the file,
   never the value, and every line the guard prints withholds every value of 6 bytes or more that
   it read, raw or in the escaped form an error message or git quotes it in. Matching is literal
   bytes, so a value under 6 bytes, a case-changed copy and an encoded copy (base64,
   URL-encoding) are neither caught in the payload nor withheld from the output. The parser checks
   the extracted text as written and the additional backslash forms defined by `value_readings`
   in `publish_guard.py`. An absent store checks nothing and says so on the
   `personal-strings:` line and never fails the gate; a store it cannot stat or read does. Exit 1
   is a finding and halts the publish like any other gate failure; exit 2 is a `PROBE FAILED`
   premise break (an unstaged tree, an empty or partial payload, a git error, a vault, allowlist
   or credential store it cannot read or parse) and halts it too. The guard
   exempts no file, its own script and suite included: a shipped file that must discuss a home
   path assembles the example from parts rather than writing it as a literal. Scope is keyed on
   the observable property, never a filename list, so the next artefact class halts without an
   edit here. Quote both of its output lines in the recap. Suite: `test_publish_guard.sh`.
   **Credential parsing limits:** the parser reads one `KEY=value` assignment per line, with an optional `export` prefix; blank lines and comment lines are skipped. It trims surrounding whitespace. A value beginning with a single or double quote ends at the first matching quote, treating a backslash and the following byte as a pair inside double quotes. All text after that closing quote is ignored. An unquoted value ends at whitespace followed by `#`; otherwise spaces and quotes within it are kept. The parser does not expand `$`, run command substitutions, join quoted segments or continue values across lines. Its backslash forms cover only the tables and unquoted rule in `value_readings`, not every shell or dotenv interpretation. The 6-byte floor applies to each extracted reading: a quoted prefix below that floor is not checked even if ignored trailing text would make the full value longer.
   **Draft mode (`publish_guard.py --draft <file>`):** the `suggest` skill's gate. The same probes read one suggestion draft
   before a person files it as a public issue, with the same exits: 0 clean, 1 hits, 2 a broken premise. No allowlist
   applies, and the default agent name `setup.sh` seeds is no needle there, since it identifies nobody. A hit warns:
   a person decides, and nothing files by itself. Its path probe reads more spellings than a payload's, because a draft
   is a person's paste; the guard's header lists them, and what it still does not read.
   **What the gate leaves to you** (it derives and adjudicates; the judgement stays yours):
   - **Extra strings only you can name** — an affiliation, a second handle, an ORCID — go one per
     line in `output/publish-gate-strings.txt` (owner-local, never shipped, absent by default and
     reported as absent on every run). Nothing else reaches the gate that the vault cannot derive.
   - **A credential finding has no allowlist.** Remove the value from the payload, and rotate it
     if it was ever pushed. A value shorter than 6 bytes is not scanned (floor set by judgement, unmeasured) — at that length it is
     ordinary text — and every run counts those on its `personal-strings:` line.
   - **An unallowlisted hit halts for inspection.** Judge it: fix the payload, or adjudicate it into
     `publish-allowlist.md` with its reason, once, permanently. That file states its own format and
     the guard parses it, so an entry that names no file or an unknown placeholder halts the gate.
   - **A provisional entry** (an owner-ruled deferral of a class fix to a named release) carries
     per-file occurrence counts. While the class is deferred those counts track the files' growth:
     an over-cap finding on a file the entry already names is a count refresh, a hit in any other
     file is a real finding.
   - **Its expiry** is reported on every run. At the recap, once the candidate version is derived,
     re-run with `--release <ver>`: a provisional entry the candidate has reached becomes a finding
     and must be removed or re-adjudicated before the commit.
   **Throttle gate (mandatory, before the recap):** `python3 .claude/skills/delegate/throttle.py check --require auto` must exit 0 on the vault (`auto` is the default preset from 2026-09-08; a vault still at `default` fails this gate until its owner runs `throttle.py set auto`) — a template is never published with floor definitions, drifted tiers or a description naming a current tier; a `PROBE FAILED` halts the publish like any other gate failure.
   **Candidate recap — mandatory final confirmation:** before committing, present the **candidate's
   row** — `Ver | Feature | What it does | What it achieves` — verified against the actual files/tests
   (never from memory). **Derive the version number from evidence, not memory**: read
   `git -C <repo> log --oneline` AND the vault log's `export |` entries at recap time — a parallel
   session may have published since this session last looked. The **full version-family table** — every release of the
   current minor so far plus the candidate, each row verified — runs only at a **minor-version
   boundary** (the first release of a new minor, vX.Y.0) or when the owner asks for a "full recap".
   The user's go-ahead on the presented recap is the publish approval.
   **Framework paths are name-neutral (2026-08-28).** The agent's own name is user-space config
   (`agent_name`, whose default the shipped `setup.sh` seeds and a user can change), so no shipped path or env var may embed
   it. The agent home is `~/.llm-wiki/` (ingest run ledger, and any future agent-owned state) and
   the lane belt is `LLM_WIKI_LANE`. A vault whose home already sits elsewhere aliases it with a
   machine-local symlink rather than moving data, so the convention costs no migration.
3. **Confirm — mandatory gate:** ask the user to approve and to give/confirm a commit message.
   **Never `commit` or `push` without an explicit "yes".**
4. **Publish:** hand that word back to the same script together with the digest the recap printed — the digest is what
   binds the word to the recap the user actually saw:
   `bash .claude/skills/export-template/publish.sh --release <candidate> --publish "<the user's word>" --message "<message>" --approved <digest> <repo>`.
   That run does **not** pull or overlay again: it checks the recap on disk still digests to `<digest>` and that the
   clone's index is still the tree that recap named, exits 1 naming the first section that differs (the index changed,
   the recap was regenerated, the vault moved), re-runs the four gates read-only on that index, then commits, tags and
   pushes — so what ships is the tree the recap described. `--publish`, `--message` and `--approved` come as a set.
   The tag is annotated, named for `--release`, and goes up with the commit in one atomic push: it is the baseline every
   copy's session check compares with. `--publish` refuses a release that does not read `vX.Y.Z`
   (`^v[0-9]+\.[0-9]+\.[0-9]+$`) and stops before the commit if that tag exists; a failed push removes the local tag.
   Never run `git commit` or `git push` for a publish by hand.
5. **Report & log:** report the commit + push result + the repo URL, then append one `export` entry to
   `wiki/log.md` via shell (version, commit hash, what shipped). The publish event logs `export`; the
   framework edits it ships were already logged as `framework` when made — never log the push as a second
   `framework`. A failed or aborted push logs nothing. If `push` fails on auth, tell the user to set up a
   GitHub token / SSH key — never handle their credentials yourself.
6. **Clean up — keep no local copy:** once the push succeeds, delete the build directory
   (`rm -rf template-export`). A `--push` writes straight to the external repo clone, so nothing is left
   in the vault either way (`payload/` stays — it is the skill, not a build artifact).
7. **Private backup — gated closing step:** if the vault root is a git repo with a remote, and the
   stop under "Private vault backup" does not apply, back the vault up now: `git add -A && git commit -m "backup: YYYY-MM-DD (post <version> publish)" && git push`
   (owner identity, no AI attribution). Report the result in-reply; never ask for confirmation and
   never log it in `wiki/log.md`. If the vault has no git repo or remote, say so briefly and move
   on — the backup must never block a publish. It stays outside the publish chain: `publish.sh` writes only to the repo
   clone and its own recap file, never to this vault's own repository. That recap is an ordinary file under `output/`:
   unless this vault's `.gitignore` excludes that directory, this backup commits it, owner word included.

## Update (pull) — guided; preview → confirm → apply
When the user wants to bring a newer framework from the repo into their vault ("pull the latest framework",
"update my framework from git"):
   *(Logging: a confirmed `--pull --apply` changes this vault's framework — log it as `framework`, never `export`.)*
1. **Preview:** `bash .claude/skills/export-template/export_template.sh --pull <repo>`. Show the user the
   listed framework files that would change (README/CLAUDE/Manual/skills, plus, on the
   copying pull, the `payload/` refresh). **Nothing is written yet.**
2. **Confirm — mandatory gate:** ask the user to approve overwriting those vault framework files. Remind
   them their knowledge (`wiki/ raw/ output/` (and your own `assets/` media)) and `.obsidian` config (bar
   `graph.json` when they choose `--with-graph`) are left untouched.
   **Never `--apply` without an explicit "yes".**
3. **Apply:** `bash .claude/skills/export-template/export_template.sh --pull <repo> --apply`
   (add `--with-graph` only if they also want the colour scheme).
4. **Report** what changed; suggest re-reading CLAUDE.md and reopening Obsidian if skills/graph changed.

**In a clone, what `--apply` does.** Git writes every core file. The script lifts Obsidian's four `skip-worktree` marks,
runs `git merge --ff-only --no-overwrite-ignore` onto the newest commit of the branch the clone follows, then
`bash setup.sh --lock`, which sets the marks and locks the core again, whichever way the merge went. Nothing else runs: no
step sets a file aside, replaces a file the user changed or saves the throttle's lines, and git's own refusals stand, each
naming the file in the way. A refusal or a failure exits 1. A user whose throttle is not `auto`, or whose
`.claude/routing.local.json` changes a helper, follows MANUAL.md's "Updating", which also says what to do when git refuses
and how to recover from a failure partway. A backup by `bash setup.sh --backup <URL>` adds no commit the release lacks.
`python3 .claude/hooks/core-check.py --report` prints the core's state after an update.

**From a separate clone,** the copying pull refuses a vault that is itself a clone of the release, whose root files it would
leave old, and it prints stale skills and agents in place of deleting them.

## Guarantees
- **One direction per run:** `--pull` and `--push` are mutually exclusive (passing both errors out) — the
  framework never syncs both ways at once.
- **Pull is preview-first & safe:** `--pull` writes nothing without `--apply`; even with `--apply` it
  touches only framework files + `payload/`, **never** your knowledge (`wiki/ raw/ output/` (and your own `assets/` media)) or
  your `.obsidian` config (`graph.json` only, and only with `--with-graph`). It copies skills per-name —
  including `export-template` itself; replacing the running script mid-pull is Unix-safe (the old inode
  stays open, the new version applies next run).
- **The core is read-only in a user's copy:** `setup.sh` removes the write bits from the tracked core files, a helper
  definition and `.claude/settings.json` staying writable, and it locks again after every update; the shipped deny rules
  stop the agent's own file tools. A person can still change the core: `bash setup.sh --unlock` lifts the bits, and the
  session line then shows the change. In a clone a core file the user changed is never quietly overwritten: where a
  release changes it, git refuses and names it.
- **No build copy left behind:** the build dir (`template-export/`) is deleted after publishing; the
  persistent sources are the vault-root docs (`README.md`, `LICENSE.md`, `assets/`) and this
  skill's `payload/` (setup.sh, git dotfiles, demo) — both kept fresh by `pull --apply`.
- **Never publishes unreviewed:** the publish flow always shows the diff and waits for your explicit OK
  before `commit`/`push`; your git credentials stay yours.
- **Read-only on the vault except `pull --apply`** (build/push write only under OUT / the repo clone).
- **No knowledge or personal data shipped** — `wiki/**`, `raw/**`, logs, `wiki/user/**` are never copied;
  `wiki/` + `raw/` ship empty (`.gitkeep`); the demo lives in `examples/seed/` only. The owner's own routing rows
  (`routing.json` rows marked `"layer": "yours"`) stay out of the public copy, and a row marked `"layer": "core"` ships.
  A row with no mark, or any other mark, stops the export before it copies anything; `routing_marks.py` holds the rule,
  and `python3 routing_marks.py --check <table>` lists what it refuses.
- **Git policy baked in**: the shipped `.gitignore` tracks the framework and ignores all content, so a
  user's notes never get committed (matches CLAUDE.md §11).
- `export-template` **ships too** and syncs like any other skill — users need only its `--pull`
  (updating their framework copy); `--push` is the maintainer's publish path. Framework development
  happens in the maintainer's vault; a user's way in is a suggestion, below.
- Personal data (the owner's e-mail addresses, credentials), machine paths, identifiers and incident
  stories never ship.

## Suggestions and bug reports
A user who wants a core change uses `/suggest`: it offers their own layer first, drafts the
suggestion, runs the draft gate and leaves the filing to them. The issue forms ship as
`.github/ISSUE_TEMPLATE/`, from `payload/github/`. A bug report carries the session's `core:` line
(`python3 .claude/hooks/core-check.py --report`), a required field of its form, so a local change is
not read as a framework fault.

## After building — verify + publish
See RUNBOOK.md §B (verify: content git-ignored; framework tracked; no personal leak) and
§C (publish: GitHub New repo → `git init/add/commit/remote/push` → mark as a Template repository).

## Private vault backup (agent-maintained)

**Stop first in a user's copy.** Where `.claude/core-paths` exists, or `origin` is the public
repository (`repository-code` in `CITATION.cff`), a backup commit in the clone would stop every
later update, which refuses commits the release lacks. Commit nothing there: say that a backup needs
a repository of its own, and offer `bash setup.sh --backup <URL>`, which keeps a bare git folder
outside the vault, adds the user's layer with `add -f` and pushes there, never committing to the
clone.

The vault's *own* git repo (private remote) is the owner's full backup — knowledge included, no review
gate. Two triggers, one command (`git add -A && git commit -m "backup: YYYY-MM-DD — <one-phrase what>"
&& git push`, owner identity):
- **After every successful public publish** — step 7 of the publish flow above.
- **On request** ("back up the vault", "push the private repo") — any time, including wiki-only days:
  the commit simply carries whatever changed.
Routine backups are never logged in `wiki/log.md` — the log records brain changes, not bookkeeping.
This repo is distinct from the public framework clone; never point one remote at the other
(CLAUDE.md §11). The Obsidian Git plugin remains an optional extra for continuous timed auto-backups;
the publish/pull git steps above stay shell-driven because the framework repo is a separate clone,
**not** this vault.
