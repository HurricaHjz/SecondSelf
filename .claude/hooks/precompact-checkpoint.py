#!/usr/bin/env python3
"""precompact-checkpoint.py — PreCompact checkpoint and SessionStart(compact) re-brief.

Registered for BOTH events; the branch is taken on the stdin fields `hook_event_name` and
`source`, never on which matcher fired.

PreCompact  — writes <state>/<session>-<YYYYMMDD-HHMMSS>-precompact.md, short sections first
              so a capped re-brief keeps them: the session header (trigger, the context figure
              computed by context-watermark.py — imported, one implementation — in the text its
              prompt line shows, the attended path's for an attended session), the fixed
              instruction, the last five log headings, the session's role/style state, every
              open ingest run with its last event line, then the two lists — spawn records
              touched and vault files modified SINCE THE SESSION STARTED (the first timestamp
              in the transcript head; 24 h when none is readable, and the heading says which),
              each capped. Appends `ts session PreCompact trigger context path` (tabs) to
              <state>/events.log — the compaction series that re-derives the bands.
SessionStart — logs EVERY event as `ts session SessionStart <source or missing>` to the same
              events.log (a trigger that never fires is then diagnosable), then, only when
              source == "compact", injects the newest checkpoint for THIS session as
              additionalContext (path line + body, capped); none for the session → one line
              saying so, naming the state dir. Any other source injects nothing.

Every section degrades to `n/a (<reason>)` on its own premise failure; a missing state dir is
created; a write failure goes to stderr with exit 0 (a stub beats nothing). stdout carries JSON
only when injecting context. The hook copies paths and single record lines, never file bodies.

Knobs (env, each with the vault-local default):
  AIMYTH_STATE_DIR       ~/.aimyth/handoffs        AIMYTH_INGEST_RUNS    ~/.llm-wiki/ingest-runs
  AIMYTH_SPAWN_RECORDS   ~/.llm-wiki/spawn-records AIMYTH_ROLE_STATE_DIR ~/.cache/aimyth/role-style
  (context-watermark.py's own knobs apply to the context figure.)
"""
import sys
sys.dont_write_bytecode = True   # the import below must never leave bytecode beside the hooks
import collections
import datetime
import importlib.util
import json
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FALLBACK_S = 24 * 3600   # window when no session start is readable; set by judgement, unmeasured (design v1.1)
VAULT_CAP = 40           # bound on listed vault paths (design v1.1); a session touches a few dozen
SPAWN_CAP = 20           # bound on listed spawn records (design v1.1); a run spawns about a dozen lanes
LINE_CAP = 300           # bound on each quoted record line
BODY_CAP = 7168          # bound on the re-brief BODY bytes (design v1.2): the JSON on stdout escapes non-ASCII to six bytes each, and this vault's log lines are dense with — and ·, so 7,168 keeps the worst case (~9.3 kB) inside the harness's ~10 kB per-hook cap
HEAD_BYTES = 64 * 1024   # bound on the transcript head read for the session start; the first timestamped record is in the first few lines
LOG_TAIL = 5
RUN_CLOSE_RE = re.compile(rb'"event"\s*:\s*"run_close"')
HEAD_RE = re.compile(rb"^## \[")
INSTRUCTION = (
    "Re-read this file and every record it names (run ledgers, spawn records, the role/style "
    "state file) and verify each against disk before acting on it: a listed run may have closed, "
    "a listed lane may have reported, a listed file may have changed since this checkpoint was "
    "written. The transcript is not the durable memory; the vault, the ledgers and the spawn "
    "records are. Continue from the disk state, not from the compaction summary, and say in the "
    "first reply after compaction which checkpoint was read.")


def _env_dir(name, default):
    return os.path.expanduser(os.environ.get(name) or default)


def state_dir():
    return _env_dir("AIMYTH_STATE_DIR", os.path.join("~", ".aimyth", "handoffs"))


def sid_safe(sid):
    return re.sub(r"[^A-Za-z0-9._-]", "-", sid or "") or "unknown"


