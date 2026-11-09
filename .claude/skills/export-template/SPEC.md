# SPEC — target shape of the published template

What `export_template.sh` produces in `template-export/` (and what the public repo should look like).

## Final file tree (publishable repo)
```
SecondSelf/                       (= template-export/)
├── README.md                  # onboarding: what it is · prerequisites · quick start → Manual
├── MANUAL.md                  # how to use it (beginner-first)
├── LICENSE.md                 # MIT — Mingjun (Jerry) Zhang, 2026
├── CITATION.cff               # how to cite: SecondSelf, MIT
├── .gitignore                 # tracks the framework, ignores all knowledge/content
├── .gitattributes
├── setup.sh                   # first-run bootstrap (registries; the lane home via `lane.py init`; --with-example; --reset) and the core's lock (--lock; --unlock), the opt-in kits (--enable; --disable) and a private backup (--backup)
├── CLAUDE.md                  # the agent's contract
├── .claude/skills/            # ingest · gather · delegate (with lane.py, the fence, routing.json, the lane core and slices) · query · output · reflect · lint · deep-lint · attic · qmd-search · adopt · project · weekly-audit · suggest · export-template (ships with its payload/)
├── .claude/hooks/             # the files payload/shipped-hooks.txt names, and optional-hooks.json, the opt-in kits `setup.sh --enable` merges
├── .claude/agents/            # the helper definitions; each one's model: and effort: lines are derived by the throttle
├── .claude/core-paths         # the core, one git pathspec a line, packaged from payload/core-paths.txt
├── .claude/settings.json      # the shipped hooks' lines and the generated deny list, packaged from payload/settings.json; updates may replace it, so a user's own settings go in .claude/settings.local.json
├── .github/ISSUE_TEMPLATE/    # core-suggestion.yml, bug-report.yml, config.yml, packaged from payload/github/
├── .obsidian/                 # graph.json, app.json, core-plugins.json, appearance.json ONLY
├── assets/                   # README images (framework_demo.png, hero.png, three-parts.png) force-tracked; other media gitignored
├── output/                    # empty (.gitkeep)
├── attic/                     # empty (.gitkeep) — owner cold storage; contents gitignored
├── raw/                       # 11 empty lanes (.gitkeep) — NO seed (content is gitignored)
│   └── 1-articles/ … 9-originals/ · archives/ · duplicates/
├── wiki/                      # 11 empty type folders (.gitkeep) — NO seed, NO index/log (gitignored)
│   └── concepts/ entities/ tools/ models/ benchmarks/ sources/ syntheses/ developments/ maps/ user/ experience/
└── examples/seed/             # the demo (TRACKED, separate from wiki/raw so .gitignore keeps it)
    ├── raw/2-papers/example-gpt4-and-mmlu.md
    └── wiki/{index.md, log.md, sources/, concepts/, entities/, models/, benchmarks/, maps/}
```

The skills line above names this release's skills. The export copies every skill the tree holds except `professor-loop` and a user's own `my-*` (`export_template.sh`), so a new skill ships with no change to the export, and `test_suggest.sh` asks for its name on that line.

## Git tracking policy
- **Tracked (framework):** README, Manual, LICENSE.md, CITATION.cff, .gitignore, .gitattributes, setup.sh,
  CLAUDE.md, `.claude/skills/**`, `.claude/agents/`, the shipped hooks, `.claude/core-paths`, `.claude/settings.json`, `.github/`,
  `.obsidian/{graph,app,core-plugins,appearance}.json`, the `.gitkeep`
  skeleton, and `examples/`.
- **Ignored (local knowledge):** `wiki/**` (incl. `index.md`, `log.md`), `raw/**`, `assets/**` (bar the README images),
  `output/**`, `attic/**`, `template-export/`, `CALENDAR.md`, `CALENDAR-done.md`, plus `.obsidian/workspace*.json`/`plugins/`/`cache`,
  `.claude/settings.local.json`, `.claude/routing.local.json`, `.claude/sanctioned.local.txt` and a user's own `my-` skills, helpers and hooks.
