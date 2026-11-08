#!/usr/bin/env python3
"""head-fence.py — PreToolUse(Bash) hook: the head's own path fence while a hands-off run is armed.

The same checker as a lane's, in the same process: this hook IMPORTS `lane-fence.py` and calls its
`check()` in the head role, so an armed head pays one interpreter start per Bash call and no more
(hands-off-mode-design.md, D34; N8 of critic C2's review).

UNARMED it is silent: no stdout, no stderr, exit 0. It costs that one start only past the shell check
in .claude/settings.json: with AIMYTH_HANDSOFF not 1, AIMYTH_STATE_DIR unset and no `armed-*` marker
in ~/.aimyth/handoffs, the command exits before Python starts. ARMED when
AIMYTH_HANDSOFF=1 is in the environment (the starter and the pre-flight's start command set it) or
the state directory holds the marker `armed-<session_id>` — handsoff-gate.py's own arming shape, so
one file arms and disarms both hooks together.

Armed, it resolves the run, loads that run's grant file and calls the checker:
  run     AIMYTH_HANDSOFF_RUN, else the state directory's pointer file `run-<session_id>` (one
          line, the run id, written by `handsoff.py run-open` and `run-resume`).
  grants  <store>/spawn-records/<run>-grants.json — LLM_WIKI_STORE, default ~/.llm-wiki resolved
          to its real path. Keys `grants` and `writes`: lists of real paths, the pre-flight's R and
          W columns, with the vault root, the store, the state directory, the projects root and
          /tmp among the defaults so the head's own primitives are never denied (C1 F2). Key
          `network` (new, optional; `run-open` and `grants` own writing it, B-HO1's): a list of hosts
          the run may reach — absent or empty means no network, and the fence denies every network
          command (register 2026-09-07, memory-hunter).
  checker <vault>/.claude/skills/delegate/lane-fence.py, the single source, beside lane.py. The
          vault comes from CLAUDE_PROJECT_DIR when it is set and holds that path, else from this
          hook's own location (…/.claude/hooks/head-fence.py → two levels up).
The head role turns off the no-nested-`claude` check (a head spawns lanes) and answers a CLEARED
command with SILENCE — never an explicit `allow`, which the harness reads as auto-approval and
which, armed in an attended session, would bypass every shell prompt the owner still keeps (C1 F1;
handsoff-gate.py's docstring states the same rule). A deny is the checker's JSON deny, printed as
the checker composed it, reason and all.

PREMISE FAILURES, and the direction each takes (N7):
  - the grant file is missing, unreadable, not JSON, has malformed grant fields, or carries no
    `grants` entries → DENY, with
    ONE exemption: a command whose text contains `handsoff.py` runs (a substring match, the hard
    band's own exemption shape), so `handsoff.py grants …` can write the file the fence is missing
    and `handsoff.py handoff …` can still close the run. An armed head with no grants is a head
    whose R and W nobody declared; denying it is what makes the miss visible at the next command
    rather than at the post-mortem, and the recovery is one command away.
  - no run resolved (no environment variable, no pointer file) → the same DENY with the same
    exemption: without a run there is no grant file to read.
  - the checker is missing or unimportable, or the payload is unreadable → ALLOW. A hook that
    cannot load its checker is broken machinery, not a policy: bricking an attended head at 3 am
    loses the run, and the pre-flight, `gate` and the head's own rule still carry the grants.
Every premise failure writes one line on stderr and one tab-separated `events.log` line
(timestamp, session, head-fence, allow-unarmed | deny-no-grants, reason), the shape
precompact-checkpoint.py and handsoff-gate.py write, so one series carries the lot. Every deny of a
command appends its own line (timestamp, session, head-fence, deny, the command's first 80
characters with the tab and every character `str.splitlines()` ends a line at made spaces, then the
whole command), and an exempted `handsoff.py grants` command appends a `grant-change` line (same
shape) so a self-grant is visible in the same series (register 2026-09-07, fix 3). The whole command
is the sixth field of every deny, deny-no-grants and grant-change line, written as
`json.dumps(command, ensure_ascii=True)`: one line with no raw tab, newline or Unicode line
separator, which `json.loads` recovers exactly, so a replay never needs the transcript (register
2026-09-14). Readers that take the first five fields count exactly as before, and a reader that
splits with `splitlines()` sees each line whole. The log is written UTF-8 with backslash
replacement, so a command holding a lone surrogate (a JSON payload can carry one) still leaves its
line: field five shows the surrogate as a backslash escape and field six recovers it exactly.

After a CLEARED command, and only then, the hook hands the event to the checker's
`record_unplaced_reads` (the owner's decision of 23 October 2026: a read the checker cannot
place is logged, never refused). It appends to `<store>/spawn-records/<run>-unplaced-reads.jsonl`
as `head`, under the writer's own premises, and never blocks: the call is guarded by `except
BaseException`, a failure is one stderr note, and a version-skewed checker without the recorder
simply does not log. The cleared command keeps its silence.

The grant-change exemption is the ONE place this hook and the checker diverge (CR-F F8): the checker
alone denies `handsoff.py grants --grant <new path>`, because a new path is by definition outside the
current grants, and only this hook clears it — before `check()` runs, and only for the vault's own
primitive standing first as one simple command (`is_grant_change`). A lane never runs it.

Never blocks by exit code: every path exits 0 and the decision travels in the JSON on stdout, which
is what the registration line (`... || true`) preserves.

Knobs (env): AIMYTH_HANDSOFF, AIMYTH_STATE_DIR (default ~/.aimyth/handoffs), AIMYTH_HANDSOFF_RUN,
LLM_WIKI_STORE (default ~/.llm-wiki), CLAUDE_PROJECT_DIR.
"""
import sys
sys.dont_write_bytecode = True   # never leave bytecode beside the hooks

