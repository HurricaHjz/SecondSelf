# Manual: using your LLM second brain

> **What is this.** Your AI-built **second brain**: drop in your sources and the agent compiles them into a structured, self-maintaining knowledge base that answers questions, creates deliverables, and acts as a cited reference. 
>
> **What this manual covers.** How to use it day to day: the capture → compile → ask → maintain loop, the everyday commands (`/ingest`, `/query`, `/output`), and the advanced options. You rarely edit the wiki by hand; you work through the agent.

## What's in here

| Folder | What it holds |
|--------|---------------|
| `raw/` | **Your sources** (the inbox). Drop files, clips, or links here in almost any format: PDF, Word, PowerPoint, Excel, Markdown and plain text, CSV, HTML and web pages (articles, blogs, GitHub repos and gists), images (PNG/JPG), audio (MP3/WAV), EPUB, and YouTube links. Once processed, the agent files each into a numbered subfolder (`1-articles` … `9-originals`, `archives`, `duplicates`). |
| `wiki/` | **The compiled brain:** `concepts/ entities/ tools/ models/ benchmarks/ sources/ syntheses/ experience/ developments/ maps/ user/`, plus `index.md` (the catalogue) and `log.md` (history). |
| `wiki/user/` | **About you** — profile, research, works. The agent reads this for personal context; you curate it. |
| `output/` | **Deliverables** the agent writes on request — reports, briefs, decks. Kept separate from the brain. The root holds one-off pieces; `reports/` collects every report for you to sort later; the other subfolders (`user-notes/`, `fundings/`, `conference/`) hold standing documents the agent keeps up to date as the underlying knowledge changes. |
| `assets/` | Images and reference attachments — diagrams, screenshots, and *special* PDFs you want to link to. Source PDFs to **ingest** go in `raw/`, not here. |
| `IDEAS.md` | **Your scratchpad** — a copy-ready **TODO prompt queue** plus ideas and a monitor lane of standing cautions, jotted freely. The agent ignores it unless you explicitly point it there: *"maintain IDEAS.md"* tidies and reconciles it, *"run TODO 2"* executes a queued prompt and updates its status. |
| `attic/` | **Your cold storage** — retired files kept "just in case", each listed in `attic/MANIFEST.md`. The agent may prepare an archive of a stale file and asks your yes before moving it; it opens the attic to read or restore only when you ask. Archived notes show **grey** in the graph. |
| `CUSTOMISATION.md` | **How your agent behaves** (vault root, seeded on first setup) — its name, output styles, task roles, and any standing preferences you add. Edit it, or just ask the agent. Definitions of the non-default styles and roles live next door in `CUSTOMISATION-definitions.md`, outside every session's always-on context; the Settings rule in `CUSTOMISATION.md` says when the agent reads them. |
| `CLAUDE.md` | The rule-book the agent follows (you don't normally touch it). It is part of the core, which `setup.sh` locks; see "Updating" below. |
| `.claude/skills/` | The commands: `ingest`, `gather`, `query`, `output`, `reflect`, `lint`, `deep-lint`, `attic`, `adopt`, `project`, `weekly-audit`, `suggest`, and `qmd-search` (plus `export-template` for framework updates, and `delegate`, which the agent reads itself rather than you calling it). |
| `.claude/agents/` | The subagent definitions `delegate` routes to: a builder that writes code and templates inside a named file list, a critic that argues against a plan, a verifier that checks claims against files, a compile lane, a memory lane, a planner, a writer for long prose, a gate judge that grades blind tests and a cross-session reflector. Each one is a small Markdown file naming what that lane may read and write. |

Every note in `wiki/` (except the navigational maps) also carries a **confidence level**, so you can see at a glance how far to trust it:

| Level           | What it means                                                                              |
| --------------- | ------------------------------------------------------------------------------------------ |
| `authoritative` | Checked by independent experts: peer-reviewed or published work, expert reviews and verified claims — the highest trust. |
| `high` | Written first-hand by the people who did the work, wherever it was posted — preprints, official documentation, a team's own account, a maker's plain facts about its product — or your own work by default. |
| `medium` | A knowledgeable second-hand account, however faithful, a maker's announcement that mixes its facts with its own praise, or a page grounded only in sources primary for something adjacent. |
| `low` | Weak grounding — an author no one can trace, an unsourced claim, another AI system's unchecked report, a third party's listing, or a seller's own praise; treat with care. |
| `very-low`      | Speculative or unverified material, flagged for caution.                                   |

The agent sets each level by judgement, starting from who wrote a source and how they know, never from where it was posted or what language it is in; it marks a level one step lower while a machine transcript, a machine translation or a conversion recorded as suspect stands unchecked against the original, and notes its reason on the page whenever it departs from the usual level.

## The loop

**Capture** (drop a file, clip, or URL into `raw/`) → **Compile** (`/ingest`) → **Ask** (`/query`) →
**Maintain** (`/lint`). Good answers get filed back, so the wiki compounds over time.

## Everyday commands

Type these to the agent, in the Claudian panel or Claude Code.

**`/ingest` — turn sources into wiki notes**
- `/ingest` — process everything new in `raw/`.
- `/ingest <file or https://…>` — a single file or web link; PDFs, documents, web pages, and YouTube are all handled. A platform link the capture chain cannot reach (an X post, a Reddit thread, a XiaoHongShu note) is reported with a ready, owner-gated option rather than improvised or silently skipped.
- `ingest this at research depth` — pin the thorough, academic treatment for an important paper: exact figures, verbatim quotes, methods, and limitations. Left unpinned, the agent decides per source after reading and shows you what it chose.
- Plain language works too: *"add this to my wiki."*
- After each ingest, the agent lists the new notes with their **confidence level**, so you can check the trust ratings and ask to re-grade any.

**`/query` — ask your knowledge base**
- `/query <question>` — for example, *"/query what do my notes say about calibration?"*
- Answers come **from your wiki**, with clickable `[[links]]` to the pages used, and can be filed back when worth keeping.

**`/reflect` — keep what a session taught you**
- `/reflect` — at the end of a working session, the agent sweeps the conversation for research insight, method lessons and any faults it found, then shows you a table of what it proposes to record and where. Nothing is written until you approve it, with one exception: a lesson about how a feature should decide goes straight onto that feature's experience page once an independent checker has failed to refute it, listed for you to undo. A critic subagent tries to knock down each proposal before you see it (`--no-critic` skips), and the report names how much of the session's record it could still see. After a development run (an IDEAS todo, a framework change or a delegated job) the proposal table also carries the run's cost at each boundary and a short waste list, each entry naming where its fix should go.
- `/reflect --cross <session>` — the same sweep run over another, usually finished, session's transcript by a separate read-only agent. That agent is an independent witness: it can catch what the original session never noticed about itself. It only proposes, and you approve every write line by line. The one exception is a session's own closing pass run with `--yes`, where the lead session applies checked experience lessons and lists them for your undo. After a large multi-agent job the agent may offer one such pass itself, once, with the cost stated; it runs only on your yes.
- It only ever runs when you ask. The agent already files findings as it works, and that carries on unchanged; this is your own trigger for the times it didn't.
- It tells you how far back it can still see, since a long session may have dropped its earliest turns, and it never claims to have swept the whole thing.
- Add `--yes` to let it write without waiting. It still shows you everything it wrote, and it may only add new pages or append to existing ones inside `wiki/`, or make checked lesson edits on an existing experience page — never your own pages in `wiki/user/`, your own entries on an experience page, or the rule-book. A hands-off close leaves experience edits for your morning.

**`/output` — produce a polished deliverable**
- `/output <what you want>` — for example, *"/output a one-page brief on X for a non-expert."*
- Writes a grounded, **cited** document into `output/`; it cites what it draws on and does not invent facts.

## Rules of thumb

- **You curate and ask; the agent writes the wiki.** Change notes through the agent rather than by hand.
- Keep anything **about you** — bio, research, works — in `wiki/user/`, starting with `About Me`.
- `raw/` is your source of truth: the agent files and sorts your sources but never rewrites them.
- Keep Obsidian open, and explore through the **graph view** and **backlinks**.
- The agent runs on API credits or plan quota, so it is worth being deliberate about very large jobs.

---

## Skills, tools and plugins: three use levels

Everything the agent can reach for beyond its own workflows sits in one register, `wiki/developments/capability-register.md`, with a use level per entry. An `auto` add-on is used whenever a task fits, such as the chart and figure skills inside a deliverable. A `propose-first` add-on is offered once, in a line, and runs only when you say yes; typing its slash command, naming it, or granting it in a hands-off pre-flight counts as yes. A `by-name` add-on never appears in any listing and runs only when you invoke it. The academic writing suite (ARS) and the experiment agent are propose-first; reflect and the attic are by-name.

To add something new, say "adopt <url>" or type `/adopt <url>`; `/adopt --assess-only <url>` stops after the report, and `/adopt --retire <name>` reverses an adoption. The agent fingerprints the repository, recommends a level and says what the add-on would mean for the system, then waits for your approval before installing, recording and routing it. To change a level, say so, and the register row and the wrapper change together.

**Optional helpers and tools.** The everyday loop needs none of these.
- **The Codex CLI.** `codex-lane.py` runs GPT helper agents through an installed, authenticated Codex CLI. It accepts the efforts `low`, `medium`, `high`, `xhigh`, `max` and `ultra`, but your CLI and plan decide which of them work, so an `ultra` round runs only where both support it. Without the Codex CLI the GPT helpers are simply off: `codex-lane.py` stops with a `PROBE FAILED` line naming the missing executable, a reviewing seat stays on the Claude side in a fresh context, and its report says the review was by the same model family.
- **Tesseract, with `pdftoppm` from Poppler.** A PDF that holds only page images has no text to convert. Run `pdftoppm -r 300` on it, then `tesseract --psm 1` on each page, and drop the result in `raw/`; or let the agent transcribe the file itself with `/ingest --agent-convert`, which costs more tokens.
- **The browser route in `/gather`.** For a page that blocks ordinary capture, `/gather` tries the open-access resolver first. In an attended session it can then use the Chrome connector with a separate Chrome profile signed in to a throwaway Google account, so your own profiles are never used. A headless run never takes this route and lists the page for you to fetch by hand.
- **Anything else.** A skill or tool you want comes in through `/adopt`, as above.

## Advanced

**Deeper `/ingest` options**
- `/ingest --verbatim <url>` — save the **exact** page rather than a cleaned version, for precise quoting.
- `/ingest --no-dedup` — skip the automatic "already ingested?" check when loading material you know is new.
- `/ingest --agent-convert <file>` — the agent itself transcribes a PDF or image to Markdown instead of the automatic converter, for precision on complex layouts (heavier on tokens, so opt-in). If an automatic conversion comes back empty or garbled, the agent offers this route with a cost estimate before anything else.
- `/ingest --depth concise,standard` — narrow the depths the agent may choose from for this run. It may use all three unless you narrow or pin.
- Capture is automatic by type: web pages via `defuddle`, Markdown and text via `curl`, audio/video/binary via MarkItDown, with **Jina Reader** as a fallback for awkward or JavaScript-heavy pages.

**`/gather` — capture from the web: links, or a whole topic**
- `/gather <url> [url2 …]` — fetches the page(s) **and the relevant sources they cite** (papers, repos, docs) into `raw/`, then hands off to `/ingest`. It **previews what it will fetch and asks first**, and caps how much it pulls. On documentation sites it also checks the site's sitemap, so the preview shows the host's whole inventory rather than just the pages the seed happens to link.
- `/gather --search "<topic>"` — no links needed: the agent web-searches the topic, triages the hits, and shows you a **dated shortlist to approve** before anything is fetched. If the topic is too vague to plan from, it asks up to three sharp questions first; each approval screen also shows which sub-questions of your topic are covered and which are still open. Add `--rounds 2` to let it search again for whatever the first haul left uncovered — later rounds never re-run earlier queries or re-present rows you already passed over as new. This is the vault's own deep-research route — after `/ingest`, ask `/query` or `/output` for the cited report. When a topic needs Chinese or community coverage, search mode can also query the enabled platform channels (Bilibili, V2EX, known RSS feeds) alongside web search, declared at the approval screen.
- With a bigger budget (say `--max-pages 40`) the menu stays small but every further ranked candidate is listed one per line, and you capture by **rule** — *"top 30 by relevance"*, with row-level tweaks if you like. A bare "approve" always means just the menu, and the search funnel (queries, pool, date checks) scales with the budget and is printed at the gate.
- Conservative by default (search mode captures just the approved results; link mode follows one citation hop; up to ten pages). Override with `--expand 2` (citation hops), `--focus "X"` (only material relevant to X), `--max-pages 50`, `--shortlist 10` (detailed rows at the gate), `--queries 8` (searches per round), `--same-domain`, `--include a,b` / `--exclude c,d`, `--yes` (skip the preview), or `--ingest` (compile afterwards) — or simply describe it: *"gather these, two hops, only the papers."*
- Runs keep themselves honest (v3.1): every capture goes through one script that enforces the caps, raw immutability and provenance; a per-run ledger tracks captures and your drops across rounds on bigger runs; and the gate adds the agent's advice ("~N worth capturing") — rows beyond your budget are marked, and capturing them just means raising the cap ("raise to 15, take top 15").
- The agent may also **suggest** a gather when a `/query` or `/output` run hits a real knowledge gap: a short brief (why · what · the exact command · cost) after its answer. It only ever runs on your explicit yes — say nothing and it reminds you once, then drops it; say no and it stays dropped for the session.

**`/lint` — health-check the wiki**
- Finds broken links, orphans, unindexed pages, and conflicts, checks that no third-party installer has slipped an unsanctioned skill into the agent's skill folders, and checks that no shipped skill or agent file links to a wiki page that never ships (such a link would be dead in the published framework). A normal `/ingest` self-cleans, so run this after hand-editing, after syncing between machines, or for a periodic review.

**`/deep-lint` — periodic deep maintenance**
- A heavier pass (roughly monthly, or when flags pile up) that does everything `/lint` does and also reconciles the staleness flags queries leave behind, audits **confidence** on changed and sampled pages rather than re-reading the whole vault, re-checks a capped, priority-ordered set of sources against their **live online versions**, keeps the external capture tools current — a trustworthy newer release (tagged, past a cooling-off, same publisher, acceptance-tested) upgrades automatically with each bump reported to you, while anything failing that bar is only reported — and reviews the IDEAS Monitor lane, updating the wiki where things changed. Token-bounded by design, and every cap it applies is stated in its report.

**The attic — retire files without deleting them**
- Say *"archive [[X]] to the attic"* (or `/attic archive X`) and the agent runs the full routine: it first folds anything still useful from the file into your live notes, shows you the list for approval, then moves the file into `attic/`, records what, where from and why in `attic/MANIFEST.md`, unindexes it, tidies every link, and verifies nothing still points in; *"restore X from the attic"* (`/attic restore X`) reverses it; *"what's in my attic?"* reads the manifest back to you.
- Archived notes stay in the graph in **grey**, so retired material remains visible without cluttering your live knowledge. The agent may find a stale note itself and prepare its archive, but it moves nothing until you say yes, and it opens the attic to read or restore only when you ask. The monthly `/deep-lint` prepares archive candidates (stale or superseded notes) the same way and never moves anything itself, and the routine `/lint` guards the boundary by flagging any live note that still links into the attic.

**Your working repositories — Overleaf and code, managed from the vault**
- Say *"link this Overleaf project"* (or `/project link <url>`) and the agent clones it into its own store outside the vault, shows you what it will do first, and puts one registry row in `wiki/tools/Agent Project Store.md` plus a commit-pinned snapshot of the document into `raw/`, ingested like any source, so the wiki knows the project without holding its files. From then on *"open my research outline"*, *"rewrite section 3, commit, push"* work in that clone; commits are yours, pushes happen only when you say push, and an Overleaf push lands in the project at once.
- A repository you already keep elsewhere (your code) is registered where it is (`/project link --path <dir>`), never copied. The clone's files are not visible in Obsidian, which is the point: nothing in a repository can enter the second brain except the snapshots you ask for.
- A code repository can use the vault as read-only context. Keep the repository's working files separate, grant only the needed vault paths, and deny vault writes from that repository. The `project` skill describes repository management; its registry is `wiki/tools/Agent Project Store.md`.

**qmd — optional local semantic search (for large or fast-growing vaults)**
> Worth adding when your wiki is **already large enough that `index.md` is hard to scan**, *or* when you **expect it to grow very large**. In that case adopt it **early**: the index then builds up incrementally (one quick re-embed per note as you go) instead of as one slow bulk embed later, and you get search-by-meaning the whole way up.
- Once enabled, the agent **searches by meaning** (not just exact keywords) — but **only when it's actually needed**: when the normal `index.md` + keyword search comes up short for a question. It is **not** run on every search, and you don't have to ask for it — the agent decides when it genuinely helps (you *can* force it with `/qmd-search <query>`). Whenever qmd is off or absent, search silently falls back to the normal path.
- It stays **dormant and cost-free** until you install and enable it, runs **only as quick one-shot calls** (nothing is ever left running in the background), and the agent keeps its index fresh automatically as you add or change notes. Ask the agent to set it up when you're ready.

**Experience pages — rules and lessons read at the moment they matter**
- A feature that keeps making the same kind of decision can hold one short page in `wiki/experience/`: your rules for that decision and what earlier runs taught, read whole at the step where the feature decides and at no other time, so it costs nothing while the feature is unused. A page is created at its first entry, together with the pointer at the step that reads it. `/reflect` delivers the lessons: each one is checked by an independent agent before it steers anything, and each change is listed for you to undo. A new page, and any change to your own entries, comes to you first. `/lint` checks that each page and its pointer still meet, `/deep-lint` lists growth and stale measures monthly, and `recall-probe.py` shows that a task reads the page it needs and no other.

**Back up your vault — private repo**

- Your *entire* vault — notes and all — can back up to a **private** Git repository of your own, giving you version history and a copy off your machine. Create the repository, then run `bash setup.sh --backup <its address>`. It keeps a separate git folder outside your vault, adds your layer there (your notes are ignored by the clone, so it adds them by force) and pushes to your repository. It never commits to the clone. Run the same command whenever you want a fresh backup.

- This is **separate from sharing the framework**: the backup keeps *everything in a private repo*; the framework is published *stripped of your notes to a public repo*. Keep the two remotes distinct.
- Do not point a git plugin such as **Obsidian Git**, or a commit of your own, at the clone itself. A commit made in the clone is a commit the release lacks, and an update refuses a copy that has one (see "Updating").

**`/export-template` — sync the framework with its repo**
> Most users need this only to **update**: `--pull` brings a newer framework version into your vault (see "Updating" below). `--push` publishes framework changes and is the maintainer's path. You never need either to capture sources or use your wiki.
- It packages the framework with **none** of your notes and syncs it with the public GitHub repo, one direction at a time. It always previews and asks before writing anything.
- A plain `git push` only syncs a single repository with its own remote. This skill instead carries framework changes between two separate repositories, your private vault and the public framework repo, and assembles the shareable demo. Your knowledge therefore stays in its own private, independently backed-up vault, while the framework itself stays shareable through the public repo.
- Updating a separate vault from a version without `CITATION.cff` takes one `--pull --apply`, as any update does. The file reaches your vault root at your next pull; until then a `--push` keeps the repository's copy, and a fresh standalone build stops and names that pull as the fix.

**Modes and pacing**
- **Depth**: `concise` · `standard` · `research`. When ingesting, the agent picks a depth for each source **after reading it** and tells you which it chose and why, in the same report that lists confidence — so you can re-grade either with one word. Narrow what it may use with `/ingest --depth concise,standard`, or pin one for the whole run with `--research`, `--standard` or `--concise`. Asking a question is different: there `research` is opt-in or the agent asks first. All modes stay token-efficient.
- **Pacing** (how many at once): `auto` (default) · one at a time · in batches.

**Customisation — make the agent yours**
- Your agent's **name**, default **output style**, and **interaction preferences** live in `CUSTOMISATION.md`, seeded on first setup. Edit it — or just ask the agent — to change how it addresses you and how it writes. The styles and roles you are *not* currently using sit in `CUSTOMISATION-definitions.md`; the Settings rule in `CUSTOMISATION.md` says when the agent reads that file, and "set default style/role to X" moves the definition into the always-on file for you.
- Those are only starter examples: the file is **open-ended**. Add any standing preference you want every session to honour — citation habits, formatting rules, tutoring style, anything — as new bullets or sections.
- **Deliverable defaults** (optional): a `## Deliverable defaults` section sets standing formats for `/output` documents — citation style, deck format, and so on. Leave it empty and the agent chooses per deliverable; whatever you write in the instruction always wins.
- **Roles**: say *"act as tutor"* (or any role you define under `## Roles`) to switch the agent's task context for the conversation; every reply carries the active `role · style` status line (opening its first text or its final answer), a claim the reply has to satisfy rather than a decoration. Roles shape how the agent works on your task and add to your global preferences; they never change your output style — how much you read stays your choice alone.
- **Throttle**: subagent model and effort tiers follow one knob, `throttle` in `CUSTOMISATION.md` (`auto · top · default · cheap · fast · cheap-fast`). Say *"set throttle to fast"* and the agent runs `throttle.py set fast`, which rewrites the Settings line and every subagent definition; the change registers at your next message and, on a machine with the anchor hook installed, the status anchor shows it. `auto`, the default from 2026-09-08, picks model and effort per task within the class range. The row anchor in `routing.json` is the reference (which model and effort serve which helper seat is set in that table, never restated here), and every departure is recorded with its reason on the lane-open event. `default`, `top`, `cheap`, `fast` and `cheap-fast` are overrides you set by hand and they are never re-resolved: `default` pins the anchors with no reason required, `top` the ceilings, and `cheap`, `fast` and `cheap-fast` name a budget or time constraint; `top` and `cheap` resolve every model through `preset_model` in `routing.json`. Which steps a skill may route to lanes is fixed by its parity gates and applies under the `multi` regime; in `single` the agent does the step itself unless it has a named reason for a lane.
- **Long sessions**: every turn the agent sees its own context size. In an attended session it starts new work only when that work fits, and states the sum first: the context now, the work's estimate and a 50,000-token close-out reserve must stay under 950,000 tokens; by 900,000 tokens it begins the close-out, with a hand-off document (`~/.llm-wiki/handoffs/`) and a ready prompt for a fresh session. Another window or a band setting keeps the 60 % and 80 % bands; a hands-off run hands over only when its gate refuses the next item, because the item would not fit, with the 80 % mark deciding only where no estimate exists; and if the harness compacts the conversation, a checkpoint written just before is re-read afterwards. These are hooks in `.claude/hooks/`, on by default; the hands-off gate belongs to the opt-in `hands-off` kit (see "Hands-off long runs"). If your context window is not 1,000,000 tokens, set the environment variable `AIMYTH_CONTEXT_WINDOW` to its size in tokens.
- **Output styles** shape conversation only, one ladder from most to least: `detailed` (everything the prompt makes relevant) · `balanced` (the default — the natural answer) · `brief` (the answer plus what you need to act on it, in flowing prose) · `shortest` (the answer and nothing around it). Say *"switch to brief"* for one session, or *"make shortest my default"* to keep it. You can add your own styles too. A scoped wish such as *"more concise for the next 3 replies"* shows as `customised` in the status line while it lasts, then the style reverts on its own.
- Choosing a style **never** changes the wiki itself — your notes, their confidence ratings, and the agent's status reports stay exactly the same.

**Subagent lanes — the helpers the agent spawns**
- The agent does the work itself by default. It calls a helper agent, a *lane*, only when there is a named reason: a check that has to be independent of whoever did the work, breadth it cannot hold in one context, isolation from a long conversation, or a job longer than it can afford. The reason is recorded before the lane starts, so you can see afterwards why each one was called.
- A lane is a separate, short-lived session that knows nothing about your vault. It runs from a **lane home**, a small folder outside the vault (`~/.llm-wiki/lane-home/`) holding the lane's own settings, a shell guard and a few extracts of the rules. `setup.sh` builds it for you by running `python3 .claude/skills/delegate/lane.py init`, and re-running setup refreshes it. Nothing in it is your knowledge, and it is never published with the framework.
- Each lane sees only its brief and the folders granted for that one call. Anything else it reaches for is refused, and the agent treats the refusal as a sign to brief it again rather than as a result.
- **`delegation`** in `CUSTOMISATION.md` sets how much of this you get. `auto`, the default, leaves the choice to the agent: for each run it decides between `single` (the work stays with the main agent) and `multi` (a skill may also route its own steps to lanes), weighing the size of the run, how full its context is, the throttle and breadth settings and whether you are present, and it records the reason. A run it chose to run `multi` shows as `auto→multi` in the fourth entry of the status line each reply opens with, and the first lane of such a run waits for your go. Take the choice away by setting `single` or `multi` yourself: say *"switch to multi"* for one conversation, *"do this multi"* for one run, or *"set default delegation to multi"* to keep it.
- Lane reports and the record of every spawn are written outside the vault as well, under `~/.llm-wiki/`, so your notes stay only your notes.
- Runs that touch the wiki now log a cost line beside their entry: what the session billed at list prices, split between the main agent and its lanes, with the number of lanes and the reasons they were called. It is arithmetic over the transcripts rather than a charge from your plan, so read it as a comparison between runs.

**More `/query` examples**
- `Compare [[A]] and [[B]] and save a table to syntheses.`
- `Where are the gaps in what I know about <X>? What should I read next?`
- `Turn [[topic]] into a Marp slide deck.`
- `Do a research-mode synthesis of <X> with exact ƒfigures and citations.`

---

### Hands-off long runs

When you want a long task done while you are away, say so. The agent first shows a short table: the permissions it needs and might need, the conditions under which it will stop on its own, the expected spend, and what happens if its context window fills. One confirming message starts the run. It ends with a reflection and a hand-off document you can resume from in a fresh session. A hands-off run relies on three hooks in `.claude/hooks/`: the context line is on in every copy, and the other two, the gate and the head fence, are the opt-in `hands-off` kit. Turn the kit on once with `bash setup.sh --enable hands-off`; `bash setup.sh --disable hands-off` turns it off. Without the kit the run is refused at its second gate and stops after one hand-off, and the pre-flight table says so and names the command. A related kit, `ingest-check`, adds a warning at the end of a turn when an ingest was left open and stale: `bash setup.sh --enable ingest-check`.

**Filling in web forms in auto mode.** A template of a rule that lets the agent fill in a web form you give it, in auto mode, on five conditions, sits at `.claude/skills/export-template/payload/automode-form-entry.template.json`. The rule changes a safety check on the agent's own actions, so you add it yourself and `setup.sh` never does. Copy `~/.claude/settings.json` somewhere safe. If that file already holds an `autoMode` section, compare the two first. Add the template's `autoMode` section to the file, keeping `"$defaults"` as the first line of each list, then replace `{{WHO_YOU_ARE}}`, `{{YOUR_SITES}}` and `{{YOUR_SIGN_IN_PAGES}}` with your own details. To undo it, run `claude auto-mode reset`.

Starting one is a single exchange. Say what you want done and that you will be away; the agent replies with the pre-flight table — the permissions it holds and the ones it may need, the gates it will decide on your behalf with the default it will apply to each, the conditions under which it will stop by itself, the expected spend phase by phase, the reset time of your usage window against the expected finish, and what it will do as its own context fills. Read it once; one confirming message is the whole authorisation, and it covers exactly those grants. Anything outside them stops the run and waits for you with a report.

What happens as the agent's context window fills depends on whether you are there. In an attended session the rule only advises: before new work the agent states whether it fits (the context now, the work's estimate and a 50,000-token close-out reserve, under a 950,000-token belt), starts nothing new without an estimate, and by 900,000 tokens begins the close-out, which writes the hand-off document and gives the prompt for a fresh session; on another window or with a band setting, the 60 % and 80 % warnings still apply. On a hands-off run the limit is hard, and it is judged item by item: when the next item would not fit (the context now, the item's estimated cost and the hand-off's allowance), its gate refuses that item, with the 80 % mark deciding only where no estimate exists. The agent then opens nothing new, waits for the helpers still running, writes the hand-off, ends its own session and starts a successor that picks the work up from the hand-off's resume prompt, so the conversation is never compacted mid-task and the cost of the change-over is one reload of the standing context. The run closes once, in its last head. At 90 % a hook stops everything except the close-out: writing the hand-off, starting that successor, and the two bookkeeping records (the boundary and the findings ledger). That is the emergency exit, and it costs at most the item in flight.

