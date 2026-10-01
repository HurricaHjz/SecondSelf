#!/usr/bin/env python3
"""check-plugins.py — the injection guard's plugin arm (lint Step 2e).

Stdout-only by construction: reads settings files, the plugin install record and the
machine-local baseline, prints, writes nothing.

Why (known-issues 2026-09-05): a plugin enabled in settings adds its skills to every session, and
a plugin that ships hooks adds hooks to every session too, while the injection guard watched only
the skills and agents roots. This arm lists every enabled plugin and compares its key
(`<name>@<marketplace>`) with the `plugin:<key>` lines of the machine-local baseline
`<claude home>/skills/.sanctioned.txt`, the file the user-level skills arm already diffs (its other
lines are skill names, which this arm ignores, and the skills arm's `comm -13` never prints a
baseline-only line).

Sources, each reported present or absent on the first line:
  <claude home>/settings.json, the user settings, where <claude home> is $CLAUDE_CONFIG_DIR when
  set and ~/.claude otherwise (the harness's own resolution);
  <vault>/.claude/settings.json and <vault>/.claude/settings.local.json, the project settings.
A later source overrides an earlier one key by key, in that order (user, project, local), so a
plugin a project turns off with `false` is not enabled. For each enabled plugin the install record
<claude home>/plugins/installed_plugins.json names its install path, and the line says whether
that root ships hooks (`hooks/hooks.json`, or a `hooks` entry in `.claude-plugin/plugin.json`).

Premises, each in its own way (the Step 2e convention: never a silent clean):
  - a settings file that exists but does not parse as a JSON object, or whose `enabledPlugins`
    is not an object: PROBE FAILED, exit 2;
  - no baseline file, or a baseline with no `plugin:` line: the baseline is not seeded, so the
    enabled list prints as information with a proposal to seed it after the owner reviews, never
    a finding and never auto-seeded, exit 0 (Step 2e's fresh-machine rule);
  - a seeded baseline: an enabled key with no `plugin:` line is an UNSANCTIONED PLUGIN, exit 1,
    and a `plugin:` line naming no enabled plugin is drift, information only.
Control on every run: a known-absent key injected into the enabled side must come out
unsanctioned against the same baseline; if it does not, PROBE FAILED.

Usage (from the vault root):
  python3 .claude/skills/lint/check-plugins.py [--vault ROOT] [--baseline FILE]
  exit 0 = clean or not seeded · 1 = unsanctioned plugins · 2 = broken premise
"""
import json
import os
import sys

USAGE = ("usage: check-plugins.py [--vault ROOT] [--baseline FILE]   "
         "(exit 0 clean or not seeded · 1 unsanctioned · 2 broken premise)")
CONTROL_KEY = "zzz-ctrl@nowhere"