import importlib.util
import ipaddress
import json
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SID_RE = re.compile(r"[A-Za-z0-9._-]{1,128}")    # a marker or pointer file name, or not at all
RUN_RE = re.compile(r"[A-Za-z0-9._-]{1,128}")    # a run id names a file in the store
CMD_HEAD = 80                    # characters of the command in the events line's fifth field
EXEMPT = "handsoff.py"           # the one command family a grant-less armed head may still run


def note(msg):
    sys.stderr.write("[head-fence] %s\n" % msg)


def state_dir():
    return os.path.expanduser(os.environ.get("AIMYTH_STATE_DIR")
                              or os.path.join("~", ".aimyth", "handoffs"))


# The tab and every character str.splitlines() ends a line at (the newline, CR, VT, FF, U+001C to
# U+001E, U+0085, U+2028 and U+2029): each becomes a space in a field, so one events line is one
# line to every reader, whichever way it splits.
FLAT = {ord(c): " " for c in "\t\n\r\x0b\x0c\x1c\x1d\x1e\x85" + chr(0x2028) + chr(0x2029)}


def field(v):
    return str(v).translate(FLAT) or "unknown"


def log_event(sid, action, detail, command=None):
    """One events.log line. A deny, deny-no-grants or grant-change line passes `command`, which
    becomes a sixth field holding the whole command as one ASCII-only JSON string. Written with
    backslash replacement, so a lone surrogate in a field cannot raise and lose the line."""
    path = os.path.join(state_dir(), "events.log")
    whole = "" if command is None else "\t" + json.dumps(command, ensure_ascii=True)
    try:
        os.makedirs(state_dir(), exist_ok=True)
        with open(path, "a", encoding="utf-8", errors="backslashreplace") as handle:
            handle.write("%s\t%s\thead-fence\t%s\t%s%s\n"
                         % (time.strftime("%Y-%m-%dT%H:%M:%S%z"), field(sid),
                            field(action), field(detail), whole))
    except OSError as exc:
        note("events.log append failed at %s: %s" % (path, exc))


def record_unplaced(module, event, run):
    """Log-only: record the reads the checker could not place. Never raises, never prints to stdout."""
    try:
        recorder = getattr(module, "record_unplaced_reads", None)
        if recorder is not None:          # a version-skewed checker simply does not log
            recorder(event, store_root(), run, "head")
    except BaseException as exc:          # SystemExit included: nothing here may end the hook
        note("unplaced-reads skipped (%s: %s)" % (type(exc).__name__, exc))