def _now_str(now):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now))


def _truncate(s):
    return s if len(s) <= LINE_CAP else s[:LINE_CAP] + "…"


def _last_line_of(data):
    for line in reversed(data.split(b"\n")):
        if line.strip():
            return _truncate(line.decode("utf-8", "replace").strip())
    return "(empty)"


def _tail_line(path, nbytes=8192):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - nbytes))
            return _last_line_of(f.read())
    except OSError as e:
        return "n/a (unreadable: %s)" % e.strerror


def _when(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


# ---------------------------------------------------------------- the window
def session_start(tp):
    """Epoch of the first timestamped record in the transcript head, or None."""
    if not tp:
        return None
    tp = os.path.expanduser(tp)
    if not os.path.isfile(tp):
        return None
    try:
        with open(tp, "rb") as f:
            head = f.read(HEAD_BYTES)
    except OSError:
        return None
    for line in head.split(b"\n"):
        if b'"timestamp"' not in line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue   # the last line of the head may be torn
        ts = rec.get("timestamp") if isinstance(rec, dict) else None
        if not isinstance(ts, str):
            continue
        try:
            dt = datetime.datetime.fromisoformat(ts[:-1] + "+00:00" if ts.endswith("Z") else ts)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.timestamp()
    return None


def recent_window(tp, now):
    """(since_epoch, label): the session start, else the 24 h fallback that says so."""
    start = session_start(tp)
    if start is None:
        return now - FALLBACK_S, "last 24 h — no session start found"
    return start, "since " + time.strftime("%Y-%m-%dT%H:%M%z", time.localtime(start))


# ---------------------------------------------------------------- sections
def sec_context(tp, sid):
    """(text for the header, context int or None) via the watermark module, selected as its
    prompt line is: the attended text for an attended session, else the shared render()."""
    try:
        spec = importlib.util.spec_from_file_location(
            "context_watermark", os.path.join(HERE, "context-watermark.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        return "n/a (watermark module unavailable: %s: %s)" % (type(e).__name__, e), None
    m = mod.measure(tp)
    w = mod.window()
    text = mod.render_attended(m, w) if mod.attended(sid, w) else mod.render(m, w)
    return text, m.get("context")


def sec_open_runs(d):
    if not os.path.isdir(d):
        return "n/a (directory missing: %s)" % d
    names = sorted(n for n in os.listdir(d) if n.startswith("run-") and n.endswith(".jsonl"))
    if not names:
        return "none (no run ledgers in %s)" % d
    out = []
    for n in names:
        p = os.path.join(d, n)
        try:
            with open(p, "rb") as f:
                data = f.read()
        except OSError as e:
            out.append("- %s\n  n/a (unreadable: %s)" % (p, e.strerror))
            continue
        if RUN_CLOSE_RE.search(data):
            continue
        out.append("- %s\n  last: %s" % (p, _last_line_of(data)))
    return "\n".join(out) if out else "none open (%d ledgers, all closed)" % len(names)


def sec_spawn_records(d, since):
    if not os.path.isdir(d):
        return "n/a (directory missing: %s)" % d
    hits, total = [], 0
    for root, dirs, files in os.walk(d):
        for n in files:
            p = os.path.join(root, n)
            try:
                mt = os.stat(p).st_mtime
            except OSError:
                continue
            total += 1
            if mt >= since:
                hits.append((mt, p))
    if not hits:
        return "none touched in the window (%d files older)" % total
    hits.sort(reverse=True)
    out = ["- %s (modified %s)\n  last: %s" % (p, _when(mt), _tail_line(p)) for mt, p in hits[:SPAWN_CAP]]
    if len(hits) > SPAWN_CAP:
        out.append("… and %d more" % (len(hits) - SPAWN_CAP))
    return "\n".join(out)


def sec_vault_files(cwd, since):
    if not cwd or not os.path.isdir(cwd):
        return "n/a (cwd missing: %s)" % (cwd or "none given")
    hits = []
    for rel in ("wiki", ".claude", "output"):
        base = os.path.join(cwd, rel)
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [x for x in dirs if x not in ("__pycache__", ".git", "node_modules")]
            for n in files:
                p = os.path.join(root, n)
                try:
                    mt = os.stat(p).st_mtime
                except OSError:
                    continue
                if mt >= since:
                    hits.append((mt, os.path.relpath(p, cwd)))
    for n in ("CLAUDE.md", "CUSTOMISATION.md", "IDEAS.md"):
        p = os.path.join(cwd, n)
        try:
            mt = os.stat(p).st_mtime
        except OSError:
            continue
        if mt >= since:
            hits.append((mt, n))
    if not hits:
        return "none in the window"
    hits.sort(reverse=True)
    out = ["- %s (%s)" % (rel, _when(mt)) for mt, rel in hits[:VAULT_CAP]]
    if len(hits) > VAULT_CAP:
        out.append("… and %d more" % (len(hits) - VAULT_CAP))
    return "\n".join(out)


def sec_log_tail(cwd):
    if not cwd:
        return "n/a (no cwd given)"
    p = os.path.join(cwd, "wiki", "log.md")
    if not os.path.isfile(p):
        return "n/a (no wiki/log.md under %s)" % cwd
    tail = collections.deque(maxlen=LOG_TAIL)
    try:
        with open(p, "rb") as f:
            for line in f:
                if HEAD_RE.match(line):   # listed without the `## ` so they never read as sections
                    tail.append("- " + line.decode("utf-8", "replace").rstrip()[3:])
    except OSError as e:
        return "n/a (unreadable: %s)" % e.strerror
    return "\n".join(tail) if tail else "n/a (no `## [` headings in %s)" % p


def sec_role_state(sid):
    p = os.path.join(_env_dir("AIMYTH_ROLE_STATE_DIR", os.path.join("~", ".cache", "aimyth", "role-style")),
                     sid_safe(sid) + ".json")
    if not os.path.isfile(p):
        return "n/a (no state file at %s)" % p
    try:
        with open(p, encoding="utf-8") as f:
            raw = f.read().strip()
    except OSError as e:
        return "n/a (unreadable: %s)" % e.strerror
    return "%s\n```json\n%s\n```" % (p, raw)


# ---------------------------------------------------------------- PreCompact
def build_checkpoint(ev, now):
    sid = ev.get("session_id") or ""
    tp = ev.get("transcript_path")
    cwd = ev.get("cwd")
    trigger = ev.get("trigger") or "unknown"
    custom = ev.get("custom_instructions") or ""
    ctx_text, ctx = sec_context(tp, sid)
    since, label = recent_window(tp, now)
    header = "\n".join([
        "# Pre-compaction checkpoint", "",
        "## Session",
        "- session: %s" % (sid or "n/a (no session_id)"),
        "- written: %s" % _now_str(now),
        "- trigger: %s (custom instructions: %s)" % (trigger, custom.strip() or "none"),
        "- transcript: %s" % (tp or "n/a (no transcript_path)"),
        "- cwd: %s" % (cwd or "n/a (no cwd)"),
        "- %s" % ctx_text,
    ])
    body = "\n\n".join([   # short sections first: a capped re-brief keeps them (design v1.1)
        header,
        "## Instruction\n" + INSTRUCTION,
        "## Log tail\n" + sec_log_tail(cwd),
        "## Role/style state\n" + sec_role_state(sid),
        "## Open runs\n" + sec_open_runs(_env_dir("AIMYTH_INGEST_RUNS", os.path.join("~", ".llm-wiki", "ingest-runs"))),
        "## Spawn records (%s)\n%s" % (label, sec_spawn_records(_env_dir("AIMYTH_SPAWN_RECORDS", os.path.join("~", ".llm-wiki", "spawn-records")), since)),
        "## Vault files modified (%s)\n%s" % (label, sec_vault_files(cwd, since)),
    ]) + "\n"
    return body, ctx, trigger


def write_checkpoint(state, sid, now, body):
    os.makedirs(state, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    path = os.path.join(state, "%s-%s-precompact.md" % (sid_safe(sid), stamp))
    n = 2
    while os.path.exists(path):   # two compactions in one second: never clobber
        path = os.path.join(state, "%s-%s-%d-precompact.md" % (sid_safe(sid), stamp, n))
        n += 1
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(body)
    os.replace(tmp, path)   # atomic: a concurrent re-brief never reads a torn file
    return path


def log_event(state, fields):
    try:
        os.makedirs(state, exist_ok=True)
        with open(os.path.join(state, "events.log"), "a", encoding="utf-8") as f:
            f.write("\t".join(str(x) for x in fields) + "\n")
    except OSError as e:
        sys.stderr.write("[precompact-checkpoint] events.log append failed under %s: %s\n" % (state, e))


def do_precompact(ev):
    now = time.time()
    body, ctx, trigger = build_checkpoint(ev, now)
    state = state_dir()
    try:
        path = write_checkpoint(state, ev.get("session_id"), now, body)
        sys.stderr.write("[precompact-checkpoint] wrote %s\n" % path)
    except OSError as e:
        sys.stderr.write("[precompact-checkpoint] checkpoint write failed under %s: %s\n" % (state, e))
        path = "unwritten"
    log_event(state, [_now_str(now), sid_safe(ev.get("session_id")), "PreCompact", trigger,
                      ctx if ctx is not None else "unmetered", path])


# ---------------------------------------------------------------- SessionStart
def newest_checkpoint(state, sid):
    prefix, suffix = sid_safe(sid) + "-", "-precompact.md"
    best = None
    try:
        names = os.listdir(state)
    except OSError:
        return None
    for n in names:
        if not (n.startswith(prefix) and n.endswith(suffix)):
            continue
        p = os.path.join(state, n)
        try:
            key = (os.stat(p).st_mtime, n)
        except OSError:
            continue
        if best is None or key > best[0]:
            best = (key, p)
    return best[1] if best else None


def _cap(body):
    raw = body.encode("utf-8")
    if len(raw) <= BODY_CAP:
        return body
    cut = raw[:BODY_CAP].decode("utf-8", "ignore")
    if "\n" in cut:
        cut = cut[:cut.rfind("\n")]
    return cut + "\n… [truncated: %d of %d bytes shown; read the file for the rest]" % (
        len(cut.encode("utf-8")), len(raw))


def do_rebrief(ev, state):
    sid = ev.get("session_id") or ""
    path = newest_checkpoint(state, sid)
    if path is None:
        text = ("[precompact-checkpoint] Compaction occurred but no checkpoint exists for session %s "
                "in %s. Fall back to the latest hand-off document there, if any, and verify against "
                "disk before continuing; the transcript is not the durable memory." % (sid_safe(sid), state))
    else:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                body = f.read()
        except OSError as e:
            body = "n/a (checkpoint unreadable: %s)" % e.strerror
        text = ("[precompact-checkpoint] Compaction re-brief: read %s (reproduced below) and the "
                "records it names; verify each against disk before acting.\n%s" % (path, _cap(body)))
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": text}}))


def do_sessionstart(ev):
    state = state_dir()
    source = ev.get("source")
    log_event(state, [_now_str(time.time()), sid_safe(ev.get("session_id")), "SessionStart",
                      source if isinstance(source, str) and source else "missing"])
    if source == "compact":
        do_rebrief(ev, state)


def main():
    raw = sys.stdin.read()
    try:
        ev = json.loads(raw) if raw.strip() else None
    except ValueError:
        return
    if not isinstance(ev, dict):
        return
    name = ev.get("hook_event_name")
    if name == "PreCompact":
        do_precompact(ev)
    elif name == "SessionStart":
        do_sessionstart(ev)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:   # fail-safe: never block compaction or a session start
        sys.stderr.write("[precompact-checkpoint] %s: %s\n" % (type(e).__name__, e))
    sys.exit(0)
