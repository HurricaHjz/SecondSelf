#!/usr/bin/env python3
"""recall-probe.py — does a task read only the experience it needs? (reflect Step 7; deep-lint 4a)

An experience page is read through a pointer at the step where its feature decides, and at no other
time. Routine lint can compare files; only a real session can show that a task touching one feature
reads that page and no other. This runner measures that on a throwaway copy, so nothing it does
reaches the vault:

1. It copies CLAUDE.md, CUSTOMISATION.md, its definitions file, `.claude/skills/`, `.claude/agents/`
   and `wiki/` into a temporary folder, with an empty `raw/` and no settings or hooks. Decoy pages
   named by the task file join the copy's `wiki/experience/`, with index lines, so a session that
   loads the folder cannot pass unseen. A fixture pointer the task file names goes under a skill
   step in the copy, to test a step pointer where no real page uses one yet. Decoys and fixture
   pointers exist only in the copy.
2. It runs each task as a fresh headless session from the copy, with read tools only and no session
   saved, on the deciding seat's model. A task of kind `helper` runs from an empty folder beside
   the copy instead, seeing the copy through a grant, as a helper with the wiki view does.
3. It reads the session's own tool record: every path under `wiki/experience/` that a Read, Grep or
   Glob touched.
4. It scores. A `fitting` task must read its page before its last reply, read no other page, reach
   it through its pointer, and carry the use note (the page's exact name in brackets) in its reply.
   An `unrelated` task must touch no page. A `helper` task must read its page and no other. A
   search over the folder that brings back file names alone loads no page, so it is noted and
   passes; a content search over the folder loads lines of every page it hits, so it fails. The route is read from the record: a page
   first surfaced by a content search was found by luck of wording, not by its pointer, so it fails;
   a page named in the session's context, in a skill or file it read, or found by a glob on the
   page's own name came through its pointer.

A second arm, `--without-pointer PAGE`, removes that page's pointer from the copy and runs its tasks
again: there the page must not be reached through a pointer, which is what shows the first arm's
reads came from the pointer and not from the task's wording. A read in that arm is printed with its
route. A model's tool record is the evidence, so the score cannot be read off the question. Scripts
score reads and routes; whether a read came before the decision (the first text committing to what
the task asks, never the status line or a line of intent) is read from the record by a fresh
checker, who gets each session's record. A failed task reruns once before any pointer moves. Three
clean tries find gross failure only: under independent tries they leave a 95 % upper bound of 0.632
on a common miss rate, so the result reads `no gross failure`, never a miss rate.

The task file (JSON, private: it names private pages):
  {"decoys": ["<kebab-name>", ...],
   "fixture_pointers": [{"page": "<a decoy>", "file": "<a skill file>", "heading": "<its exact
                         heading line>", "decision": "<the decision, in words>"}],
   "tasks": [{"id": "F1", "kind": "fitting|unrelated|helper", "page": "<kebab-name>",
              "prompt": "<the message>"}, ...]}

Usage (from the vault root):
  python3 .claude/skills/reflect/recall-probe.py --tasks FILE [--vault ROOT] [--page NAME]...
      [--only ID]... [--without-pointer PAGE] [--model opus] [--effort xhigh] [--out DIR] [--dry-run]
  python3 .claude/skills/reflect/recall-probe.py --score STREAM --kind KIND [--page NAME]
  --page keeps that page's tasks and the first unrelated task, since other pointers did not move.
  --score reads one saved stream-JSON record and prints its verdict, with no model call.
  exit 0 = every task passed · 1 = a task failed · 2 = broken premise (not a vault root, an unknown
  flag, an unreadable task file, a malformed task, a session that did not finish)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

USAGE = ("usage: recall-probe.py --tasks FILE [--vault ROOT] [--page NAME]... [--only ID]... "
         "[--without-pointer PAGE] [--model M] [--effort E] [--out DIR] [--dry-run] | "
         "--score STREAM --kind KIND [--page NAME]")
FOLDER = "wiki/experience/"
TOOLS = "Read,Grep,Glob,Skill"
TASKS_NAME = "experience-recall-tasks.json"
KINDS = ("fitting", "unrelated", "helper")
DECOY = """---
title: "{name}"
type: synthesis
confidence: medium
audited: 2026-01-01
tags: [experience]
sources: [wiki/index.md]
aliases: []
created: 2026-01-01
updated: 2026-01-01
---

**Feature:** {name} · **Moment:** a fixture decision · **Read by:** `.claude/skills/none/SKILL.md` (Step 1) · **Multi-agent pattern:** one agent

