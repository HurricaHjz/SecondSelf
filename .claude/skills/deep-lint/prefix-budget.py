#!/usr/bin/env python3
"""Always-on prefix reconciliation measurement for deep-lint Step 1 (read-only).

Report-only by construction: this script prints to stdout and stderr and writes nothing.

It measures every always-on context layer — the bytes that ride into the model on every
request of every session — and prints the runbook's own line so the run records it verbatim:

  prefix budget: CLAUDE.md <N> B · skills <M> B (<name> <n> · ...) · agents <A> B (<name> <n> · ...)
  · user-skills <U> B (<name> <n> · ...) · plugin-skills <P> B (<plugin>:<skill> <n> · ...)
  · customisation <K> B · MCP <k> declared · total ≈<T> tok/request

Layers and their conventions:
  - CLAUDE.md — whole file;
  - each `.claude/skills/*/SKILL.md` frontmatter block, per skill — the ever-loaded name and
    description block, measured from the first `---` line through the second, MARKERS INCLUDED
    (the two marker lines and their newlines total 8 B per file);
  - each `.claude/agents/*.md` frontmatter block, per definition, the same convention — the
    harness surfaces every definition's name and description in every session's system prompt;
  - each user-level `<claude home>/skills/*/SKILL.md` frontmatter block, per skill, the same
    convention (known-issues 2026-09-05: user-level descriptions sit in every session's skill
    listing and no reconciliation could attribute them). <claude home> is $CLAUDE_CONFIG_DIR when
    set and ~/.claude otherwise, the harness's own resolution, so a suite points both user-level
    arms at a fixture with one variable and never reads the live home;
  - each enabled plugin's skills, the same convention, labelled `<plugin>:<skill>`: a plugin is
    enabled when `enabledPlugins` sets its key true in <claude home>/settings.json, the project's
    .claude/settings.json or its .claude/settings.local.json, a later source overriding an earlier
    one key by key (the reading lint's check-plugins.py applies); its install path comes from
    <claude home>/plugins/installed_plugins.json, and its skill roots are `skills/` plus any
    `skills` path its .claude-plugin/plugin.json names;
  - CUSTOMISATION.md — whole file (the schema imports it on every request);
  - project-declared MCP servers, reported as `k declared`, never a bare `k`: user-level servers
    load into the session too and this probe does not see them, so a bare count would overstate
    what was checked.

With --diff-log it finds the LAST `prefix budget:` line in the given log, parses its per-layer
and per-name figures, and prints each delta (new names, retired names, changed bytes). Deltas
only: attributing a delta to its cause is the agent's job, not the script's. A layer the previous
line does not carry is a format baseline and says so (the agents layer from 2026-08-28, the
user-skills and plugin-skills layers from 2026-09-13), and a total diffed across such a line says
how much of its delta the unmeasured layers account for.

A missing layer SOURCE is a broken premise, not a zero: the layer prints PROBE FAILED and the run
exits 2 with every other layer still measured. Two user-level cases and one vault case are
legitimately absent on a fresh machine and report `n/a` at exit 0, the same `n/a` precedent the
lint injection guard uses: no `.claude/agents/` (`agents n/a (no directory)`), no
`<claude home>/skills/` (`user-skills n/a (no directory)`), and no enabled plugin
(`plugin-skills 0 B (no enabled plugin)`). An EMPTY but present skills or agents directory is a
real zero and reports as one, beside the number of candidates inspected so the zero carries its
scope.

The vault's own layers and the two user-level layers keep different policies (2026-09-13). A vault
skill or agent definition with no frontmatter block, or one that cannot be read, is PROBE FAILED:
the vault owns the file and its contract. The user-level layers read files the vault does not own,
so a user-level or plugin SKILL.md with no frontmatter block is a row at 0 description bytes with
one WARNING line naming it, and any other problem inside a user-level layer (an unreadable
candidate, a settings file that does not parse, an enabled plugin the install record cannot place
on disk) is a WARNING while that layer measured at least one skill, and PROBE FAILED only when the
layer measured none, since exit 2 means the probe could not answer. A project settings file that
does not parse still fails through the MCP probe, which reads the same file.

Usage (from the vault root):
  python3 .claude/skills/deep-lint/prefix-budget.py
  python3 .claude/skills/deep-lint/prefix-budget.py --vault <root> --diff-log wiki/log.md

Exit codes: 0 = every layer measured or legitimately absent, user-level WARNING lines included;
2 = a vault layer's premise failed, or a user-level layer with a problem measured nothing.
"""

