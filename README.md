# Second Yourself

Pre-release: the design changes often until v1.0. Forks are welcome; pull updates often.

**Second yourself. One agent that remembers you, with many hands to act for you.**

> *Tony Stark never had to reintroduce himself to Jarvis. Jarvis thought with him, acted for him, and never forgot.*

We believe true intelligence comes from the same composition. A foundation model gives it reason. A multi-agent harness gives it hands. A well-structured knowledge base gives it memory. Second Yourself is built where the three meet.

![Three parts joining into one agent that works for a person: a foundation model that reasons, a team of agents that acts and checks its own work, and a knowledge base of linked notes kept on the user's machine](assets/three-parts.png)

Today Second Yourself runs in Claude Code or the Claudian plugin inside Obsidian, with GPT models as helper agents through the Codex CLI and a wiki of plain Markdown on your own machine.

A second brain stores what you know. A second self knows it with you and acts on it.

What you build is up to you:

* **A second you**, the goal this project is built towards: an agent that can act for you rather than only answer, from a brief in your voice to an elderly parent's medication and appointments.
* **A research assistant**, what ships today: drop in papers and articles, ask questions, and get answers cited from your own library.
* **A shared brain for many agents**, which already runs: one wiki that a team of agents works from.

## The foundation model

Reasoning comes from whichever frontier model you plug in. Today Claude models coordinate the work. From release v0.9.6, a launcher with its own test script runs the GPT helper agents. Models are replaced every year. The other two parts are yours, and they compound.

## The multi-agent harness

You speak to one agent, and it briefs helper agents under a written contract. Each helper may write only the files it is given. Long jobs run unattended for hours.

Independent critic and verifier agents check the work. A check that reports nothing must first show that it can catch a planted case, so a silent failure is not read as a clean result.

The harness is this repository, with its rules, 13 skills under `.claude/skills/`, 9 agent definitions under `.claude/agents/` and 34 test scripts. Every commit on the main branch is a version, from v0.1 on 24 June 2026, and tagged releases start at v0.9.6.

## The knowledge base

You drop sources into your Obsidian vault, and the agent compiles them into a wiki of linked notes that it maintains on its own. The notes are yours to open, read and correct. Every knowledge page carries a graded trust level, and every answer cites the pages it drew on. To see one before you build your own, run `bash setup.sh --with-example`, which loads a bundled demo wiki.

Think of the model as a CPU and its context window as RAM, fast but emptied when a conversation ends. The wiki is the disk underneath, and the notes a conversation needs flow back up into the context window.

![Two loops around an AI agent labelled cpu with its context tray labelled ram: on the left, the user sends a question and receives an answer; on the right, the agent files sources into a violet vault labelled disk that holds a knowledge graph, and draws a note back into its tray](assets/hero.png)

Feed it for a month and the assistant stops being a stranger; a year in, nothing else will know your work the way it does.

## What it does today

Simply drop in your sources (PDFs, slides, links, blogs, and almost any other file format). The agent processes each one into linked Markdown, files it correctly, and keeps your cross-references and catalogue completely up to date. Instead of building a folder of unread clippings, you create a structured, compounding knowledge base that an AI can read natively.

Once populated, the wiki can:
* **Answers and generation:** The agent answers questions and creates almost any deliverable, from briefs and reports to presentations, tables, and cross-source syntheses.
* **Smart referencing:** It acts as a living, cited knowledge base that any agent can draw from. Every note carries a confidence level, so answers are grounded in your own sources and weighted by how trustworthy each one is, all while maintaining highly efficient token usage.
* **Persistent insight:** It proactively synthesises across your sources and offers to save valuable answers as permanent, linked notes, so a brilliant idea from a conversation can be preserved instead of lost when the chat ends.
* **Self-maintenance and growth:** The system actively cross-links files, merges duplicates, and flags conflicting information or knowledge gaps. It automatically maintains your catalogue and graph as your information compounds.

Reliability is built in rather than hoped for. Plans that change the framework are reviewed by an independent critic agent before they are approved.

We purposely designed the architecture to be universal and highly adaptable. Although it is pre-tuned for AI and machine learning research (treating models and benchmarks as primary note types), you can easily customise the repository to perfectly fit your own field or workflow. You can also personalise the agent itself in `CUSTOMISATION.md`, created on first setup: its name, tone, output styles and task roles come as starter examples, and the file is open-ended, so add whatever standing preferences you want every session to follow.

![The knowledge graph the agent builds, coloured by note type](assets/framework_demo.png)

## Setup

This is a framework rather than a plugin. It needs an AI coding agent that reads `CLAUDE.md` and the skills in `.claude/skills/`, and today that agent is Claude Code or the Claudian plugin inside Obsidian. Setup takes about ten minutes.

1. **Obsidian and the agent.** Install [Obsidian](https://obsidian.md) and open this folder as a vault. Then install the agent: the **Claudian** community plugin (Settings → Community plugins → Browse → *Claudian*), or [Claude Code](https://claude.com/claude-code) run from a terminal in the vault. Claudian is the only Obsidian plugin the framework requires.

2. **Command-line tools.** Install MarkItDown, which converts PDFs and Office documents to Markdown:

   ```bash
   pip install 'markitdown[all]'
   ```

   `python3`, `curl`, and `git` are also used, and are usually already present.

   GPT helper agents require an installed, authenticated Codex CLI; select model and effort options supported by that installation. The delegate skill documents their invocation. The open-access resolver requires your own `OA_CONTACT_EMAIL` configuration. The professor-loop authoring workflow is not included in this version.

3. **Capture skills (recommended).** Install kepano's [obsidian-skills](https://github.com/kepano/obsidian-skills). The agent uses `defuddle` for clean web capture and `obsidian-cli` for vault access. Without them, the framework falls back to `curl` and MarkItDown.

4. **Web Clipper (optional).** The [Obsidian Web Clipper](https://obsidian.md/clipper) browser extension saves web pages into `raw/` in one click. You can also drop files in `raw/` or paste a URL to the agent.

5. **Clone and initialise.**

   ```bash
   git clone https://github.com/HurricaHjz/second-yourself.git
   cd second-yourself
   bash setup.sh
   ```

   **Always run `setup.sh` once before first use.** It creates the wiki registries and applies the graph colour palette. It is safe to re-run at any time and never overwrites existing notes.

   To start with the bundled demo instead, run `bash setup.sh --with-example`. Then open the folder in Obsidian, open the graph view, and ask the agent `/query what is GPT?`. The answer is drawn from the demo wiki, with links to the notes behind it. Run `bash setup.sh --reset` when you are ready to start your own knowledge base. After that, the `examples/` folder is safe to delete.

   > **A fresh vault's graph is empty** until you load the demo or `/ingest` your first source. That is expected, not a fault. `setup.sh` and your first ingest apply the colour palette automatically, and Obsidian then colour-codes nodes by type. If the colours ever vanish later (Obsidian can rewrite its own graph config), just ask the agent to restore your graph colours.

6. **Back up your vault (optional).** Install the [Obsidian Git](https://github.com/Vinzent03/obsidian-git) plugin to sync your *whole* vault, notes included, to a **private** repository for version history and multi-device backup. Keep that private remote separate from this public framework repo. Your notes are never part of it.

## Hardware and running costs

Any computer that runs Obsidian is enough. The intelligence lives in the cloud agent, so there is no GPU to buy and no local model to host, and the vault itself is plain text that stays at megabytes even after months of use. The one optional extra, qmd semantic search, runs a small embedding model comfortably on a laptop CPU.

The real cost is API credits or plan quota, and the framework is built to keep it small. The agent reads selectively, catalogue first and then only the notes a task needs, instead of loading the whole vault. It also benefits from Claude's prompt caching. The stable opening of every session (the agent's rules and your preferences) is cached after the first turn, and re-reading cached text costs about a tenth of the normal input price, so long working sessions stay warm and cheap. Two habits help: batch new sources into one ingest run, and keep one task per conversation.

## Usage

**New here? Read the [Manual](MANUAL.md).** It covers the commands, the capture → compile → ask → maintain workflow, and all the options in full, so this README doesn't repeat them.

## How it works

Sources live in `raw/`; compiled notes live in `wiki/`, organised by type, with a generated `index.md` and `log.md`. The skills:

| Skill | Purpose |
|-------|---------|
| `ingest` | Compile sources from `raw/` into linked notes. |
| `gather` | Capture a topic into `raw/` — web-search it, or start from a page and the sources it cites. |
| `query` | Answer a question from the wiki, with citations. |
| `output` | Produce a grounded, cited document in `output/`. |
| `lint` | Check the wiki for broken links, orphans, and gaps (cheap, frequent). |
| `deep-lint` | Heavier ~monthly pass, token-bounded: audit confidence levels, flag stale claims, and re-check a capped set of sources against their live online versions. |
| `attic` | Retire notes into cold storage, or restore them — only ever on your explicit instruction. |
| `project` | Manage your own working repositories (Overleaf LaTeX, code) from the vault on your instruction: clones live outside the vault, the wiki keeps one registry row per repository, and content enters only as commit-pinned snapshots through `raw/` when you ask. |
| `reflect` | Capture what a working session taught — insight, method lessons, defects — and file what you approve. Only on your explicit instruction. |
| `adopt` | Bring a third-party skill or tool into the vault: fingerprint it, recommend a use level, report, then install and record it on your yes; `--retire` reverses. |
| `delegate` | The agent's own runbook for handing work to subagents: which lane, what it may write, how its findings get checked. You never call it; it shapes how larger jobs are run. |
| `qmd-search` | *(optional)* Local semantic search over the wiki via qmd; dormant unless installed. |
| `export-template` | Sync with the framework repo: `--pull` updates your copy from upstream; `--push` is the maintainer's publish path. See the [Manual](MANUAL.md). |

## What the repository tracks

The repository holds the framework only: skills, rules, configuration, and a small demo. Your own notes stay on your machine: `wiki/`, `raw/`, `output/`, `attic/`, `index.md`, `log.md`, and your personal `CUSTOMISATION.md` are excluded by `.gitignore`, so pushing only ever publishes changes to the framework.

To back those notes up, use the optional Obsidian Git step above. That gives you a separate, private repository.

## Credits and licence

The wiki layer builds on Andrej Karpathy's [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern, and capture uses kepano's [obsidian-skills](https://github.com/kepano/obsidian-skills). Released under the MIT License ([`LICENSE`](LICENSE.md)).