End the decision with one plain clause in your own prose naming this page with its name in brackets ("I read the fixture page ({name}) and applied none of it").

## Rules
E1. A fixture entry. (lesson · 2026-01-01 · a fixture · [[index]])

## Measures
**Measures:** reach changed 2026-01-01 · probe not yet run · entry added 2026-01-01 · uses 0 and repeats 0 since 2026-01-01 · last label E1

## Related
- [[index]]
"""


def page_of(path):
    """The page stem a path names under the experience folder, or None."""
    m = re.search(r"(?:^|/)wiki/experience/([A-Za-z0-9-]+)\.md\b", path or "")
    return m.group(1) if m else None


def folder_touch(value):
    """True when a search path or pattern reaches the folder rather than one page."""
    value = value or ""
    return bool(re.search(r"(?:^|[/{,])wiki/experience(?:[/,}]|$)", value)) and page_of(value) is None


def result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(part.get("text") or "") for part in content if isinstance(part, dict))
    return ""


def parse_stream(lines):
    """(events, final text, result record): events in order are ('read', stem), ('touch', what),
    ('text', chars) and ('surfaced', tool, text), from a stream-JSON session's records."""
    events, final, result = [], "", None
    calls = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get("type") == "result":
            result = record
            final = record.get("result") or final
            continue
        if record.get("type") == "user":
            content = (record.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    events.append(("surfaced", calls.get(block.get("tool_use_id"), ("?", "")),
                                   result_text(block)))
            continue
        if record.get("type") != "assistant":
            continue
        for block in (record.get("message") or {}).get("content") or []:
            kind = block.get("type")
            if kind == "text" and (block.get("text") or "").strip():
                events.append(("text", block["text"]))
            elif kind == "tool_use":
                data = block.get("input") if isinstance(block.get("input"), dict) else {}
                name = block.get("name")
                calls[block.get("id")] = (name, str(data.get("pattern") or ""))
                if name == "Read":
                    stem = page_of(data.get("file_path"))
                    if stem:
                        events.append(("read", stem))
                    elif folder_touch(data.get("file_path")):
                        events.append(("touch", "Read %s" % data.get("file_path")))
                elif name in ("Grep", "Glob"):
                    names_only = name == "Glob" or data.get("output_mode") != "content"
                    for key in ("path", "pattern", "glob"):
                        if folder_touch(data.get(key)):
                            events.append(("listed" if names_only else "touch",
                                           "%s %s" % (name, data.get(key))))
                            break
                        stem = page_of(data.get(key))
                        if stem:
                            events.append(("read", stem))
                            break
    return events, final, result


def route(page, events):
    """How `page` first reached the session: 'search' when a content search surfaced it before its
    first read, else 'pointer'."""
    for event in events:
        if event == ("read", page):
            return "pointer"
        if event[0] != "surfaced" or (page + ".md" not in event[2] and "[[" + page not in event[2]):
            continue
        tool, pattern = event[1]
        if tool == "Grep" or (tool == "Glob" and page not in pattern):
            return "search"
        return "pointer"
    return "pointer"


def score(kind, page, events, final):
    """(passed, reasons) for one session's record."""
    reads = [e[1] for e in events if e[0] == "read"]
    touches = [e[1] for e in events if e[0] == "touch"]
    reasons = []
    if touches:
        reasons.append("folder touched: %s" % "; ".join(touches))
    if kind == "unrelated":
        if reads:
            reasons.append("read a page an unrelated task needs none of: %s" % ", ".join(sorted(set(reads))))
        return not reasons, reasons
    others = sorted({r for r in reads if r != page})
    if others:
        reasons.append("read another page: %s" % ", ".join(others))
    if page not in reads:
        reasons.append("did not read %s" % page)
    else:
        first = next(i for i, e in enumerate(events) if e == ("read", page))
        if not any(e[0] == "text" for e in events[first + 1:]) and not final:
            reasons.append("no reply after the read")
        if kind == "fitting" and route(page, events) == "search":
            reasons.append("reached by a content search, not through its pointer")
    if kind == "fitting" and "(%s)" % page not in final:
        reasons.append("no use note naming (%s) in the reply" % page)
    return not reasons, reasons


def add_fixture_pointers(out, pointers):
    """A step pointer under its heading, in the copy only. A heading not found once is a premise
    failure, so an edited skill cannot quietly leave the fixture out."""
    for item in pointers:
        target = out / item["file"]
        text = target.read_text(encoding="utf-8")
        heading = item["heading"] + "\n"
        if text.count(heading) != 1:
            raise ValueError("fixture heading not found once: %s" % item["heading"])
        pointer = ("**Experience:** before %s, and before changing how it is made, read "
                   "`wiki/experience/%s.md` whole.\n\n" % (item["decision"], item["page"]))
        target.write_text(text.replace(heading, heading + "\n" + pointer), encoding="utf-8")


def build_copy(root, out, decoys):
    """The throwaway copy. It carries no `.claude/settings*`, so no hook runs in it."""
    ignore = shutil.ignore_patterns("__pycache__", ".DS_Store", "*.pyc")
    for name in ("CLAUDE.md", "CUSTOMISATION.md", "CUSTOMISATION-definitions.md"):
        if (root / name).is_file():
            shutil.copy2(root / name, out / name)
    (out / ".claude").mkdir()
    for part in ("skills", "agents"):
        if (root / ".claude" / part).is_dir():
            shutil.copytree(root / ".claude" / part, out / ".claude" / part, ignore=ignore)
    shutil.copytree(root / "wiki", out / "wiki",
                    ignore=shutil.ignore_patterns("__pycache__", ".DS_Store", "*.pyc", TASKS_NAME))
    (out / "raw").mkdir()
    (out / "wiki" / "experience").mkdir(exist_ok=True)
    index = out / "wiki" / "index.md"
    text = index.read_text(encoding="utf-8")
    lines = "".join("- [[%s]] — a fixture decision.\n" % name for name in decoys)
    if decoys and "## Experience\n\n" in text:
        text = text.replace("## Experience\n\n", "## Experience\n\n" + lines, 1)
        index.write_text(text, encoding="utf-8")
    for name in decoys:
        (out / "wiki" / "experience" / (name + ".md")).write_text(DECOY.format(name=name),
                                                                  encoding="utf-8")


def remove_pointer(copy, page):
    """Take a page's pointers out of the copy: an always-on line naming it, or a step pointer line
    naming its path. The count of lines removed is returned, so an arm that removed nothing fails."""
    removed = 0
    path = "wiki/experience/%s.md" % page
    targets = [copy / "CLAUDE.md", copy / "CUSTOMISATION.md", copy / "CUSTOMISATION-definitions.md"]
    targets += [p for p in (copy / ".claude").rglob("*.md") if p.is_file()]
    for target in targets:
        if not target.is_file():
            continue
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = [l for l in lines if not ("[[%s]]" % page in l or
                                         ("**Experience:**" in l and path in l))]
        if len(kept) != len(lines):
            removed += len(lines) - len(kept)
            target.write_text("".join(kept), encoding="utf-8")
    return removed


def run_task(task, copy, model, effort, dry):
    argv = ["claude", "-p", "--model", model, "--effort", effort, "--tools", TOOLS,
            "--setting-sources", "project", "--strict-mcp-config", "--no-session-persistence",
            "--output-format", "stream-json", "--verbose"]
    cwd = copy
    if task["kind"] == "helper":
        cwd = copy.parent / "helper-home"
        cwd.mkdir(exist_ok=True)
        argv += ["--add-dir", str(copy)]
    if dry:
        return argv, None, None
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    try:
        done = subprocess.run(argv, input=task["prompt"], cwd=cwd, env=env, capture_output=True,
                              text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return argv, "", "the session timed out"
    return argv, done.stdout, done.stderr


def load_tasks(path, pages):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("no tasks")
    for task in tasks:
        if task.get("kind") not in KINDS or not task.get("id") or not task.get("prompt"):
            raise ValueError("malformed task: %r" % task.get("id"))
        if task["kind"] != "unrelated" and not task.get("page"):
            raise ValueError("task %s names no page" % task["id"])
    if pages:
        first = next((t["id"] for t in tasks if t["kind"] == "unrelated"), None)
        tasks = [t for t in tasks if t["id"] == first or t.get("page") in pages]
    return tasks, list(data.get("decoys") or []), list(data.get("fixture_pointers") or [])


def parse_args(argv):
    options = {"vault": ".", "tasks": None, "pages": [], "only": [], "model": "opus",
               "effort": "xhigh", "out": None, "dry": False, "score": None, "kind": None,
               "without": None}
    args = list(argv)
    names = {"--vault": "vault", "--tasks": "tasks", "--model": "model", "--effort": "effort",
             "--out": "out", "--score": "score", "--kind": "kind",
             "--without-pointer": "without"}
    while args:
        flag = args.pop(0)
        if flag in names and args:
            options[names[flag]] = args.pop(0)
        elif flag == "--page" and args:
            options["pages"].append(args.pop(0))
        elif flag == "--only" and args:
            options["only"].append(args.pop(0))
        elif flag == "--dry-run":
            options["dry"] = True
        else:
            print(USAGE, file=sys.stderr)
            sys.exit(2)
    return options


def score_file(options):
    if options["kind"] not in KINDS or (options["kind"] != "unrelated" and not options["pages"]):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        lines = Path(options["score"]).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print("PROBE FAILED: cannot read %s: %s" % (options["score"], exc))
        return 2
    events, final, result = parse_stream(lines)
    if result is None:
        print("PROBE FAILED: the stream has no result record")
        return 2
    page = options["pages"][0] if options["pages"] else None
    passed, reasons = score(options["kind"], page, events, final)
    print(("PASS" if passed else "FAIL") + (": " + "; ".join(reasons) if reasons else ""))
    return 0 if passed else 1


def main(argv):
    options = parse_args(argv)
    if options["score"]:
        return score_file(options)
    if not options["tasks"]:
        print(USAGE, file=sys.stderr)
        return 2
    root = Path(options["vault"]).resolve()
    if not (root / "raw").is_dir() or not (root / "wiki").is_dir():
        print("PROBE FAILED: %s is not a vault root (no raw/ or wiki/)" % root, file=sys.stderr)
        return 2
    try:
        tasks, decoys, pointers = load_tasks(options["tasks"], options["pages"])
    except (OSError, ValueError) as exc:
        print("PROBE FAILED: %s" % exc)
        return 2
    without = options["without"]
    if without:
        tasks = [t for t in tasks if t.get("page") == without and t["kind"] == "fitting"]
    if options["only"]:
        tasks = [t for t in tasks if t["id"] in options["only"]]
    if not tasks:
        print("PROBE FAILED: no task selected")
        return 2
    home = Path(options["out"] or tempfile.mkdtemp(prefix="recall-probe-")).resolve()
    copy = home / "copy"
    if copy.exists():
        print("PROBE FAILED: %s already holds a copy" % home)
        return 2
    home.mkdir(parents=True, exist_ok=True)
    copy.mkdir()
    build_copy(root, copy, decoys)
    try:
        add_fixture_pointers(copy, pointers)
    except (OSError, ValueError, KeyError) as exc:
        print("PROBE FAILED: %s" % exc)
        return 2
    if without and not remove_pointer(copy, without):
        print("PROBE FAILED: no pointer to %s found in the copy" % without)
        return 2
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()
    print("recall probe: %d tasks · model %s · effort %s · harness %s · copy %s"
          % (len(tasks), options["model"], options["effort"], version, copy))
    failed, broken, cost = 0, 0, 0.0
    for task in tasks:
        argv_used, stdout, stderr = run_task(task, copy, options["model"], options["effort"],
                                             options["dry"])
        if options["dry"]:
            print("DRY %s %s: %s" % (task["id"], task["kind"], " ".join(argv_used)))
            continue
        (home / ("%s.jsonl" % task["id"])).write_text(stdout or "", encoding="utf-8")
        events, final, result = parse_stream((stdout or "").splitlines())
        if result is None:
            print("BROKEN %s: the session did not finish: %s" % (task["id"], (stderr or "")[:200]))
            broken += 1
            continue
        cost += float(result.get("total_cost_usd") or 0)
        reads = sorted({e[1] for e in events if e[0] == "read"})
        if without:
            how = route(without, events) if without in reads else "none"
            print("%s %s no-pointer arm page=%s read=%s route=%s"
                  % ("FAIL" if how == "pointer" else "PASS", task["id"], without,
                     ",".join(reads) or "none", how))
            failed += 1 if how == "pointer" else 0
            continue
        passed, reasons = score(task["kind"], task.get("page"), events, final)
        listed = [e[1] for e in events if e[0] == "listed"]
        print("%s %s %s page=%s read=%s%s%s"
              % ("PASS" if passed else "FAIL", task["id"], task["kind"], task.get("page") or "-",
                 ",".join(reads) or "none", (" · " + "; ".join(reasons)) if reasons else "",
                 (" · names listed: " + "; ".join(listed)) if listed else ""))
        failed += 0 if passed else 1
    print("recall probe: tasks %d · failed %d · broken %d · cost $%.2f · records %s"
          % (len(tasks), failed, broken, cost, home))
    if broken:
        return 2
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