import argparse
import json
import os
import re
import sys

# Bytes per token, the standard rough English ratio used for the prefix line; a bound, not a
# decider — nothing here fires on the token figure.
BYTES_PER_TOKEN = 4
# The frontmatter block, matched only at the very START of the file and markers included. Anchoring
# it matters: a file with no frontmatter but two `---` rules in its body otherwise measures as a
# phantom always-on layer, and a stray README under .claude/agents/ then enters the budget line.
# CRLF is accepted, and a closing marker with no trailing newline ends the block at end of file.
FM_BYTES_RE = re.compile(rb"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
# A UTF-8 byte-order mark; it precedes the marker, so skip it before matching and never count it.
BOM_BYTES = b"\xef\xbb\xbf"


def frontmatter_bytes(path):
    """Bytes of the leading frontmatter block, markers included; -1 when the file has none."""
    with open(path, "rb") as handle:
        data = handle.read()
    if data.startswith(BOM_BYTES):
        data = data[len(BOM_BYTES):]
    match = FM_BYTES_RE.match(data)
    return len(match.group(0)) if match else -1


def measure_dir(directory, pattern, foreign=False):
    """Measure each frontmatter block under a directory. Returns (rows, failures, candidates, zeroed).

    With foreign=True (the user-level layers) a candidate with no frontmatter block is a row at 0 B and its
    note goes to `zeroed` instead of `failures`: it carries no description block to measure, and the vault
    does not own the file. The vault's own layers call it with foreign=False, so `zeroed` stays empty."""
    rows, failures, zeroed = [], [], []
    candidates = 0
    try:
        names = sorted(os.listdir(directory))
    except OSError as exc:
        return [], [f"{directory} could not be listed ({exc.__class__.__name__})"], 0, []
    for name in names:
        path, label = pattern(directory, name)
        if path is None:
            continue
        candidates += 1
        try:
            size = frontmatter_bytes(path)
        except OSError as exc:
            # A path that is not a readable file — a directory named `x.md`, a broken symlink, a
            # permission-denied file — is reported, never allowed to abort the whole measurement.
            failures.append(f"{label} ({path}) could not be read ({exc.__class__.__name__})")
            continue
        if size < 0:
            note = f"{label} ({path}) does not begin with a frontmatter block"
            if foreign:
                rows.append((label, 0))
                zeroed.append(note)
            else:
                failures.append(note)
            continue
        rows.append((label, size))
    return rows, failures, candidates, zeroed


def skill_pattern(directory, name):
    path = os.path.join(directory, name, "SKILL.md")
    if os.path.isdir(os.path.join(directory, name)) and os.path.exists(path):
        return path, name
    return None, None


def agent_pattern(directory, name):
    if name.endswith(".md"):
        return os.path.join(directory, name), name[:-3]
    return None, None


def claude_home():
    """The user-level configuration root as the harness resolves it."""
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def enabled_plugins(home, root):
    """(enabled keys, source states, failures) from the three settings sources, in override order."""
    effective, states, failures = {}, [], []
    for label, path in (("user", os.path.join(home, "settings.json")),
                        ("project", os.path.join(root, ".claude", "settings.json")),
                        ("local", os.path.join(root, ".claude", "settings.local.json"))):
        if not os.path.exists(path):
            states.append(f"{label} absent")
            continue
        try:
            data = load_json(path)
        except (OSError, ValueError) as exc:
            failures.append(f"plugin-skills: the {label} settings file {path} could not be parsed "
                            f"({exc.__class__.__name__})")
            states.append(f"{label} unparseable")
            continue
        if not isinstance(data, dict):
            failures.append(f"plugin-skills: the {label} settings file {path} is not a JSON object")
            states.append(f"{label} unparseable")
            continue
        block = data.get("enabledPlugins")
        if block is not None and not isinstance(block, dict):
            failures.append(f"plugin-skills: the {label} settings file {path} carries an enabledPlugins "
                            f"that is not an object")
            block = None
        states.append(f"{label} present ({len(block) if block else 0} key(s))")
        for key, value in (block or {}).items():
            effective[key] = value is True
    return sorted(k for k, on in effective.items() if on), states, failures


def plugin_skill_roots(install_root):
    """`skills/` plus any `skills` path (a string or a list, relative to the install root) that the
    plugin's .claude-plugin/plugin.json names."""
    roots = [os.path.join(install_root, "skills")]
    try:
        manifest = load_json(os.path.join(install_root, ".claude-plugin", "plugin.json"))
    except (OSError, ValueError):
        manifest = None
    extra = manifest.get("skills") if isinstance(manifest, dict) else None
    for rel in ([extra] if isinstance(extra, str) else extra if isinstance(extra, list) else []):
        if isinstance(rel, str):
            path = os.path.normpath(os.path.join(install_root, rel))
            if path not in roots:
                roots.append(path)
    return roots


def measure_plugin_skills(home, enabled):
    """(rows, problems, candidates, zeroed) over every enabled plugin's skill roots, each note labelled
    `plugin-skills:`. A skill with no frontmatter block is a row at 0 B, as in the user skills layer; the
    caller decides whether a problem is a warning or a probe failure."""
    rows, failures, candidates, zeroed = [], [], 0, []
    if not enabled:
        return rows, failures, candidates, zeroed
    record_path = os.path.join(home, "plugins", "installed_plugins.json")
    try:
        record = load_json(record_path)
    except (OSError, ValueError) as exc:
        return rows, [f"plugin-skills: {len(enabled)} plugin(s) enabled but the install record "
                      f"{record_path} could not be read ({exc.__class__.__name__})"], 0, zeroed
    plugins = record.get("plugins") if isinstance(record, dict) else None
    for key in enabled:
        entries = plugins.get(key) if isinstance(plugins, dict) else None
        paths = [e.get("installPath") for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []
        install_root = next((p for p in paths if isinstance(p, str) and os.path.isdir(p)), None)
        if install_root is None:
            failures.append(f"plugin-skills: {key} is enabled but the install record places no install path on disk")
            continue
        name = key.split("@", 1)[0]
        for skills_root in plugin_skill_roots(install_root):
            single = os.path.join(skills_root, "SKILL.md")
            if os.path.isfile(single):
                label = os.path.basename(skills_root)
                found, bad, count, zero = [], [], 1, []
                try:
                    size = frontmatter_bytes(single)
                except OSError as exc:
                    size, bad = None, [f"{label} ({single}) could not be read ({exc.__class__.__name__})"]
                if size is not None and size < 0:
                    found, zero = [(label, 0)], [f"{label} ({single}) does not begin with a frontmatter block"]
                elif size is not None:
                    found = [(label, size)]
            elif os.path.isdir(skills_root):
                found, bad, count, zero = measure_dir(skills_root, skill_pattern, foreign=True)
            else:
                continue
            rows.extend((f"{name}:{label}", size) for label, size in found)
            failures.extend(f"plugin-skills: {name}:{note}" for note in bad)
            zeroed.extend(f"plugin-skills: {name}:{note}" for note in zero)
            candidates += count
    return rows, failures, candidates, zeroed


def mcp_servers(root):
    """Project-declared MCP server names, with the files actually checked."""
    names, checked, failures = set(), [], []
    for rel, key in ((".mcp.json", "mcpServers"), (os.path.join(".claude", "settings.json"), "mcpServers")):
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            checked.append(f"{rel} absent")
            continue
        try:
            data = json.load(open(path, encoding="utf-8"))
        except (ValueError, OSError) as exc:
            failures.append(f"{rel} could not be parsed ({exc.__class__.__name__})")
            checked.append(f"{rel} unparseable")
            continue
        block = data.get(key) if isinstance(data, dict) else None
        found = sorted(block) if isinstance(block, dict) else []
        names.update(found)
        checked.append(f"{rel} present ({len(found)})")
    return sorted(names), checked, failures


def parse_pairs(blob):
    """Parse `name 123 · other 456` into a name -> bytes mapping."""
    out = {}
    for chunk in blob.split("·"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.rsplit(None, 1)
        if len(parts) == 2 and parts[1].isdigit():
            out[parts[0].strip()] = int(parts[1])
    return out


def parse_previous(line):
    """Parse a previous `prefix budget:` line into its layers; missing layers stay None."""
    got = {"claude": None, "skills": None, "skill_rows": None, "agents": None,
           "agent_rows": None, "user_skills": None, "user_skill_rows": None,
           "plugin_skills": None, "plugin_skill_rows": None, "customisation": None,
           "mcp": None, "total": None}
    m = re.search(r"CLAUDE\.md\s+(\d+)\s*B", line)
    if m:
        got["claude"] = int(m.group(1))
    # The vault layer's name is a suffix of the two user-level ones, so it must not follow a hyphen.
    for key, pattern in (("skills", r"(?<![\w-])skills"), ("agents", r"(?<![\w-])agents"),
                         ("user_skills", r"user-skills"), ("plugin_skills", r"plugin-skills")):
        m = re.search(pattern + r"\s+(\d+)\s*B\s*\(([^)]*)\)", line)
        if m:
            got[key] = int(m.group(1))
            got[{"skills": "skill_rows", "agents": "agent_rows"}.get(key, key[:-1] + "_rows")] = parse_pairs(m.group(2))
    m = re.search(r"customisation\s+(\d+)\s*B", line)
    if m:
        got["customisation"] = int(m.group(1))
    m = re.search(r"MCP\s+(\d+)\s+declared", line)
    if m:
        got["mcp"] = int(m.group(1))
    m = re.search(r"total\s*[≈~]?\s*(\d+)\s*tok/request", line)
    if m:
        got["total"] = int(m.group(1))
    return got


def diff_layer(label, old, new, unit="B"):
    if new is None:
        return f"  {label}: n/a this run — the layer's source is absent, so it is not diffed"
    if old is None:
        return f"  {label}: no figure in the previous line — format baseline, cannot diff"
    delta = new - old
    sign = "+" if delta > 0 else ""
    state = "no change" if delta == 0 else f"{sign}{delta}"
    return f"  {label}: {old} -> {new} {unit} ({state})"


def diff_rows(kind, old_rows, new_rows):
    lines = []
    if new_rows is None:
        return [f"    {kind} per name: n/a this run — the layer's source is absent"]
    if old_rows is None:
        return [f"  {kind} per name: no figures in the previous line — format baseline, cannot diff"]
    for name in sorted(set(old_rows) | set(new_rows)):
        was, now = old_rows.get(name), new_rows.get(name)
        if was is None:
            lines.append(f"    new {kind}: {name} {now} B")
        elif now is None:
            lines.append(f"    retired {kind}: {name} (was {was} B)")
        elif was != now:
            delta = now - was
            lines.append(f"    {kind} {name}: {was} -> {now} B ({'+' if delta > 0 else ''}{delta})")
    if not lines:
        lines.append(f"    {kind} per name: no change")
    return lines


def main():
    parser = argparse.ArgumentParser(
        description="Deep-lint always-on prefix measurement (read-only; prints, never writes).")
    parser.add_argument("--vault", default=".", help="vault root (default: the current directory)")
    parser.add_argument("--diff-log", default=None,
                        help="log file to diff against (its last `prefix budget:` line)")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    # A file name that is not valid UTF-8 arrives here as a surrogate; without this the first print
    # touching it aborts the whole report. Mangled beats missing, and it changes nothing otherwise.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")

    root = os.path.abspath(args.vault)
    failures = []

    claude_path = os.path.join(root, "CLAUDE.md")
    claude_bytes = 0
    if os.path.isfile(claude_path):
        claude_bytes = os.path.getsize(claude_path)
    else:
        failures.append("CLAUDE.md is absent")

    skills_dir = os.path.join(root, ".claude", "skills")
    skill_rows, skill_candidates = [], 0
    if os.path.isdir(skills_dir):
        skill_rows, skill_failures, skill_candidates, _ = measure_dir(skills_dir, skill_pattern)
        failures.extend(skill_failures)
    else:
        failures.append(".claude/skills is absent or is not a directory")

    # `.claude/agents/` is the one optional layer: a fresh machine has no definitions yet, and that
    # is a legitimate vault state rather than a broken premise. Report it as `n/a`, keep every other
    # layer measured, and stay at exit 0 — the same `n/a` the lint injection guard prints when the
    # surface it checks does not exist. A present directory is measured exactly as before.
    agents_dir = os.path.join(root, ".claude", "agents")
    agent_rows, agent_candidates = [], 0
    agents_present = os.path.isdir(agents_dir)
    if agents_present:
        agent_rows, agent_failures, agent_candidates, _ = measure_dir(agents_dir, agent_pattern)
        failures.extend(agent_failures)

    # The two user-level layers (2026-09-13). An absent user skills directory is a fresh machine,
    # n/a like the agents layer; no enabled plugin is a real zero. Both read files the vault does not
    # own: a SKILL.md with no frontmatter is a 0 B row with a warning, and any other problem inside a
    # layer is a warning while that layer measured a skill, PROBE FAILED only when it measured none.
    home = claude_home()
    user_dir = os.path.join(home, "skills")
    user_rows, user_problems, user_candidates, user_zeroed = [], [], 0, []
    user_present = os.path.isdir(user_dir)
    if user_present:
        user_rows, user_problems, user_candidates, user_zeroed = measure_dir(user_dir, skill_pattern, foreign=True)
        user_problems = [f"user-skills: {note}" for note in user_problems]
        user_zeroed = [f"user-skills: {note}" for note in user_zeroed]
    enabled, plugin_states, settings_failures = enabled_plugins(home, root)
    plugin_rows, plugin_failures, plugin_candidates, plugin_zeroed = measure_plugin_skills(home, enabled)
    warnings = []
    for layer_rows, problems, zeroed in ((user_rows, user_problems, user_zeroed),
                                         (plugin_rows, settings_failures + plugin_failures, plugin_zeroed)):
        warnings.extend(f"{note} — counted as 0 description bytes (a user-level file the vault does not own)"
                        for note in zeroed)
        if layer_rows:
            warnings.extend(f"{note} — the layer measured {len(layer_rows)} skill(s), so a warning, not a probe "
                            f"failure" for note in problems)
        else:
            failures.extend(problems)

    cust_path = os.path.join(root, "CUSTOMISATION.md")
    cust_bytes = 0
    if os.path.isfile(cust_path):
        cust_bytes = os.path.getsize(cust_path)
    else:
        failures.append("CUSTOMISATION.md is absent")

    servers, checked, mcp_failures = mcp_servers(root)
    failures.extend(mcp_failures)

    skills_bytes = sum(size for _, size in skill_rows)
    agents_bytes = sum(size for _, size in agent_rows) if agents_present else None
    user_bytes = sum(size for _, size in user_rows) if user_present else None
    plugin_bytes = sum(size for _, size in plugin_rows)
    total = claude_bytes + skills_bytes + (agents_bytes or 0) + (user_bytes or 0) + plugin_bytes + cust_bytes
    tokens = total // BYTES_PER_TOKEN

    agents_clause = (f"agents {agents_bytes} B ({' · '.join(f'{n} {b}' for n, b in agent_rows)})"
                     if agents_present else "agents n/a (no directory)")
    user_clause = (f"user-skills {user_bytes} B ({' · '.join(f'{n} {b}' for n, b in user_rows)})"
                   if user_present else "user-skills n/a (no directory)")
    plugin_clause = (f"plugin-skills {plugin_bytes} B ({' · '.join(f'{n} {b}' for n, b in plugin_rows)})"
                     if enabled else "plugin-skills 0 B (no enabled plugin)")
    budget_line = (
        f"prefix budget: CLAUDE.md {claude_bytes} B · "
        f"skills {skills_bytes} B ({' · '.join(f'{n} {b}' for n, b in skill_rows)}) · "
        f"{agents_clause} · {user_clause} · {plugin_clause} · "
        f"customisation {cust_bytes} B · MCP {len(servers)} declared · "
        f"total ≈{tokens} tok/request"
    )

    diff_lines = []
    previous_line = None
    if args.diff_log:
        log_path = args.diff_log if os.path.isabs(args.diff_log) else os.path.join(root, args.diff_log)
        if not os.path.exists(log_path):
            failures.append(f"--diff-log {args.diff_log} does not exist")
        else:
            for line in open(log_path, encoding="utf-8", errors="replace"):
                found = line.rfind("prefix budget:")
                if found >= 0:
                    # A log entry is one long line, so keep only the budget clause: parsing the
                    # whole line would let unrelated figures earlier in it match a layer regex.
                    previous_line = line[found:].strip()
            if previous_line is None:
                diff_lines.append(f"  no previous prefix budget line in {args.diff_log} — "
                                  f"this run is the baseline")
            else:
                old = parse_previous(previous_line)
                diff_lines.append(diff_layer("CLAUDE.md", old["claude"], claude_bytes))
                diff_lines.append(diff_layer("skills", old["skills"], skills_bytes))
                diff_lines.extend(diff_rows("skill", old["skill_rows"], dict(skill_rows)))
                diff_lines.append(diff_layer("agents", old["agents"], agents_bytes))
                diff_lines.extend(diff_rows("agent", old["agent_rows"],
                                            dict(agent_rows) if agents_present else None))
                diff_lines.append(diff_layer("user-skills", old["user_skills"], user_bytes))
                diff_lines.extend(diff_rows("user skill", old["user_skill_rows"],
                                            dict(user_rows) if user_present else None))
                diff_lines.append(diff_layer("plugin-skills", old["plugin_skills"], plugin_bytes))
                diff_lines.extend(diff_rows("plugin skill", old["plugin_skill_rows"], dict(plugin_rows)))
                diff_lines.append(diff_layer("customisation", old["customisation"], cust_bytes))
                diff_lines.append(diff_layer("MCP", old["mcp"], len(servers), unit="declared"))
                diff_lines.append(diff_layer("total", old["total"], tokens, unit="tok/request"))
                unmeasured = ((user_bytes or 0) if old["user_skills"] is None else 0) + \
                             (plugin_bytes if old["plugin_skills"] is None else 0)
                if old["total"] is not None and unmeasured:
                    diff_lines.append(f"  total: ≈{unmeasured // BYTES_PER_TOKEN} tok/request of that delta is the "
                                      f"user-skills and plugin-skills layers the previous line never measured")

    result = {
        "vault": root,
        "claude_md": claude_bytes,
        "skills": {"total": skills_bytes, "rows": dict(skill_rows), "count": len(skill_rows),
                   "candidates": skill_candidates},
        "agents": {"present": agents_present, "total": agents_bytes,
                   "rows": dict(agent_rows) if agents_present else None,
                   "count": len(agent_rows), "candidates": agent_candidates},
        "user_skills": {"home": home, "present": user_present, "total": user_bytes,
                        "rows": dict(user_rows) if user_present else None,
                        "count": len(user_rows), "candidates": user_candidates,
                        "without_frontmatter": len(user_zeroed)},
        "plugin_skills": {"enabled": enabled, "settings": plugin_states, "total": plugin_bytes,
                          "rows": dict(plugin_rows), "count": len(plugin_rows),
                          "candidates": plugin_candidates, "without_frontmatter": len(plugin_zeroed)},
        "customisation": cust_bytes,
        "mcp": {"declared": len(servers), "names": servers, "checked": checked},
        "total_bytes": total,
        "tokens": tokens,
        "budget_line": budget_line,
        "previous_line": previous_line,
        "diff": diff_lines,
        "warnings": warnings,
        "probe_failures": failures,
    }

    if args.format == "json":
        json.dump(result, sys.stdout, indent=1, sort_keys=True)
        sys.stdout.write("\n")
        for note in warnings:
            print(f"WARNING: {note}", file=sys.stderr)
        for note in failures:
            print(f"PROBE FAILED: {note}", file=sys.stderr)
        return 2 if failures else 0

    agents_scope = (f"agents measured={len(agent_rows)} of {agent_candidates} candidates"
                    if agents_present else "agents n/a (no .claude/agents directory)")
    print(f"prefix-budget: vault={root} skills measured={len(skill_rows)} of {skill_candidates} "
          f"candidates {agents_scope} bytes/token={BYTES_PER_TOKEN}   "
          f"(the candidate counts are the scope a zero would be measured over)")
    def zero_note(zeroed):
        return f" ({len(zeroed)} without frontmatter, counted as 0 B)" if zeroed else ""
    user_scope = (f"user-skills measured={len(user_rows)} of {user_candidates} candidates{zero_note(user_zeroed)}"
                  if user_present else "user-skills n/a (no skills directory)")
    print(f"prefix-budget: claude home={home} {user_scope} plugin-skills measured={len(plugin_rows)} of "
          f"{plugin_candidates} candidates{zero_note(plugin_zeroed)} from {len(enabled)} enabled plugin(s)"
          + (f" ({', '.join(enabled)})" if enabled else "") + f" · settings: {' · '.join(plugin_states)}")
    print(f"mcp-probe: {' · '.join(checked)} — {len(servers)} declared"
          + (f" ({', '.join(servers)})" if servers else ""))
    print(budget_line)
    if args.diff_log:
        print(f"--- DIFF vs {args.diff_log} ---")
        if previous_line:
            print(f"  previous: {previous_line[:160]}")
        for line in diff_lines:
            print(line)
        if not diff_lines:
            print("  no delta computed — the log named above could not be read; see the probe "
                  "failure below")
    for note in warnings:
        print(f"WARNING: {note}")
    for note in failures:
        print(f"PROBE FAILED: {note}")
    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