Two more things run under the hood on a hands-off run. The agent's shell is fenced: every command is checked against the grants you confirmed in the pre-flight, a command outside them is refused and logged rather than worked around, and the status line at the top of each reply carries a fifth entry, `· hands-off`, while the fence is armed. And the hand-off is written as a pack for the next step, never as a history: what the next item needs, the decisions it rests on and the gate it must pass, so a successor orients from it in a few thousand tokens. The run also has a live console, a read-only board of its items, helpers and timeline (`handsoff.py watch --run <run>`): at a launch, a successor or a resume the run opens a Terminal window on it unless one is already open, or unless the pre-flight says `viewer: none`. If you are working alongside the agent yourself, `handsoff.py watch --session <id>` shows that session's background jobs, such as test suites and helpers, with their progress, and the status line carries a `· jobs` entry for as long as any of them run. The console window a hands-off launch opens also opens for any attended run that spawns helper agents, whenever none is open for that run, so every multi-agent run is watched; `--viewer none` on the spawn or `AIMYTH_VIEWER=none` keeps it closed.

What you read in the morning is that hand-off document, in `~/.llm-wiki/handoffs/` outside the vault, one file per session. It opens with a morning report — what shipped, what waits on a decision of yours, what changed in the registers, what it spent, what the run saved, every warning it raised, and the prompt to paste into a fresh session to carry on — and the sections below it hold the detail: the item in flight, the grants the run held, a ledger of every finding and warning with what was done about it, the trace of each phase boundary, and the plan of record. It is rewritten at every boundary, so it is current even if the run stopped in the night.

