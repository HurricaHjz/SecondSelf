#!/usr/bin/env python3
"""test_head_model.py: the legs of the head-model check at gate and boundary (decided line
DW-20261021-1) in handsoff.py.

Usage: python3 -B test_head_model.py [--target PATH/handsoff.py] [--only H01,H07]
The target defaults to the handsoff.py beside this file. Every leg runs in its own fixture under
one temporary root (LLM_WIKI_STORE, AIMYTH_STATE_DIR, AIMYTH_PROJECTS_DIR, CLAUDE_PROJECT_DIR and
HOME all point into it), with a planted head transcript and a dead pid for the head; no model
session, account reading or live store is touched, and the one process a leg may start in
place of a harness is /usr/bin/true.

The mode and the read budget are module constants (MODEL_CHECK_MODE, MODEL_CHECK_BUDGET_S): a
leg sets them by loading the target as a module in a child process and assigning them before
main() runs, so production code carries no test hook. A target without the check (the base)
takes the same assignments and ignores them, which is how its legs report what the base does.

The suite ends `PASS n/n` or `FAIL k/n` and exits 0 or 1; a broken premise prints
`PROBE FAILED: <what>` and exits 2.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
METER = ("billed (list 2001-01-01) · head $12.34 · lanes $4.22 · session $16.56 · rewrites 3 "
         "($0.30) · tool uses/call head 2.00 lanes 4.00 · delegation multi (owner) · lanes 1 "
         "(reasons: (a)×1 (b)×0 (c)×0 (d)×0, none×0) · metered 1 of 1")
OPUS, OLD, SONNET, HAIKU = ("claude-opus-5-5", "claude-opus-4-8", "claude-sonnet-5-5",
                            "claude-haiku-4-5-20251001")
UNVERIFIED_TAIL = "carrying on marked unverified"

# The child process: load the target as a module, set the two constants, then run main() on the
# given argv ("cli") or call one function and print its result as JSON ("call").
RUNNER = r"""
import importlib.util, json, sys
target, mode, budget, kind = sys.argv[1:5]
rest = sys.argv[5:]
spec = importlib.util.spec_from_file_location("handsoff_under_test", target)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
if mode != "-":
    mod.MODEL_CHECK_MODE = mode
if budget != "-":
    mod.MODEL_CHECK_BUDGET_S = float(budget)
if kind == "cli":
    sys.argv = [target] + rest
    mod.main()
elif kind == "start_guards":
    path, run = rest
    events = mod.read_record(path)[0]
    print(json.dumps(list(mod.start_guards(events, mod.last_index(events, ("head-exit",)), run=run))))
elif kind == "resume_head":
    path, run, sid, out = rest
    class A: pass
    a = A()
    a.run, a.harness_bin, a.config_dir, a.viewer_opened = run, "/usr/bin/true", None, True
    try:
        got = mod.resume_head(a, path, sid, 1.0, "fixture", out, {}, "error", 0.0, "fixture",
                              0.0, successor_fallback=True)
        print(json.dumps({"returned": None if got is None else "started"}))
    except SystemExit as exc:
        print(json.dumps({"returned": "exit %s" % exc.code}))
    except Exception as exc:
        print(json.dumps({"returned": "raised %s" % type(exc).__name__}))
elif kind == "check":
    path, sid = rest
    events = mod.read_record(path)[0]
    fn = getattr(mod, "head_model_check", None)
    print(json.dumps(None if fn is None else fn(events, sid)))
elif kind == "memory":
    # The alias candidates the check keeps, read from its own frame as it returns (reviewer
    # V-T2a's probe for Claim 14), beside the ids it reports.
    path, sid = rest
    events = mod.read_record(path)[0]
    fn = getattr(mod, "head_model_check", None)
    state = {}
    def trace(frame, event, arg):
        if frame.f_code.co_name == "head_model_check" and event == "return":
            state["candidates_kept"] = len(frame.f_locals.get("candidates") or {})
        return trace
    sys.settrace(trace)
    got = fn(events, sid) if fn else None
    sys.settrace(None)
    got = got if isinstance(got, dict) else {}
    state.update(verdict=got.get("verdict"), ids_kept=len(got.get("ids") or {}),
                 reason=got.get("reason"))
    print(json.dumps(state))
elif kind == "measure":
    sid, = rest
    try:
        got = mod.measure_head(sid)
        print(json.dumps({"returned": dict((k, got.get(k)) for k in
                                           ("context", "reason", "transcript"))}))
    except Exception as exc:
        print(json.dumps({"raised": type(exc).__name__}))