def emit(reason):
    """One PreToolUse deny on stdout. A cleared command gets nothing at all."""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))


def allow_open(sid, reason):
    """Broken machinery: allow the call, name the reason on stderr and in the events series."""
    note("premise failure: %s; allowing the call" % reason)
    log_event(sid, "allow-unarmed", reason)


def deny_no_grants(sid, command, reason):
    """No grants to check against: deny, unless the command is the recovery itself (N7)."""
    if EXEMPT in command:
        note("%s; allowing this `%s` command (the recovery)" % (reason, EXEMPT))
        log_event(sid, "allow-unarmed", "%s; exempt: %s" % (reason, EXEMPT))
        return
    emit("head-fence: %s. Every Bash call is denied until the grants are in place; `%s grants "
         "--run <run> --grant <path> --write <path>` writes them, and `%s` commands run meanwhile."
         % (reason, EXEMPT, EXEMPT))
    log_event(sid, "deny-no-grants", command[:CMD_HEAD], command)


def armed(sid):
    """Environment first (it needs no disk), then the marker file — handsoff-gate.py's shape."""
    if os.environ.get("AIMYTH_HANDSOFF") == "1":
        return True
    if not sid or not SID_RE.fullmatch(sid):
        return False
    return os.path.isfile(os.path.join(state_dir(), "armed-" + sid))


def resolve_run(sid):
    """The run id from the environment, else the state directory's `run-<sid>` pointer file."""
    run = (os.environ.get("AIMYTH_HANDSOFF_RUN") or "").strip()
    if run:
        return run, None
    if not sid or not SID_RE.fullmatch(sid):
        return None, "no run in the environment and session id %r cannot name a pointer file" % sid
    pointer = os.path.join(state_dir(), "run-" + sid)
    try:
        with open(pointer, encoding="utf-8") as handle:
            run = handle.readline().strip()
    except OSError:
        return None, "no AIMYTH_HANDSOFF_RUN and no run pointer at %s" % pointer
    if not run or not RUN_RE.fullmatch(run):
        return None, "the run pointer %s holds %r, which is not a run id" % (pointer, run)
    return run, None


def store_root():
    return os.path.realpath(os.path.expanduser(os.environ.get("LLM_WIKI_STORE") or "~/.llm-wiki"))


def grants_path(run):
    return os.path.join(store_root(), "spawn-records", "%s-grants.json" % run)


def grant_host(value):
    """A literal DNS hostname (including a single label) or an IP address, never an endpoint."""
    if "%" in value:
        return False                 # a scoped IPv6 zone is interface syntax, not a host grant
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        pass
    # DNS wire limit: 255 octets minus the first length octet and the root octet gives 253
    # presentation characters; each label has at most 63 octets. A final root dot is optional.
    name = value[:-1] if value.endswith(".") else value
    return (0 < len(name) <= 253 and all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in name.split(".")))