The agent runs under one account, so a usage limit stops it and its helpers together. That is expected, not avoided. The process that started a hands-off agent stays beside it as a supervisor. By default (since 6 September 2026) a limit ends the run there: the supervisor records the stop and stands down, the hand-off is the recovery, and once the window resets you resume it yourself with `handsoff.py resume-head --run <run>` (the same session, where it left off) or `handsoff.py successor --run <run>` (a fresh agent from the hand-off). If you would rather the run carried on across the reset without you, write `limit-off` in the pre-flight: the run then opens with `--on-limit resume`, the supervisor reads the reset time from the stop message, sleeps until then, and resumes the same session, provided its context is still under 60 % of the window; above that it starts a successor from the hand-off. A helper stopped by the limit is resumed from its own transcript in the same way, and you lose one cold re-read of the context and nothing else. In that mode the status line reads `hands-off-limit-off`, and the supervisor stands down of its own accord if you continue the session by hand in the meantime, or if you run `handsoff.py supervise --stop --run <run>`. If the stop message names no reset time, the run ends there and the hand-off is the recovery. The agent never probes your account to learn when a limit lifts, never tries a second login, and never adjusts to a limit beyond waiting for the reset. If you are working with the agent yourself when a limit stops it, say "continue" once the window resets and it carries on. A machine sleep or restart ends the supervisor too. The hand-off is then the recovery, as before.