def probe_failed(message):
    print(f"PROBE FAILED: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_args(argv):
    """(vault, baseline); an unknown argument is refused, never read as a root."""
    vault, baseline, rest = None, None, list(argv)
    while rest:
        arg = rest.pop(0)
        if arg in ("-h", "--help"):
            print(USAGE)
            raise SystemExit(0)
        if arg in ("--vault", "--baseline"):
            if not rest:
                probe_failed(f"{arg} needs an argument")
            value = rest.pop(0)
        elif arg.startswith("--vault=") or arg.startswith("--baseline="):
            arg, value = arg.split("=", 1)
        else:
            probe_failed(f"unknown argument {arg} ({USAGE})")
        if arg == "--vault":
            vault = value
        else:
            baseline = value
    return vault, baseline


def claude_home():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read_settings(path, label):
    """(state text, enabledPlugins object or None) for one settings file."""
    if not os.path.exists(path):
        return "absent", None
    try:
        data = load_json(path)
    except (OSError, ValueError) as exc:
        probe_failed(f"the {label} settings file {path} could not be parsed ({exc.__class__.__name__})")
    if not isinstance(data, dict):
        probe_failed(f"the {label} settings file {path} is not a JSON object")
    block = data.get("enabledPlugins")
    if block is None:
        return "present (no enabledPlugins)", None
    if not isinstance(block, dict):
        probe_failed(f"the {label} settings file {path}: enabledPlugins is not an object")
    return f"present ({len(block)} key(s))", block


def baseline_keys(path):
    """(state text, set of sanctioned plugin keys)."""
    if not os.path.isfile(path):
        return "absent", set()
    keys = set()
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                text = line.strip()
                if text.startswith("plugin:") and text[len("plugin:"):].strip():
                    keys.add(text[len("plugin:"):].strip())
    except OSError as exc:
        probe_failed(f"the baseline {path} could not be read ({exc.__class__.__name__})")
    return "present", keys


def unsanctioned(enabled, keys):
    return sorted(k for k in enabled if k not in keys)


def install_record(home):
    path = os.path.join(home, "plugins", "installed_plugins.json")
    try:
        data = load_json(path)
    except (OSError, ValueError):
        return None
    plugins = data.get("plugins") if isinstance(data, dict) else None
    return plugins if isinstance(plugins, dict) else None


def hooks_note(key, record):
    """Whether the plugin's install root ships hooks, as far as the install record lets us see."""
    if record is None:
        return "hooks unknown (no readable install record)"
    entries = record.get(key)
    if not isinstance(entries, list) or not entries:
        return "hooks unknown (not in the install record)"
    for entry in entries:
        path = entry.get("installPath") if isinstance(entry, dict) else None
        if not isinstance(path, str) or not os.path.isdir(path):
            continue
        if os.path.isfile(os.path.join(path, "hooks", "hooks.json")):
            return "ships hooks (hooks/hooks.json reaches every session)"
        try:
            manifest = load_json(os.path.join(path, ".claude-plugin", "plugin.json"))
        except (OSError, ValueError):
            manifest = None
        if isinstance(manifest, dict) and manifest.get("hooks"):
            return "ships hooks (plugin.json hooks reach every session)"
        return "no hooks"
    return "hooks unknown (no install path on disk)"


def main():
    vault, baseline_arg = parse_args(sys.argv[1:])
    root = vault if vault else "."
    if not all(os.path.isdir(os.path.join(root, d)) for d in ("raw", "wiki")):
        probe_failed(f"{root} is not a vault root (no raw/ or wiki/)")
    home = claude_home()
    effective, origin, states = {}, {}, []
    for label, path in (("user", os.path.join(home, "settings.json")),
                        ("project", os.path.join(root, ".claude", "settings.json")),
                        ("local", os.path.join(root, ".claude", "settings.local.json"))):
        state, block = read_settings(path, label)
        states.append(f"{label} {state}")
        for key, value in (block or {}).items():
            effective[key] = value is True
            origin[key] = label
    enabled = sorted(k for k, on in effective.items() if on)
    baseline = baseline_arg or os.path.join(home, "skills", ".sanctioned.txt")
    b_state, keys = baseline_keys(baseline)
    if CONTROL_KEY not in unsanctioned(enabled + [CONTROL_KEY], keys):
        probe_failed(f"the injected control key {CONTROL_KEY} did not come out unsanctioned")
    record = install_record(home)

    print(f"plugins-guard: {len(enabled)} enabled ({', '.join(enabled) or 'none'}) | baseline {baseline}: "
          f"{b_state}, {len(keys)} plugin: line(s) | settings: {' · '.join(states)}   "
          f"(the enabled count is the scope a clean result covers)")
    print(f"CONTROL: the known-absent key {CONTROL_KEY} injected into the enabled side -> unsanctioned")
    if not keys:
        print(f"UNSANCTIONED PLUGINS: n/a (baseline not seeded: no plugin: line in {baseline}) — the list below "
              f"is information; propose one `plugin:<key>` line per plugin after the owner reviews, never auto-seeded")
        for key in enabled:
            print(f"  (enabled, not yet baselined) {key} · enabled in {origin[key]} settings · {hooks_note(key, record)}")
        return 0
    bad = unsanctioned(enabled, keys)
    print(f"UNSANCTIONED PLUGINS: {len(bad)}")
    for key in bad:
        print(f"  {key} · enabled in {origin[key]} settings · {hooks_note(key, record)}")
    for key in sorted(set(enabled) & keys):
        print(f"  (sanctioned) {key} · {hooks_note(key, record)}")
    for key in sorted(keys - set(enabled)):
        print(f"  (drift: baselined, not enabled) {key}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