def load_grants(path):
    """(grants, writes, network, error). Validate every field before any normalisation: lists of
    non-empty strings, absolute filesystem paths for grants/writes, literal hosts for network.
    Missing writes/network retain their empty defaults; explicit null is malformed. Missing or
    empty grants still deny. This hook reads the grant file; the recovery command owns writing it.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, RecursionError) as exc:
        return None, None, [], "the grant file is unusable at %s (%s: %s)" % (path, type(exc).__name__, exc)
    if not isinstance(data, dict):
        return None, None, [], "the grant file %s holds %s, not an object" % (path, type(data).__name__)
    for key in ("grants", "writes", "network"):
        values = data.get(key, [])
        problem = None
        if not isinstance(values, list):
            problem = "must be a list of non-empty strings"
        else:
            for index, value in enumerate(values):
                if not isinstance(value, str) or not value.strip():
                    problem = "entry %d must be a non-empty string" % index
                elif key == "network":
                    if not grant_host(value):
                        problem = "entry %d must be a literal host name or IP address" % index
                elif not os.path.isabs(value) or "\0" in value:
                    problem = "entry %d must be an absolute path without NUL" % index
                else:
                    try:
                        os.fsencode(value)
                    except UnicodeError:
                        problem = "entry %d is not representable as a filesystem path" % index
                if problem:
                    break
        if problem:
            return None, None, [], "the grant file %s has invalid `%s`: %s" % (path, key, problem)
    grants = data.get("grants", [])
    writes = data.get("writes", [])
    network = data.get("network", [])
    if not grants:
        return None, None, [], "the grant file %s carries no `grants` entries" % path
    return grants, writes, network, None


def checker_path():
    """The single-source checker: beside lane.py in the vault's delegate skill directory."""
    roots = []
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project:
        roots.append(os.path.expanduser(project))
    roots.append(os.path.dirname(os.path.dirname(HERE)))   # …/<vault>/.claude/hooks → <vault>
    for root in roots:
        candidate = os.path.join(root, ".claude", "skills", "delegate", "lane-fence.py")
        if os.path.isfile(candidate):
            return candidate
    return None


def checker(path):
    """Import lane-fence.py by path (its name is not an identifier) — handsoff-gate.py's shape for
    the watermark module. One process, one decision, no second interpreter start."""
    spec = importlib.util.spec_from_file_location("lane_fence", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else None
    except ValueError:
        event = None
    if not isinstance(event, dict):
        if armed(""):
            allow_open("", "unreadable payload (%d bytes)" % len(raw))
        return
    name = event.get("hook_event_name")
    if name is not None and name != "PreToolUse":
        note("ignoring event %s (registered for PreToolUse only)" % name)
        return
    sid = event.get("session_id") or ""
    if not armed(sid):
        return
    if (event.get("tool_name") or "Bash") != "Bash":
        return                                  # the matcher scopes this to Bash; this is the belt
    tool_input = event.get("tool_input")
    command = tool_input.get("command") or "" if isinstance(tool_input, dict) else ""

    run, problem = resolve_run(sid)
    if problem:
        deny_no_grants(sid, command, problem)
        return
    grants, writes, network, problem = load_grants(grants_path(run))
    if problem:
        deny_no_grants(sid, command, problem)
        return
    path = checker_path()
    if not path:
        allow_open(sid, "no lane-fence.py under CLAUDE_PROJECT_DIR or beside %s" % HERE)
        return
    try:
        module = checker(path)
    except Exception as exc:
        allow_open(sid, "checker %s unusable (%s: %s)" % (path, type(exc).__name__, exc))
        return
    # `handsoff.py grants` is the ONE command that widens a grant, and a new path is by definition
    # outside the current grants (register 2026-09-07, fix 3). Exempt exactly that subcommand — no
    # `;`, `&&`, `|` or newline appended — and log it as a `grant-change` event so a self-grant stays
    # visible; every other command, `handsoff.py`'s other subcommands included, is checked. This
    # hook and the checker are the single source and ship together; if a version-skewed checker
    # lacks the helper, the exemption simply does not apply (the command is checked as normal).
    try:
        grant_change = module.is_grant_change(command)
    except Exception:
        grant_change = False
    if grant_change:
        note("grant change exempt (register fix 3): %s" % command[:CMD_HEAD])
        log_event(sid, "grant-change", command[:CMD_HEAD], command)
        return
    try:
        action, reason = module.check(event, [module.norm(p) for p in grants],
                                      [module.norm(p) for p in writes], head=True, network=network)
    except Exception as exc:
        allow_open(sid, "checker %s unusable (%s: %s)" % (path, type(exc).__name__, exc))
        return
    if action != "deny":
        record_unplaced(module, event, run)     # log-only (owner decision 2026-10-23); never changes the silence
        return                                  # cleared: silence, never an explicit allow
    emit(reason)
    log_event(sid, "deny", command[:CMD_HEAD], command)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:      # fail-open: a broken guard must never block a head
        sys.stderr.write("[head-fence] %s: %s\n" % (type(exc).__name__, exc))
    sys.exit(0)