"""


def probe_failed(what):
    print("PROBE FAILED: %s" % what)
    sys.exit(2)


def stamp_local(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t))


def stamp_z(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03dZ" % int((t % 1) * 1000)


def dashed(path):
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(path))


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def manifest(folder):
    """{relative path: (sha256, mode)} for every file under folder, and whether a __pycache__
    folder exists anywhere in it."""
    out, cache = {}, False
    for d, dirs, files in os.walk(folder):
        if "__pycache__" in dirs:
            cache = True
        for name in files:
            p = os.path.join(d, name)
            out[os.path.relpath(p, folder)] = (sha(p), os.stat(p).st_mode & 0o7777)
    return out, cache


def dead_pid():
    proc = subprocess.Popen(["/usr/bin/true"])
    proc.wait()
    return proc.pid


HANDOFF = "\n".join([
    "# Fixture hand-off (a suite fixture, not a vault page)", "",
    "## Morning report (rewritten at every boundary)", "- **What shipped:** nothing yet.", "",
    "## In flight", "- nothing in flight.", "",
    "## Findings ledger (one line per warning · issue · finding · lesson)",
    "| Time | Phase | What | Evidence | Routing |", "|---|---|---|---|---|",
    "| 01:00 | 0 | fixture finding | fixture evidence | no action |", "",
    "## Trace (one row per decision and boundary)",
    "| Time | Item | Decision and its rule | Billed line | Waste so far |",
    "|---|---|---|---|---|", "| 01:02 | open → 1 | fixture decision | fixture | fixture |", ""])


class Fx:
    """One leg's fixture: a run record, a hand-off, a vault and a projects root."""

    def __init__(self, suite, tag, model=OPUS, attended=False):
        self.suite = suite
        self.root = tempfile.mkdtemp(prefix="leg-%s-" % tag, dir=suite.tmp)
        for sub in ("home", "store/spawn-records", "state", "projects", "vault", "handoffs"):
            os.makedirs(os.path.join(self.root, sub))
        self.run = "r%s" % tag.lower()
        self.rec = os.path.join(self.root, "store", "spawn-records", self.run + ".jsonl")
        self.ho = os.path.join(self.root, "handoffs", self.run + "-handoff.md")
        self.vault = os.path.realpath(os.path.join(self.root, "vault"))
        with open(self.ho, "w", encoding="utf-8") as handle:
            handle.write(HANDOFF)
        self.base = time.time() - 3600
        self.sid = "sid-%s-head" % tag.lower()
        self.env = dict(os.environ)
        for key in [k for k in self.env if k.startswith(("AIMYTH_", "LLM_WIKI_", "CLAUDE"))]:
            del self.env[key]
        self.env.update({
            "HOME": os.path.join(self.root, "home"),
            "LLM_WIKI_STORE": os.path.join(self.root, "store"),
            "AIMYTH_STATE_DIR": os.path.join(self.root, "state"),
            "AIMYTH_PROJECTS_DIR": os.path.join(self.root, "projects"),
            "CLAUDE_PROJECT_DIR": self.vault, "AIMYTH_HOOKS_DIR": suite.hooks,
            "AIMYTH_LANE_PY": os.path.join(suite.folder, "lane.py"),
            "AIMYTH_BANDS": "60,80,90", "AIMYTH_CONTEXT_WINDOW": "1000000",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_CONFIG_NOSYSTEM": "1",
            # A failing usage stand-in, so no command a leg drives reads the account (a
            # boundary, a close and a run-open start the usage reader from line 2 on).
            "USAGE_CLAUDE_BIN": "/usr/bin/false", "USAGE_CODEX_BIN": "/usr/bin/false"})
        self.append({"ts": stamp_local(self.base), "run": self.run, "event": "run-open",
                     "session": "sid-%s-setup" % tag.lower(), "head": "fixture head",
                     "regime": "multi", "regime_src": "owner", "handoff": os.path.realpath(self.ho),
                     "detail": "fixture run", "pid_src": "none", "envelope_usd": 200.0,
                     "model": model, "model_src": "arg"})
        if attended:
            self.sid = "sid-%s-setup" % tag.lower()
        else:
            self.start("head-successor", 10, model)

    def append(self, ev):
        with open(self.rec, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(ev, ensure_ascii=False) + "\n")

    def start(self, kind, offset, model, sid=None):
        ev = {"ts": stamp_local(self.base + offset), "run": self.run, "event": kind,
              "session_id": sid or self.sid, "pid": self.suite.pid, "effort": "max",
              "model_src": "arg" if model else "harness default (no --model)",
              "effort_src": "arg"}
        if model:
            ev["model"] = model
        self.append(ev)

    def lane(self, name, alias, open_off, close_off, served, expected=OPUS):
        self.append({"ts": stamp_local(self.base + open_off), "run": self.run, "lane": name,
                     "event": "lane-open", "harness": "claude", "class": "builder",
                     "model": alias, "effort": "max"})
        self.append({"ts": stamp_local(self.base + close_off), "run": self.run, "lane": name,
                     "event": "lane-closed", "exit_code": 0,
                     "fallback": {"detected": served != [expected], "models": served + [HAIKU],
                                  "non_helper": served, "expected": expected,
                                  "rule": "alias map and count", "reason": None}})

    def transcript_path(self, sid=None):
        folder = os.path.join(self.root, "projects", dashed(self.vault))
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, "%s.jsonl" % (sid or self.sid))

    def transcript(self, rows, sid=None, raw=None):
        """rows: (offset seconds, model) or (offset, model, extra fields); raw: lines as given."""
        with open(self.transcript_path(sid), "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(self.record(*row) + "\n")
            for line in raw or []:
                handle.write(line)

    def record(self, offset, model, extra=None):
        rec = {"type": "assistant", "isSidechain": False, "sessionId": self.sid,
               "timestamp": stamp_z(self.base + offset),
               "message": {"role": "assistant", "model": model,
                           "usage": {"input_tokens": 1000, "cache_read_input_tokens": 0,
                                     "cache_creation_input_tokens": 0, "output_tokens": 10},
                           "content": [{"type": "text", "text": "fixture"}]}}
        rec.update(extra or {})
        return json.dumps(rec)

    def events(self):
        with open(self.rec, encoding="utf-8") as handle:
            return [json.loads(x) for x in handle if x.strip()]

    def of(self, kind, **match):
        return [e for e in self.events() if e.get("event") == kind
                and all(e.get(k) == v for k, v in match.items())]

    def call(self, kind, args, mode="trial", budget="-", extra_env=None):
        env = dict(self.env)
        env.update(extra_env or {})
        t0 = time.monotonic()
        proc = subprocess.run([sys.executable, "-B", "-c", RUNNER, self.suite.target, mode,
                               budget, kind] + list(args), env=env, cwd=self.root,
                              capture_output=True, text=True, timeout=300)
        return proc.returncode, proc.stdout + proc.stderr, time.monotonic() - t0

    def cli(self, args, mode="trial", budget="-", extra_env=None):
        return self.call("cli", args, mode, budget, extra_env)

    def gate(self, mode="trial", item="item2", budget="-", extra=()):
        return self.cli(["gate", "--run", self.run, "--to", item, "--meter-line", METER]
                        + list(extra), mode, budget)

    def boundary(self, mode="trial", commit=None, extra=()):
        args = ["boundary", "--run", self.run, "--from", "item1", "--to", "item2",
                "--disposition", "fixture phase closed", "--waste", "none", "--next", "item2",
                "--meter-line", METER] + list(extra)
        if commit:
            args += ["--commit", commit]
        return self.cli(args, mode)

    def console(self):
        """(exit, lines) of one plain frame of the console (watch.py beside the target) on this
        fixture's run; --once writes no timeline report."""
        env = dict(self.env, AIMYTH_WATCH_NOTIFY="0", COLUMNS="200", LINES="60")
        proc = subprocess.run([sys.executable, "-B", os.path.join(self.suite.folder, "watch.py"),
                               "--vault", self.vault, "--run", self.run, "--once", "--plain",
                               "--no-notify"], env=env, cwd=self.root, capture_output=True,
                              text=True, timeout=120)
        return proc.returncode, (proc.stdout + proc.stderr).splitlines()

    def check(self, mode="trial"):
        code, out, _ = self.call("check", [self.rec, self.sid], mode)
        try:
            got = json.loads(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"verdict": "runner failed", "reason": out[-300:]}
        # None: the check does not apply, or the target has none (the base).
        return got if isinstance(got, dict) else {"verdict": "no check (None)"}


class Suite:
    def __init__(self, target, only):
        self.target = os.path.realpath(target)
        if not os.path.isfile(self.target):
            probe_failed("no target %s" % self.target)
        self.folder = os.path.dirname(self.target)
        self.hooks = os.environ.get("AIMYTH_HOOKS_DIR") or os.path.realpath(
            os.path.join(self.folder, os.pardir, os.pardir, "hooks"))
        if not os.path.isfile(os.path.join(self.hooks, "context-watermark.py")):
            probe_failed("no context-watermark.py under %s (set AIMYTH_HOOKS_DIR)" % self.hooks)
        self.tmp = tempfile.mkdtemp(prefix="test_head_model-")
        self.only = only
        self.pid = dead_pid()
        self.results = []

    def leg(self, name, ok, detail):
        self.results.append((name, bool(ok)))
        print("%s %s · %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)

    def want(self, name):
        return not self.only or name.split(".")[0] in self.only


def mc_of(ev):
    mc = ev.get("model_check") if isinstance(ev, dict) else None
    return mc if isinstance(mc, dict) else {}


def last(rows):
    return rows[-1] if rows else {}


def legs(s):
    # H01: a swap on an explicit id. Enforce refuses with 11 and writes the stop and no gate; trial
    # allows, writes one observation, prints nothing about it (silent trial, D6), and marks the
    # gate event. Base: the gate allows and carries no field (the leg fails on base).
    if s.want("H01"):
        for mode in ("enforce", "trial"):
            fx = Fx(s, "h01" + mode[0])
            fx.transcript([(20, OPUS), (30, OPUS), (40, OLD)])
            code, out, _ = fx.gate(mode)
            stops, gates = fx.of("stop-condition", which="model"), fx.of("gate")
            obs = fx.of("observation", what="model check would refuse")
            fu = mc_of(last(stops)).get("first_unexpected") or last(stops).get("first_unexpected")
            if mode == "enforce":
                ok = (code == 11 and len(stops) == 1 and not gates and isinstance(fu, dict)
                      and fu.get("id") == OLD and fu.get("line") == 3 and "REFUSED" in out)
            else:
                ok = (code == 0 and len(obs) == 1 and not stops and len(gates) == 1 and
                      mc_of(gates[0]).get("verdict") == "confirmed-swap" and "SWAP" not in out)
            s.leg("H01.%s" % mode, ok, "exit %d · stops %d · gates %d · observations %d · gate "
                  "verdict %s" % (code, len(stops), len(gates), len(obs),
                                  mc_of(last(gates)).get("verdict")))

    # H02: clean, with its positive control on the same run (one record flipped).
    if s.want("H02"):
        fx = Fx(s, "h02")
        fx.transcript([(20, OPUS), (30, OPUS), (40, OPUS)])
        code, out, _ = fx.gate("enforce")
        mc = mc_of(last(fx.of("gate")))
        clean = (code == 0 and mc.get("verdict") == "verified" and mc.get("primary_n") == 3
                 and mc.get("unexpected_n") == 0 and "model-check" not in out)
        fx.transcript([(20, OPUS), (30, OLD), (40, OPUS)])
        control = fx.check("enforce").get("verdict")
        s.leg("H02", clean and control == "confirmed-swap",
              "exit %d · verdict %s · primary_n %s · unexpected %s · control (one record flipped)"
              " %s" % (code, mc.get("verdict"), mc.get("primary_n"), mc.get("unexpected_n"),
                       control))

    # H03: the cases it cannot decide; each carries on marked unverified with its own reason, in
    # enforce mode too, and never reads verified.
    if s.want("H03"):
        cases = [
            ("missing", None, None, "no readable transcript"),
            ("empty", [], None, "no primary record"),
            ("malformed", [], ['{"type": "assistant", "message": {"model": \n'] * 3,
             "malformed record"),
            ("synthetic", [(20, "<synthetic>")], None, "no primary record"),
            ("helper", [(20, HAIKU)], None, "helper-family id"),
            ("nomodel", [(20, OPUS)], None, "carries no readable model"),
            ("unmapped", [(20, OPUS)], None, "is not in prices.json's map"),
            ("budget", [(20, OPUS), (30, OLD)], None, "budget"),
            ("untimed", [(20, OPUS), (30, OPUS, {"timestamp": "not a time"})], None,
             "no readable timestamp"),
            ("onebad", [(20, OPUS)], ['{"type": "assistant", "broken\n'], "malformed record"),
            ("torn", [], ['{"type": "assistant", "isSidechain": false, "message": {"model": "cl'],
             "no primary record"),
        ]
        for name, rows, raw, why in cases:
            model = None if name == "nomodel" else "zeta" if name == "unmapped" else OPUS
            fx = Fx(s, "h03" + name[:4], model=model)
            if rows is not None or raw is not None:
                fx.transcript(rows or [], raw=raw)
            code, out, _ = fx.gate("enforce", budget="0" if name == "budget" else "-")
            mc = mc_of(last(fx.of("gate")))
            line = [x for x in out.splitlines() if x.startswith("model-check: UNVERIFIED")]
            ok = (code == 0 and mc.get("verdict") == "unverified" and why in (mc.get("reason") or "")
                  and len(line) == 1 and UNVERIFIED_TAIL in line[0] and "verified (" not in out)
            s.leg("H03.%s" % name, ok, "exit %d · verdict %s · reason %s" % (
                code, mc.get("verdict"), (mc.get("reason") or "none")[:110]))
        # prices.json unreadable: a copy of the target beside a broken map.
        fx = Fx(s, "h03pric")
        fx.transcript([(20, OPUS), (30, OLD)])
        alt = os.path.join(fx.root, "skill")
        os.makedirs(alt)
        shutil.copy2(s.target, os.path.join(alt, "handsoff.py"))
        with open(os.path.join(alt, "prices.json"), "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        keep, s.target = s.target, os.path.join(alt, "handsoff.py")
        try:
            code, out, _ = fx.gate("enforce")
        finally:
            s.target = keep
        mc = mc_of(last(fx.of("gate")))
        ok = code == 0 and mc.get("verdict") == "unverified" and \
            "prices.json" in (mc.get("reason") or "")
        # A torn trailing record (a live append caught mid-line): coverage ends before it
        # (design-rev2: an incomplete trailing record is buffered until complete), so the
        # complete records before it are judged and the partial one is not counted.
        tfx = Fx(s, "h03tail")
        tfx.transcript([(20, OPUS), (30, OPUS)],
                       raw=['{"type": "assistant", "isSidechain": false, "message": {"model": "cl'])
        tmc = tfx.check("enforce")
        s.leg("H03.torntail", tmc.get("verdict") == "verified" and tmc.get("primary_n") == 2,
              "verdict %s · primary_n %s (the partial last line not counted)"
              % (tmc.get("verdict"), tmc.get("primary_n")))
        s.leg("H03.prices", ok, "exit %d · verdict %s · reason %s%s" % (
            code, mc.get("verdict"), (mc.get("reason") or "none")[:80],
            "" if ok else " · output %s" % out[-400:].replace("\n", " | ")))

    # H04: an alias expectation; another id confirms only with a lane opened on the same alias
    # after the first unexpected record that was served the alias's id (L6: opened, not closed,
    # after it); a lane served the new id is a stale map.
    if s.want("H04"):
        for name, lane, want in (("a", (50, 60, [OPUS]), "confirmed-swap"),
                                 ("b", None, "unverified"),
                                 ("c", (50, 60, [OLD]), "unverified"),
                                 ("d", (25, 60, [OPUS]), "unverified")):
            fx = Fx(s, "h04" + name, model="opus")
            fx.transcript([(20, OPUS), (30, OPUS), (40, OLD)])
            if lane:
                fx.lane("L1", "opus", lane[0], lane[1], lane[2])
            mc = fx.check("enforce")
            reason = mc.get("reason") or ""
            extra = {"b": "alias may have moved", "c": "stale map", "d": "alias may have moved"}
            ok = mc.get("verdict") == want and (name == "a" or extra[name] in reason)
            s.leg("H04.%s" % name, ok, "verdict %s · %s" % (mc.get("verdict"), reason[:110]))

    # H05: sidechain and synthetic records with other ids never count; control: the same id as
    # a non-sidechain record is caught.
    if s.want("H05"):
        fx = Fx(s, "h05")
        fx.transcript([(20, OPUS), (25, SONNET, {"isSidechain": True}), (30, "<synthetic>"),
                       (40, OPUS)])
        clean = fx.check("enforce")
        fx.transcript([(20, OPUS), (25, SONNET), (40, OPUS)])
        control = fx.check("enforce")
        s.leg("H05", clean.get("verdict") == "verified" and clean.get("primary_n") == 2 and
              control.get("verdict") == "confirmed-swap",
              "verdict %s (primary_n %s) · control %s" % (clean.get("verdict"),
                                                          clean.get("primary_n"),
                                                          control.get("verdict")))

    # H06: an owner-requested change opens an epoch; it never makes an earlier record clean.
    if s.want("H06"):
        fx = Fx(s, "h06")
        fx.start("head-resumed", 100, OLD)
        fx.transcript([(20, OPUS), (30, OPUS), (110, OLD), (120, OLD)])
        after = fx.check("enforce")
        fx.transcript([(20, OPUS), (30, OLD), (110, OLD), (120, OLD)])
        before = fx.check("enforce")
        s.leg("H06", after.get("verdict") == "verified" and before.get("verdict") ==
              "confirmed-swap" and (before.get("first_unexpected") or {}).get("line") == 2,
              "after the change %s · a record before it %s (line %s)" % (
                  after.get("verdict"), before.get("verdict"),
                  (before.get("first_unexpected") or {}).get("line")))

    # H07: the boundary. Enforce on a swap: no commit, no hand-off change, no phase-boundary,
    # the stop and exit 11 (M3). Trial on a swap and enforce on unverified: the commit is made,
    # marked on the phase-boundary (H1's provisional reading).
    if s.want("H07"):
        for name, mode, rows, want_code, want_commit, want_verdict in (
                ("enforce-swap", "enforce", [(20, OPUS), (40, OLD)], 11, False, None),
                ("trial-swap", "trial", [(20, OPUS), (40, OLD)], 0, True, "confirmed-swap"),
                ("unverified", "enforce", [(20, HAIKU)], 0, True, "unverified"),
                ("verified", "enforce", [(20, OPUS), (40, OPUS)], 0, True, "verified")):
            fx = Fx(s, "h07" + name[:3] + name[-3:])
            fx.transcript(rows)
            git = lambda *a: subprocess.run(["git", "-C", fx.vault] + list(a), env=fx.env,
                                            capture_output=True, text=True)
            git("init", "-q")
            with open(os.path.join(fx.vault, "page.md"), "w", encoding="utf-8") as handle:
                handle.write("fixture page\n")
            git("add", "-A")
            git("commit", "-q", "-m", "fixture base")
            with open(os.path.join(fx.vault, "page.md"), "a", encoding="utf-8") as handle:
                handle.write("work of the phase\n")
            n0 = git("rev-list", "--count", "HEAD").stdout.strip()
            h0 = sha(fx.ho)
            code, out, _ = fx.boundary(mode, commit="fixture checkpoint")
            n1 = git("rev-list", "--count", "HEAD").stdout.strip()
            pb = fx.of("phase-boundary")
            stops = fx.of("stop-condition", which="model")
            committed = n1 != n0
            if want_verdict is None:
                ok = (code == want_code and not committed and not pb and len(stops) == 1 and
                      sha(fx.ho) == h0 and mc_of(stops[0]).get("verdict") == "confirmed-swap")
            else:
                ok = (code == want_code and committed and len(pb) == 1 and
                      mc_of(pb[0]).get("verdict") == want_verdict and not stops)
                if want_verdict == "verified":      # must not fire: no stop and no line at all
                    ok = ok and "model-check" not in out
            s.leg("H07.%s" % name, ok, "exit %d · commits %s → %s · phase-boundary %d (verdict %s)"
                  " · model stops %d · hand-off %s" % (
                      code, n0, n1, len(pb), mc_of(last(pb)).get("verdict"), len(stops),
                      "unchanged" if sha(fx.ho) == h0 else "changed"))

    # H08: the latch, enforce only, in the two shared functions (M2's placement) and the
    # hand-off; the release from outside the head; and the trial control, where none refuses.
    if s.want("H08"):
        for mode in ("enforce", "trial"):
            fx = Fx(s, "h08" + mode[0])
            fx.transcript([(20, OPUS), (40, OLD)])
            fx.gate("enforce")      # the enforced stop on the record in both legs
            fx.append({"ts": stamp_local(fx.base + 60), "run": fx.run, "event": "head-exit",
                       "session_id": fx.sid, "pid": s.pid, "band": "80", "class": "band"})
            code, out, _ = fx.call("start_guards", [fx.rec, fx.run], mode)
            guard = json.loads(out.strip().splitlines()[-1]) if code == 0 else ["runner", out]
            code, out, _ = fx.call("resume_head", [fx.rec, fx.run, fx.sid,
                                                   os.path.join(fx.root, "head.out")], mode)
            refusals = fx.of("head-resume-refused", reason="model-stop")
            h0, n0 = sha(fx.ho), len(fx.events())
            hcode, hout, _ = fx.cli(["handoff", "--run", fx.run, "--inflight", "- from the head"],
                                    mode, extra_env={"AIMYTH_HANDSOFF": "1"})
            inside_kept = sha(fx.ho) == h0
            if mode == "enforce":
                rcode, rout, _ = fx.cli(["release-model-stop", "--run", fx.run, "--session", fx.sid,
                                         "--reason", "fixture release"], mode,
                                        extra_env={"AIMYTH_HANDSOFF": "1"})
                refused_inside = rcode == 2 and len(fx.events()) == n0
                rcode2, _, _ = fx.cli(["release-model-stop", "--run", fx.run, "--session", fx.sid,
                                       "--reason", "fixture release"], mode)
                released = rcode2 == 0 and len(fx.of("observation", what="model stop released")) == 1
                code3, out3, _ = fx.call("start_guards", [fx.rec, fx.run], mode)
                after = json.loads(out3.strip().splitlines()[-1]) if code3 == 0 else ["runner"]
                fx.call("resume_head", [fx.rec, fx.run, fx.sid, os.path.join(fx.root, "h2.out")],
                        mode)
                still = len(fx.of("head-resume-refused", reason="model-stop")) == 2
                ok = (guard[0] == "model-stop" and len(refusals) == 1 and hcode == 11 and
                      inside_kept and refused_inside and released and after[0] != "model-stop"
                      and still)
                detail = ("start_guards %s · resume refused %d · hand-off inside exit %d (%s) · "
                          "release inside refused %s · released outside %s · start_guards after "
                          "%s · resume after release refused %s" % (
                              guard[0], len(refusals), hcode,
                              "unchanged" if inside_kept else "changed", refused_inside, released,
                              after[0], still))
            else:
                ok = guard[0] != "model-stop" and not refusals and hcode != 11
                detail = "start_guards %s · resume refusals %d · hand-off exit %d" % (
                    guard[0], len(refusals), hcode)
            s.leg("H08.%s" % mode, ok, detail)

    # H09: durable. After a found swap the transcript is replaced by clean records: the next
    # gate still refuses (enforce); in trial the field stays confirmed and no second observation.
    if s.want("H09"):
        for mode in ("enforce", "trial"):
            fx = Fx(s, "h09" + mode[0])
            fx.transcript([(20, OPUS), (40, OLD)])
            fx.gate(mode)
            fx.transcript([(20, OPUS), (40, OPUS)])
            code, out, _ = fx.gate(mode, item="item3")
            if mode == "enforce":
                ok = code == 11 and len(fx.of("stop-condition", which="model")) == 2
            else:
                ok = (code == 0 and len(fx.of("observation", what="model check would refuse")) == 1
                      and mc_of(last(fx.of("gate"))).get("verdict") == "confirmed-swap")
            s.leg("H09.%s" % mode, ok, "exit %d on the clean transcript · stops %d · "
                  "observations %d" % (code, len(fx.of("stop-condition", which="model")),
                                       len(fx.of("observation", what="model check would refuse"))))

    # H10: time. A 64 MB transcript (size set by judgement) with the swap on its last line: the
    # check's own elapsed time inside 4.0 s and the whole gate call inside 5.0 s, and the same
    # for the boundary (L1). Measured, printed, never retried.
    if s.want("H10"):
        fx = Fx(s, "h10")
        # Every line a primary record carrying 4,000 characters of text, so the whole plant is
        # parsed (the worst case for the read; a real transcript's user lines are skipped).
        filler = fx.record(20, OPUS, {"message": {
            "role": "assistant", "model": OPUS, "content": [{"type": "text", "text": "x" * 4000}],
            "usage": {"input_tokens": 1000, "output_tokens": 10}}}) + "\n"
        with open(fx.transcript_path(), "w", encoding="utf-8") as handle:
            size = 0
            while size < 64 * 1024 * 1024:
                handle.write(filler)
                size += len(filler)
            handle.write(fx.record(3000, OLD) + "\n")
        size = os.path.getsize(fx.transcript_path())
        code, out, wall = fx.gate("enforce")
        stop = last(fx.of("stop-condition", which="model"))
        mc = mc_of(stop)
        elapsed = mc.get("elapsed_s")
        ok = code == 11 and isinstance(elapsed, (int, float)) and elapsed <= 4.0 and wall <= 5.0
        s.leg("H10.gate", ok, "%d bytes · exit %d · check %.3f s of 4.0 · whole gate call %.3f s of "
              "5.0 · bytes read %s" % (size, code, elapsed if isinstance(elapsed, (int, float))
                                        else -1, wall, mc.get("bytes_read")))
        fx2 = Fx(s, "h10b")
        shutil.copy2(fx.transcript_path(), fx2.transcript_path())
        code, out, wall = fx2.boundary("enforce")
        mc = mc_of(last(fx2.of("stop-condition", which="model")))
        elapsed = mc.get("elapsed_s")
        s.leg("H10.boundary", code == 11 and isinstance(elapsed, (int, float)) and elapsed <= 4.0
              and wall <= 5.0, "exit %d · check %s s · whole boundary call %.3f s of 5.0"
              % (code, elapsed, wall))

    # H11: the mode is one constant, its default trial (D6): a swap under the target's own
    # constant behaves as trial; no flag lowers or raises it.
    if s.want("H11"):
        fx = Fx(s, "h11")
        fx.transcript([(20, OPUS), (40, OLD)])
        code, out, _ = fx.gate(mode="-")
        obs = fx.of("observation", what="model check would refuse")
        fcode, fout, _ = fx.gate(mode="-", item="item3", extra=["--model-check", "enforce"])
        s.leg("H11", code == 0 and len(obs) == 1 and fcode == 2,
              "default constant: exit %d, trial observations %d · `--model-check` flag: exit %d"
              % (code, len(obs), fcode))

    # H12: dry runs print the verdict and write nothing (record and hand-off byte-identical).
    if s.want("H12"):
        for name, rows, mode in (("verified", [(20, OPUS)], "enforce"),
                                 ("unverified", [(20, HAIKU)], "enforce"),
                                 ("swap-enforce", [(20, OPUS), (40, OLD)], "enforce"),
                                 ("swap-trial", [(20, OPUS), (40, OLD)], "trial")):
            fx = Fx(s, "h12" + name[:3] + name[-3:])
            fx.transcript(rows)
            r0, h0 = sha(fx.rec), sha(fx.ho)
            gcode, gout, _ = fx.gate(mode, extra=["--dry-run"])
            bcode, bout, _ = fx.boundary(mode, extra=["--dry-run"])
            verdict = "confirmed-swap" if name.startswith("swap") else name
            shown = ("model-check %s" % verdict) in gout and ("model-check %s" % verdict) in bout
            s.leg("H12.%s" % name, gcode == 0 and bcode == 0 and shown and sha(fx.rec) == r0
                  and sha(fx.ho) == h0, "gate exit %d · boundary exit %d · verdict shown %s · "
                  "record %s · hand-off %s" % (gcode, bcode, shown,
                                               "unchanged" if sha(fx.rec) == r0 else "CHANGED",
                                               "unchanged" if sha(fx.ho) == h0 else "CHANGED"))

    # H13: the close's summary and the items held for the owner (H1's provisional reading).
    if s.want("H13"):
        fx = Fx(s, "h13")
        fx.transcript([(20, OPUS)])
        fx.gate("trial", item="item1")                       # verified
        fx.append({"ts": stamp_local(fx.base + 2000), "run": fx.run, "event": "item-done",
                   "items": ["item1"]})
        fx.gate("trial", item="item2")                       # verified: covers item1
        fx.append({"ts": stamp_local(fx.base + 2100), "run": fx.run, "event": "item-done",
                   "items": ["item2"]})
        with open(fx.transcript_path(), "a", encoding="utf-8") as handle:
            handle.write(fx.record(2050, HAIKU) + "\n")
        fx.gate("trial", item="item3")                       # unverified: item2 held
        fx.append({"ts": stamp_local(fx.base + 2200), "run": fx.run, "event": "item-done",
                   "items": ["item3"]})                      # no check after it: held
        code, out, _ = fx.cli(["close", "--run", fx.run, "--items", "fixture items",
                               "--meter-line", METER], "trial")
        rc = last(fx.of("run-close"))
        field = rc.get("model_checks") or {}
        held = dict((h.get("item"), h.get("why")) for h in field.get("held") or [])
        line = [x for x in out.splitlines() if x.startswith("close: model checks:")]
        ok = (code == 0 and field.get("verified") == 2 and field.get("unverified") == 1 and
              field.get("confirmed") == 0 and held == {"item2": "unverified",
                                                       "item3": "no check after it"}
              and len(line) == 1 and "2 verified, 1 unverified, 0 confirmed" in line[0])
        s.leg("H13", ok, "exit %d · run-close.model_checks %s · line %s" % (
            code, json.dumps(field)[:200], (line or ["none"])[0][:160]))

    # H14: an attended head (no starter start names its session) is left alone in enforce mode
    # too: no field, no line, no refusal (M1).
    if s.want("H14"):
        fx = Fx(s, "h14", attended=True)
        fx.transcript([(20, OPUS), (40, OLD)])
        code, out, _ = fx.gate("enforce")
        g = last(fx.of("gate"))
        s.leg("H14", code == 0 and g and "model_check" not in g and "model-check" not in out
              and not fx.of("stop-condition", which="model"),
              "exit %d · gate field %s · line %s" % (code, "model_check" in g,
                                                     "model-check" in out))

    # H15: twenty gates after a swap in trial: one observation (L6).
    if s.want("H15"):
        fx = Fx(s, "h15")
        fx.transcript([(20, OPUS), (40, OLD)])
        codes = [fx.gate("trial", item="item%d" % k)[0] for k in range(20)]
        obs = fx.of("observation", what="model check would refuse")
        s.leg("H15", codes == [0] * 20 and len(obs) == 1,
              "exits %s · observations %d" % (sorted(set(codes)), len(obs)))

    # H16: the verdict over mixed record classes (H2): any confirmable record confirms, whatever
    # the first unexpected record was. A first-unexpected-decides build fails each sub-leg.
    if s.want("H16"):
        cases = (("helper-first", OPUS, None, [(20, OPUS), (30, HAIKU), (40, OLD)]),
                 ("alias-first", "opus", (100, OPUS), [(20, OPUS), (30, OLD), (110, SONNET)]),
                 ("gap-first", None, (100, OPUS), [(20, OPUS), (110, OLD)]))
        for name, model, later, rows in cases:
            fx = Fx(s, "h16" + name[:5], model=model)
            if later:
                fx.start("head-resumed", later[0], later[1])
            fx.transcript(rows)
            mc = fx.check("enforce")
            s.leg("H16.%s" % name, mc.get("verdict") == "confirmed-swap",
                  "verdict %s · first unexpected %s" % (
                      mc.get("verdict"), (mc.get("first_unexpected") or {}).get("id")))

    # H17: the memory bound: forty distinct ids keep at most MODEL_CHECK_MAX_IDS (32) first
    # records and still confirm on the first unexpected one.
    if s.want("H17"):
        fx = Fx(s, "h17")
        fx.transcript([(20, OPUS)] + [(30 + k, "claude-other-%d-0" % k) for k in range(40)])
        mc = fx.check("enforce")
        s.leg("H17", mc.get("verdict") == "confirmed-swap" and len(mc.get("ids") or {}) == 32 and
              (mc.get("first_unexpected") or {}).get("id") == "claude-other-0-0",
              "verdict %s · ids kept %d" % (mc.get("verdict"), len(mc.get("ids") or {})))
        # H17.alias (reviewer V-T2a, Claim 14): forty distinct alias mismatches keep at most 32
        # candidates, as the ids do, and read unverified; control: five keep five, so the probe
        # reads the check's real map.
        got = {}
        for k in (40, 5):
            fx = Fx(s, "h17a%d" % k, model="opus")
            fx.transcript([(20, OPUS)] + [(30 + j, "claude-other-%d-0" % j) for j in range(k)])
            code, out, _ = fx.call("memory", [fx.rec, fx.sid], "enforce")
            try:
                got[k] = json.loads(out.strip().splitlines()[-1])
            except (ValueError, IndexError):
                got[k] = {"runner": out[-200:]}
        big, small = got[40], got[5]
        s.leg("H17.alias", isinstance(big.get("candidates_kept"), int) and
              big["candidates_kept"] <= 32 and big.get("verdict") == "unverified" and
              "more than 32 distinct ids" in (big.get("reason") or "") and
              small.get("candidates_kept") == 5,
              "forty: candidates kept %s, ids kept %s, verdict %s · control (five): candidates "
              "kept %s" % (big.get("candidates_kept"), big.get("ids_kept"), big.get("verdict"),
                           small.get("candidates_kept")))

    # H19 (reviewer V-T2a, R4 first bullet): an unreadable transcript. Gate and boundary carry on
    # marked unverified, write their event with the check, and never raise; the meter's read
    # (measure_head) returns unmetered. Control: the same transcript readable reads verified.
    if s.want("H19"):
        for seat in ("gate", "boundary"):
            fx = Fx(s, "h19" + seat[:4])
            fx.transcript([(20, OPUS)])
            control = fx.check("enforce").get("verdict")
            os.chmod(fx.transcript_path(), 0)
            try:
                code, out, _ = fx.gate("enforce") if seat == "gate" else fx.boundary("enforce")
                mcode, mout, _ = fx.call("measure", [fx.sid], "enforce")
            finally:
                os.chmod(fx.transcript_path(), 0o600)
            evs = fx.of("gate" if seat == "gate" else "phase-boundary")
            mc = mc_of(last(evs))
            line = [x for x in out.splitlines() if x.startswith("model-check: UNVERIFIED")]
            ok = (control == "verified" and code == 0 and len(evs) == 1 and
                  mc.get("verdict") == "unverified" and
                  "no readable transcript" in (mc.get("reason") or "") and len(line) == 1 and
                  UNVERIFIED_TAIL in line[0] and "Traceback" not in out)
            s.leg("H19.%s" % seat, ok, "control (readable) %s · exit %d · %s events %d · verdict "
                  "%s · traceback %s" % (control, code, seat, len(evs), mc.get("verdict"),
                                         "Traceback" in out))
            if seat == "gate":
                try:
                    meas = json.loads(mout.strip().splitlines()[-1])
                except (ValueError, IndexError):
                    meas = {"runner": mout[-200:]}
                back = meas.get("returned") or {}
                s.leg("H19.meter", mcode == 0 and back.get("context") is None and
                      "unreadable" in (back.get("reason") or "") and not back.get("transcript"),
                      "measure_head on the unreadable transcript: %s" % json.dumps(meas)[:160])

    # H20 (reviewer V-T2a, R4 second and third bullets; the run lead's ruling, kept as built): a
    # record with no model field, or a torn tail after a complete record, neither confirms nor
    # refutes, so a confirming record still decides: verified on a clean record, at gate and
    # boundary; control: the complete record flipped to another id confirms the swap.
    if s.want("H20"):
        for name in ("nomodel", "torntail"):
            for seat in ("gate", "boundary"):
                fx = Fx(s, "h20%s%s" % (name[:4], seat[:4]))
                if name == "nomodel":
                    row = json.loads(fx.record(30, OPUS))
                    del row["message"]["model"]
                    tail = json.dumps(row) + "\n"
                else:
                    tail = '{"type": "assistant", "isSidechain": false, "message": {'
                fx.transcript([(20, OPUS)], raw=[tail])
                code, out, _ = fx.gate("enforce") if seat == "gate" else fx.boundary("enforce")
                mc = mc_of(last(fx.of("gate" if seat == "gate" else "phase-boundary")))
                fx.transcript([(20, OLD)], raw=[tail])
                control = fx.check("enforce").get("verdict")
                ok = (code == 0 and mc.get("verdict") == "verified" and mc.get("primary_n") == 1
                      and "model-check: UNVERIFIED" not in out and control == "confirmed-swap")
                s.leg("H20.%s.%s" % (name, seat), ok, "exit %d · verdict %s · primary_n %s · "
                      "control (the complete record another id) %s" % (
                          code, mc.get("verdict"), mc.get("primary_n"), control))

    # H21 (reviewer V-T2a, Fold H1; the run lead's provisional acceptance reading): an item
    # finished while the check reads unverified is recorded done-unverified, never done, and the
    # close and the console count it held for the owner; the close still runs. Both modes;
    # through item-done and through the boundary: must fire (an unverified check), must not
    # fire (a verified check covers the item: it still reads done) and cannot decide (no check
    # of the session before the completion).
    if s.want("H21"):
        for mode in ("trial", "enforce"):
            for name in ("fire", "notfire", "cannot", "boundary-fire", "boundary-notfire"):
                fx = Fx(s, "h21%s%s" % ({"fire": "f", "notfire": "n", "cannot": "c",
                                         "boundary-fire": "bf", "boundary-notfire": "bn"}[name],
                                        mode[0]))
                if name in ("notfire", "cannot", "boundary-notfire"):
                    fx.transcript([(20, OPUS)])
                codes = []
                if name.startswith("boundary"):
                    codes.append(fx.gate(mode, item="item1")[0])   # the console draws started items
                    codes.append(fx.boundary(mode)[0])
                    done = last(fx.of("phase-boundary"))
                else:
                    if name != "cannot":
                        codes.append(fx.gate(mode, item="item1")[0])
                    codes.append(fx.cli(["item-done", "--run", fx.run, "item1"], mode)[0])
                    done = last(fx.of("item-done"))
                    if name == "notfire":
                        codes.append(fx.gate(mode, item="item2")[0])   # verified: covers item1
                ccode, cout, _ = fx.cli(["close", "--run", fx.run, "--items", "item1 done",
                                         "--meter-line", METER], mode)
                held = [h.get("item") for h in
                        (last(fx.of("run-close")).get("model_checks") or {}).get("held") or []]
                wcode, lines = fx.console()
                row = [x for x in lines if x.startswith("│ item1 ")]
                state = (row[0].split()[3] if row and len(row[0].split()) > 3 else None)
                overall = [x for x in lines if "items done" in x]
                fire = "notfire" not in name
                if fire:
                    ok = (done.get("completion") == "done-unverified" and "item1" in held and
                          state == "held" and overall and
                          all("held for the owner" in x and "all done" not in x
                              for x in overall))
                else:
                    ok = (done.get("completion") == "done" and "item1" not in held and
                          state == "done" and overall and
                          all("held for the owner" not in x for x in overall))
                ok = ok and codes and all(c == 0 for c in codes) and ccode == 0 and wcode == 0
                s.leg("H21.%s.%s" % (name, mode), ok,
                      "exits %s · close %d · completion %s (%s) · close held %s · console "
                      "item1 %s · %s" % (codes, ccode, done.get("completion"),
                                         done.get("completion_why"), held, state,
                                         (overall or ["no items line"])[-1].strip("│ ")[:90]))


def no_writes(s, before):
    """The last leg: the target's folder byte-identical after the suite, with no __pycache__;
    its control changes one byte of a copy in the same folder, under the same permissions,
    which the comparison must catch, and removes it."""
    after, cache = manifest(s.folder)
    same = after == before[0] and not cache and not before[1]
    ctl = os.path.join(s.folder, ".test_head_model-control-%d" % os.getpid())
    caught = False
    try:
        shutil.copy2(s.target, ctl)
        os.chmod(ctl, os.stat(s.target).st_mode & 0o7777)
        with_copy, _ = manifest(s.folder)
        with open(ctl, "r+b") as handle:
            first = handle.read(1)
            handle.seek(0)
            handle.write(bytes([first[0] ^ 1]))
        flipped, _ = manifest(s.folder)
        caught = flipped != with_copy
    finally:
        if os.path.exists(ctl):
            os.remove(ctl)
    final, _ = manifest(s.folder)
    s.leg("H18", same and caught and final == before[0],
          "%d files before and after, identical %s · __pycache__ %s · control (one byte of a copy "
          "in the same folder) caught %s · folder restored %s" % (
              len(before[0]), after == before[0], cache or before[1], caught,
              final == before[0]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=os.path.join(HERE, "handsoff.py"))
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    s = Suite(a.target, set(x for x in a.only.split(",") if x))
    print("target %s (sha256 %s…)" % (s.target, sha(s.target)[:12]), flush=True)
    before = manifest(s.folder)
    try:
        legs(s)
    finally:
        shutil.rmtree(s.tmp, ignore_errors=True)
    no_writes(s, before)
    failed = [n for n, ok in s.results if not ok]
    if failed:
        print("FAIL %d/%d (%s)" % (len(failed), len(s.results), ", ".join(failed)))
        return 1
    print("PASS %d/%d" % (len(s.results), len(s.results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