- Net: a fresh clone ships **empty** (skeleton + demo only); when anyone uses it their content stays
  local, and `git push` shares only framework changes.

## KEEP / STRIP (copied from the live vault by the builder)

`professor-loop` stays out of public builds (the owner's decision of 3 November 2026, answer 3g; its
upgrade is set for v0.10.2, moved from v0.10.1 by his yes of 9 November 2026).

- **KEEP →** CLAUDE.md, MANUAL.md, `README.md`/`LICENSE.md` + `assets/` (from the vault root),
  `.claude/skills/**` — every publishable skill, including `export-template` (the maintainer's publish tool, with its `payload/`), except `professor-loop` while its standalone prerequisites are being prepared,
  the hooks `payload/shipped-hooks.txt` names, `.obsidian/{graph,app,core-plugins,appearance}.json`.
- **STRIP →** all `wiki/**`, `raw/**`, `assets/**` (bar the README images), `output/**`, `attic/**`,
  `wiki/user/**`, `CUSTOMISATION.md`, `CUSTOMISATION-definitions.md`, `CALENDAR.md`, `CALENDAR-done.md`, every other hook, the vault's own `.claude/settings.json`, `.claude/routing.local.json`, `.claude/sanctioned.local.txt`, any `my-*` skill, helper or hook, personal data, `.obsidian/workspace.json`/`plugins/`/`community-plugins.json`, `.claudian/`, `.git/`.

The exclusion removes a previous generated copy from build/push destinations and leaves the private source directory unchanged.

## Conventions the scaffold must preserve
- Every empty content dir keeps a `.gitkeep`.
- `raw/` lanes 1-articles…9-originals + archives + duplicates; `wiki/` type folders as above.
- The demo is the ONLY shipped content and lives in `examples/seed/` (never in `wiki/`/`raw/`).


## Push / pull round-trip (how repo and vault stay in sync)
The builder runs **one direction per invocation** (see SKILL.md):
- **push** (vault → repo): `copy_framework` (CLAUDE.md, MANUAL.md, publishable skills, the shipped hooks, `.obsidian`, seed) +
  `copy_packaging` (`README.md`/`LICENSE.md` + `assets/` from the vault root; setup.sh, `.claude/settings.json`,
  `.claude/core-paths`, `.github/` + git dotfiles from `payload/`) + `make_skeleton` + `apply_fixes`.
- **update** (a vault that is a clone of the release, with `--apply`): a git fast-forward to the newest commit of the
  branch it follows, git's own refusals standing; nothing is copied (SKILL.md, "Update (pull)").
- **pull** (a vault beside a clone: repo → vault, with `--apply`): repo framework → vault (CLAUDE.md, MANUAL.md,
  `README.md`/`LICENSE.md`+`assets/`, the shipped hooks, all skills — copied **per-name**, incl.
  `export-template` itself (replacing the running script is Unix-safe)); repo setup.sh/settings/git-dotfiles/seed → `payload/`,
  so the vault's own `.claude/settings.json` is never written.
- **Canonical sources:** `README.md`, `LICENSE.md` + `assets/` live at the **vault root**
  (visible, editable); the build machinery lives in `payload/`. Pull keeps both fresh so push never clobbers
  upstream edits.
- **Pull never writes** to `wiki/ raw/ output/` (and your own `assets/` media), never touches
  `.obsidian/{app,appearance,core-plugins}.json` (vault-specific), and pulls `.obsidian/graph.json` **only**
  with `--with-graph`.

## Graph exclusion
`.obsidian/app.json` `userIgnoreFilters` includes `examples/`, `template-export/`,
`output/`, `raw/`, `CLAUDE.md`, `MANUAL.md` so the demo + non-wiki files don't clutter the graph.

## The seed demo (purpose)
A 6-page AI/LLM-research mini-wiki (source → concept · entity · model · benchmark · map) so a first-time
cloner can `setup.sh --with-example`, see the colour-coded graph, run `/query`, and read a worked
`raw → wiki` compile. Deletable via `setup.sh --reset`. Safe general knowledge only.