Two rules govern what happens when something goes wrong while you are away. Nearly every trigger — spend past the envelope, a band crossing, a helper that fails, stalls or is refused a path, a red test suite, a reviewer's "not ready", a helper's usage limit — is warn-and-continue: the agent records it in the ledger with what it did about it and keeps going, and you read the list in the morning. The rest are holds: work whose review rounds stop making progress (CUSTOMISATION.md's rules on rounds and stopped designs) when those rules require it to wait for you, a phase running away with the budget, and any finding that would reverse a decision you made yourself are parked with their state on disk for you to rule on, while a refusal or a limit on the main agent itself, or any write or fetch outside the grants you confirmed, stops the run outright.

## Updating

An update moves the core to a newer release and never touches your layer: `wiki/`, `raw/`, `output/`, `CUSTOMISATION.md`, your calendar, your own skills (`my-` names), `.claude/settings.local.json`, `.claude/routing.local.json` and `.claude/sanctioned.local.txt`. The first line of each new session says where you stand, and a bug report carries it (`python3 .claude/hooks/core-check.py --report` prints it again):

- `core: v0.10.0, unchanged (N files)`: the core is exactly that release.
- `core: v0.10.0, N file(s) differ from the release: …`: some core files differ, by an edit of yours after `bash setup.sh --unlock` or by something else; the line names up to five of them.
- `core: not checked (…)`: this copy has no git record of a release, so nothing was compared; "A copy that is not a clone" below says how to fix that. A vault kept apart from its clone (see below) runs no check and prints no line.

**The usual update: your vault is the clone.** Preview first, then apply:

```bash
bash .claude/skills/export-template/export_template.sh --pull .
bash .claude/skills/export-template/export_template.sh --pull . --apply
```

The preview fetches from the repository and lists the files that would change; it writes no working file. Applying is plain git: `git merge --ff-only --no-overwrite-ignore` onto the newest commit of the branch your copy follows, then `bash setup.sh --lock`, which locks the core again. Nothing else runs, so no step sets a file of yours aside, replaces a core file you changed or saves the throttle's lines, and where git refuses, its refusal stands. Your next session's first line shows the result. A plain `git pull` also works on a clean copy, and the hook that `bash setup.sh` installs locks the core again afterwards, but it silently replaces a file of yours that git ignores at a path the release adds, which the update above refuses.

**If your throttle is not `auto`.** The throttle (`throttle` in `CUSTOMISATION.md`) rewrites the `model:` and `effort:` lines of the helper definitions, so git can see those files as changed and refuse a release that changes one of them. Note your value with `python3 .claude/skills/delegate/throttle.py show`, then set it back to `auto`, update, run setup and set it again:

```bash
python3 .claude/skills/delegate/throttle.py set auto
bash .claude/skills/export-template/export_template.sh --pull . --apply
bash setup.sh
python3 .claude/skills/delegate/throttle.py set <your value>
```

A `classes.<name>` override in `.claude/routing.local.json` that changes a helper's model or effort has the same effect, even at `auto`. Move that file out of `.claude/` before these lines, and put it back before the last one.

**When git refuses.** Git checks the release against your copy before it writes, so here your files stay as they were and its lines name the ones in the way. The update then exits with code 1 and locks the core again. Its message says that working files may have changed, because it cannot tell a refusal from a failure partway (below); git's lines show which it was.

- **A file you changed that the release also changes**, in the core or not (the README and the `examples/` folder ship but are not core). Save a copy, run `git checkout -- <file>`, update again, and re-apply your change by hand to the new file. A change to a file the release leaves alone does not stop the update and stays as it is: a core file then stays changed, locked, and the session line names it. A shipped file you deleted stays deleted until a release changes it, and then it comes back.
- **Your copy has commits the release lacks** (a fork, or a backup committed in the clone). Git says it cannot fast-forward. Merge by hand: `git fetch --tags`, then `git merge <tag>`. Do not commit backups in the clone; use `bash setup.sh --backup <address>` (see "Back up your vault" above).
- **A file of yours sits at a path the release adds**, ignored by git or not. Move it and update again. A skill of your own named `my-<name>` never clashes, since no release uses that prefix.
- **The fetch fails.** Nothing has changed; try again.

**If the update fails partway**, for example on a full disk or at a folder git cannot write to, your copy stays on the old commit with some working files already changed, and nothing puts them back for you. Running the update again is then refused, and git names every file in the way. Fix the cause. Save any change of your own among those files, restore each changed one with `git checkout -- <file>`, move each new one out of the folder, and update again.

**Settings.** A settings file of your own belongs in `.claude/settings.local.json`; `.claude/settings.json` is core. If an approval you grant with "always allow" lands in `.claude/settings.json`, the check ignores its `permissions.allow` list and the entry stays until a release changes that file. Git then refuses as for any file you changed: note your entries, run `git checkout -- .claude/settings.json`, update, and add them to `.claude/settings.local.json`.

**Obsidian's own settings.** Setup marks `.obsidian/app.json`, `appearance.json`, `core-plugins.json` and `graph.json` as unchanged for git (`skip-worktree`), so that Obsidian rewriting them does not show as a change. The update lifts the marks for the merge and sets them again, whichever way it went. If one of the four changed on your machine and the release changes it too, git refuses and names it; a plain `git pull` refuses whenever a release changes one of the four. In either case run `git update-index --no-skip-worktree <file>`, save your copy, run `git checkout -- <file>`, update, then run `bash setup.sh`, which sets the mark again. `git checkout` alone fails while the mark is on.

**The first update, from v0.9.7.** That version's export script has no update for a vault that is its own clone, so the first update is plain git, followed by `bash setup.sh`. If your throttle is anything but `auto`, git can refuse, because the throttle has rewritten helper definitions that the release also changes. Note your value first with `python3 .claude/skills/delegate/throttle.py show`, then:

```bash
python3 .claude/skills/delegate/throttle.py set auto
git fetch --tags
git merge --ff-only --no-overwrite-ignore <newest release tag>
bash setup.sh
python3 .claude/skills/delegate/throttle.py set <your value>
```

`git tag -l 'v*'` lists the tags. If git still names files, they are core files you changed, or files of yours at a path the release adds, such as a `.claude/settings.json` of your own, whose lines belong in `.claude/settings.local.json`. For a core file you changed, save a copy, run `git checkout -- <file>`, merge again, and re-apply your change to the new file. After this one update, the usual update above takes over.

**A copy that is not a clone.** A ZIP download, or a copy made from the repository's "Use this template" button, has no git record of a release, so it prints `core: not checked`. Five commands turn it into a clone without changing a file. Run them inside the folder, with the tag of your release in place of `<tag>` (a ZIP's `CITATION.cff` gives the version, so the tag is `v` and then that number):

```bash
git init -b main
git remote add origin https://github.com/HurricaHjz/SecondSelf.git
git fetch --tags origin
git reset --mixed <tag>
git branch --set-upstream-to=origin/main
```

If the folder already has a repository of your own, as a template copy does, name the remote `upstream` in the second, third and fifth commands (the fifth then reads `git branch --set-upstream-to=upstream/main`). Then run `bash setup.sh` to lock the core; `git status` shows only the changes you made yourself.

**A vault kept apart from its clone.** If you keep a clone of the repository beside your vault, `--pull <path to the clone> --apply` still copies the release into the vault as before. It lists the files a release drops and does not remove them, no check runs, and a vault that is itself a clone of the release is refused, since a copying pull would leave some of its files at the old version.

**Lock and unlock.** `bash setup.sh --lock` locks the core's files again and `bash setup.sh --unlock` lifts the lock, so that a person can edit the core; the session line then shows the change. The lock removes write permission only, and never from a folder. The agent itself is not allowed to edit a core file in a copy of this kind, with or without the lock.

## Graph view (colours)

The graph is **colour-coded by node type**, so the shape of your knowledge reads at a glance. Reopen the graph view after any setup change to load new colours. **A fresh vault's graph is empty** until you `/ingest` your first source (or load the demo with `bash setup.sh --with-example`). The colours appear as soon as there are notes to colour, and `setup.sh` or your first ingest applies the palette automatically. If the colours ever disappear later (Obsidian can rewrite its graph config), just ask the agent to restore your graph colours.

| Colour         | Node type       | What it is                                     |
| -------------- | --------------- | ---------------------------------------------- |
| ⚪ White        | `index` · `log` | the registry hubs that anchor the graph        |
| 🟡 Gold        | Maps            | navigational hubs (Maps of Content)            |
| 🔵 Blue        | Concepts        | abstractions — methods, theories, principles   |
| 🟢 Green       | Entities        | people & organisations                         |
| 🟠 Orange      | Tools           | software, apps, plugins, skills, services      |
| 🟦 Oxford blue | User            | **about you** — profile, research, works       |
| 🔴 Red         | Models          | LLMs (Qwen, GPT, …)                            |
| 🟣 Purple      | Benchmarks      | evaluation datasets (AIME, GSM8K, …)           |
| ⚫ Charcoal     | Sources         | one summary per raw source (the bulk of nodes) |
| 🩷 Pink        | Syntheses       | knowledge the agent wrote itself, from a query, a reflect run, or its own reading |
| 🟤 Brown       | Developments    | this vault's own self-upgrade docs (design · plans · rollouts) |
| 🩶 Grey        | Attic           | retired files kept "just in case" (cold storage) |

New nodes colour themselves: each colour keys off the **type folder** (`wiki/models/`, …), so anything the agent files there is coloured automatically, with no manual tagging.

---
*This manual is stable. It changes only when the system's setup changes, not on every ingest or query.*
