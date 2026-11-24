#!/usr/bin/env python3
"""test_decisions_spawn.py — the spawn hold, the decisions file's binding and the in-flight ack line.

  python3 test_decisions_spawn.py [--wrappers DIR] [--fixture-root DIR]
                                  [--part all|lane|codex|handsoff] [--only TEXT]

Each leg runs in one part only: test_lane.sh runs `lane`, test_codex_lane.sh `codex` and
test_handsoff.sh `handsoff`, as test_a3.py's --part split does. Every fixture sits under a removed
mktemp folder, with real workers on test_a3.py's stub provider: no model is called. The hold's
`enforce` half runs on a copy of the wrappers with the one mode word changed, and the wrappers
under test are read and never written, which the part's last legs prove against a changed byte.

Lines read `OK <leg>` or `BAD <leg>  [why]`, and the last line is `PASS n/n` or `FAIL k/n`.
Exit 0 every leg passed, 1 a leg failed, 2 PROBE FAILED: a premise of the suite broke. A bare run on
wrappers with no spawn hold prints one UNRUN line and exits 0, since this file can outlive that fix.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_a3 import Fixture, events_for, rows  # noqa: E402

# The mode lane.py ships with, the suite's one pin. Each half runs on a copy with this line set to
# its own mode, so a change of the shipped mode is this one word here and the one in lane.py.
SHIPPED_MODE = "enforce"
MODE_LINE = 'DECISIONS_HOLD_MODE = "%s"' % SHIPPED_MODE
ENFORCE_LINE = 'DECISIONS_HOLD_MODE = "enforce"'
TRIAL_LINE = 'DECISIONS_HOLD_MODE = "trial"'
SUMMARY = "lane.py: summary: "


def summary_of(text):
    """(the number of summary lines, the last line) of a call's joined output: the detached caller's
    closing summary (register 2026-11-12 09:13) must be one line, and the last."""
    lines = text.rstrip("\n").split("\n")
    return sum(1 for line in lines if line.startswith(SUMMARY)), lines[-1]


STATE = """import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import handsoff
print(json.dumps(handsoff.decisions_spawn_state(sys.argv[2])))
"""
TEXT = """import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import handsoff
state = json.loads(sys.argv[2])
print("\\n".join(handsoff.decisions_spawn_lines(state, "spawn", "L", "fixture", trial=sys.argv[3] == "trial")))
"""
SPAWN_AFTER_REPAIR = """import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import lane
def die(message, *rest):
    raise SystemExit(message)
lane.die = die
out, real = {}, lane.a3_record_rows
def attempt(key, name):
    try:
        lane.require_new_lane_id(name, sys.argv[2])
        out[key] = "clear"
    except SystemExit as exc:
        out[key] = str(exc)
lane.a3_record_rows = lambda path, allow_tail=False: ([{"lane": "Old"}], b"")
attempt("fresh", "Fresh")
attempt("same", "old")
lane.a3_record_rows = real
attempt("strict", "Fresh")
print(json.dumps(out))
"""

REPAIR = """import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import handsoff
class Reader:
    A3Premise = ValueError
    @staticmethod
    def a3_close_valid(row):
        return True
    @staticmethod
    def a3_record_rows(path):
        if sys.argv[3] == "refuses":
            raise ValueError("damaged")
        return [], b""
handsoff.HOLD_REREAD_S = 0
handsoff.a3_shared = lambda: Reader
print(json.dumps(handsoff.decisions_spawn_state(sys.argv[2])))
"""


HEAL = """import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import handsoff
class Clock:
    @staticmethod
    def sleep(seconds):
        with open(sys.argv[2], "a") as handle:
            handle.write('ter"}\\n')
handsoff.time = Clock
print(json.dumps(handsoff.decisions_spawn_state(sys.argv[2])))
"""


LATE = """import sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import handsoff
target = sys.argv[2]
def meter(*args, **kwargs):
    with open(target, "a") as handle:
        handle.write("a line that landed while the close was preparing\\n")
    return "billed (list): head $1.00 · lanes $0.00 · session $1.00"
handsoff.meter_line = meter
sys.argv = ["handsoff.py", "close", "--run", "fixture", "--items", "one"]
raise SystemExit(handsoff.main())
"""


AUTHORED = """import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import handsoff
events = handsoff.read_record(sys.argv[2])[0]
pending = handsoff.decisions_pending(events, None)[0]
owner = [line for line in handsoff.derive_inflight(events).split("\\n") if line.startswith("- Owner")]
print(json.dumps({"pending": len(pending), "owner": owner}))
"""

MESSAGE = """import sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import handsoff
sys.stdout.write(handsoff.resume_instruction(sys.argv[2], sys.argv[3]))
"""


def message_steps(text):
    """The two steps of a successor's start message that the spawn hold reads, in the message's own
    order, and the `run-resume` command it carries as an argv: (["resume", "ack"] or the reverse,
    argv), or None when the message lacks either step, which no leg reads as a pass."""
    found = re.search(r"then run `([^`]*\srun-resume\s[^`]*)`", text)
    ack = text.find("`decisions-ack`")
    if not found or ack < 0:
        return None
    order = [name for _, name in sorted([(found.start(1), "resume"), (ack, "ack")])]
    return order, shlex.split(found.group(1))


def stamp(offset=0):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() + offset))


def manifest(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


class Case:
    """One fixture with a hands-off record in it."""

    def __init__(self, suite, wrappers=None):
        self.f = Fixture(wrappers or suite.wrappers, suite.root)
        self.f.env["AIMYTH_STATE_DIR"] = str(self.f.root / "state")
        self.dec = self.f.root / "decisions.md"
        self.ho = self.f.root / "handoff.md"
        self.ho.write_text("# Hand-off\n\n## In flight\n- pack written: 2026-01-01T00:00:00+0000\n"
                           "- Next: one\n- Needs: nothing\n- Decided: nothing\n\n## Trace\n\n"
                           "## Findings ledger\n")
        self.n = 0

    def close(self):
        self.f.cleanup()

    def opened(self, bound=True):
        row = {"ts": stamp(-30), "run": "fixture", "event": "run-open", "session": "sid-fixture",
               "head": "fixture head", "regime": "single", "regime_src": "owner",
               "handoff": str(self.ho), "detail": "fixture", "pid_src": "none", "session_kind": "head"}
        if bound:
            row["decisions_file"] = os.path.realpath(self.dec)
        return row

    def record(self, *lines):
        self.f.record.write_text("".join(json.dumps(row) + "\n" for row in lines))

    def add(self, row):
        with self.f.record.open("a") as handle:
            handle.write(json.dumps(dict({"ts": stamp(), "run": "fixture"}, **row)) + "\n")

    def bound(self, text="the first line\n"):
        self.dec.write_text(text)
        self.record(self.opened())

    def hands(self, *args):
        return self.f.run([sys.executable, "-B", str(self.f.wrappers / "handsoff.py")] + list(args))

    def digest(self):
        found = re.search(r"^digest: (\S+)$", self.hands("decisions-read", "--run", "fixture").stdout, re.M)
        return found.group(1) if found else "no-digest"

    def ack(self, line="read the file"):
        return self.hands("decisions-ack", "--run", "fixture", "--ack", line, "--ack-digest", self.digest())

    def state(self):
        out = self.f.run([sys.executable, "-B", "-c", STATE, str(self.f.wrappers), str(self.f.record)])
        return json.loads(out.stdout)

    def lane(self, name=None):
        self.n += 1
        return name or "L%d" % self.n

    def spawn(self, family="claude", lane=None, extra=(), scenario=True):
        if scenario:
            self.f.scenario(family, events_for(family, "clean"))
        command = self.f.command(family, extra=extra)
        command[command.index("--lane") + 1] = self.lane(lane)
        return self.f.run(command, timeout=60)

    def resume(self, family, lane, extra=()):
        self.f.scenario(family, events_for(family, "clean"))
        command = self.f.command(family, "resume", extra=list(extra))
        command[command.index("--lane") + 1] = lane
        return self.f.run(command, timeout=60)

    def joined(self, family, operation, lane, extra=(), scenario=True):
        """A call with its two streams joined, as a launch script writes them: (exit code, text)."""
        if scenario:
            self.f.scenario(family, events_for(family, "clean"))
        command = self.f.command(family, operation, extra=list(extra))
        command[command.index("--lane") + 1] = lane
        result = subprocess.run(command, env=self.f.env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=60)
        return result.returncode, result.stdout

    def closes(self, lane):
        return sum(1 for r in self.rows() if r.get("lane") == lane and r.get("event") == "lane-closed")

    def await_close(self, lane, count, bound=30):
        """Whether the lane's closes pass `count` within `bound` seconds (a detached worker's)."""
        end = time.time() + bound
        while time.time() < end:
            if self.closes(lane) > count:
                return True
            time.sleep(0.25)
        return False

    def rows(self):
        return rows(self.f.record)

    def lanes_opened(self):
        return [r.get("lane") for r in self.rows() if r.get("event") == "lane-open"]

    def trials(self):
        return [r for r in self.rows() if str(r.get("what") or "").startswith("decisions-hold trial")]


class Suite:
    def __init__(self, args):
        self.wrappers = Path(args.wrappers).resolve()
        self.only = args.only
        self.base = Path(args.fixture_root).resolve()
        self.root = Path(tempfile.mkdtemp(prefix="decisions-spawn.", dir=str(self.base)))
        self.passed = self.failed = 0

    def check(self, name, good, why=""):
        if self.only and self.only not in name:
            return
        if good:
            self.passed += 1
            print("OK %s" % name, flush=True)
        else:
            self.failed += 1
            print("BAD %s  [%s]" % (name, str(why)[:300].replace("\n", " ")), flush=True)

    def wrapper_copy(self, name, edit=None):
        """A copy of the wrappers under the suite's root, for a mode or a planted fault."""
        copy = self.root / name
        shutil.copytree(self.wrappers, copy, ignore=shutil.ignore_patterns("__pycache__", "test_*"))
        if edit:
            edit(copy)
        return copy

    def moded(self, name, line, edit=None):
        """A copy of the wrappers whose lane.py reads `line` for its mode (and `edit` applied)."""
        if (self.root / name).is_dir():
            return self.root / name

        def flip(copy):
            path = copy / "lane.py"
            text = path.read_text(encoding="utf-8")
            if text.count(MODE_LINE) != 1:
                print("PROBE FAILED: lane.py holds %d shipped mode line(s) (%s)"
                      % (text.count(MODE_LINE), MODE_LINE), flush=True)
                raise SystemExit(2)
            path.write_text(text.replace(MODE_LINE, line), encoding="utf-8")
            if edit:
                edit(copy)
        return self.wrapper_copy(name, flip)

    def enforcing(self, name="enforce", edit=None):
        return self.moded(name, ENFORCE_LINE, edit)

    def trialing(self, name="trial", edit=None):
        return self.moded(name, TRIAL_LINE, edit)

    def finish(self):
        total = self.passed + self.failed
        shutil.rmtree(self.root, ignore_errors=True)
        print(("PASS %d/%d" % (self.passed, total)) if not self.failed else "FAIL %d/%d" % (self.failed, total))
        return 1 if self.failed else 0


def broken_state(copy):
    path = copy / "handsoff.py"
    text = path.read_text(encoding="utf-8")
    anchor = "def decisions_spawn_state(path):\n"
    if text.count(anchor) != 1:
        raise SystemExit("PROBE FAILED: no decisions_spawn_state in handsoff.py")
    path.write_text(text.replace(anchor, anchor + '    raise RuntimeError("planted fault")\n'), encoding="utf-8")


def unimportable(copy):
    (copy / "handsoff.py").write_text("def broken(:\n", encoding="utf-8")


def shipped_case(s, family):
    """A spawn on the wrappers as shipped, not a copy, after an unread line: (call, case). Run
    before any mode copy, so on a file whose mode differs from the pin it reports before the pin's
    probe stops the part."""
    c = Case(s)
    c.bound()
    c.ack()
    with c.dec.open("a") as handle:
        handle.write("an owner line the shipped file reads\n")
    return c.spawn(family), c


def shipped_holds(call, c, opened):
    """Whether a call on the shipped wrappers did what SHIPPED_MODE says: enforce holds it (exit 7,
    nothing started, no trial line); trial lets it on with the trial line."""
    if SHIPPED_MODE == "enforce":
        return call.returncode == 7 and "HOLD (decisions channel)" in call.stderr \
            and "nothing held" not in call.stderr and not c.trials() and opened() == []
    return call.returncode == 0 and "trial, nothing held" in call.stderr and len(c.trials()) == 1


def part_lane(s):
    shipped, c = shipped_case(s, "claude")
    try:
        s.check("G44s lane.py as shipped holds as its pinned mode says (%s)" % SHIPPED_MODE,
                shipped_holds(shipped, c, c.lanes_opened), "rc %s %s" % (shipped.returncode, shipped.stderr))
        c.ack()
        c.add({"event": "run-resume", "session": "sid-next", "head": "next head", "pid_src": "none"})
        fresh = c.spawn(scenario=False)
        c.ack("the next head's own read")
        admitted = c.spawn()
        want = (7, 0) if SHIPPED_MODE == "enforce" else (0, 0)
        s.check("G44h lane.py as shipped: a successor head's first spawn before its own ack is held as its mode "
                "says (enforce: exit 7, 'this head has acknowledged nothing yet', the read and ack commands), "
                "and its own ack admits the next",
                (fresh.returncode, admitted.returncode) == want
                and "this head has acknowledged nothing yet" in fresh.stderr
                and "handsoff.py decisions-read --run fixture" in fresh.stderr
                and "handsoff.py decisions-ack --run fixture" in fresh.stderr,
                "rc %s %s | %s" % (fresh.returncode, admitted.returncode, fresh.stderr))
    finally:
        c.close()
    c = Case(s, s.enforcing())
    try:
        c.bound()
        c.ack()
        first = c.spawn()
        s.check("G17 after a current ack a spawn starts its helper", first.returncode == 0 and c.lanes_opened() == ["L1"],
                first.stderr)
        with c.dec.open("a") as handle:
            handle.write("an owner line of the afternoon\n")
        before = c.f.record.read_bytes()
        held = c.spawn(scenario=False)
        s.check("G03 lane.py spawn exits 7 on an appended line, enforcing", held.returncode == 7, held.stderr)
        s.check("G04 the unread line is shown", "an owner line of the afternoon" in held.stderr, held.stderr)
        s.check("G05 no record line on a hold", c.f.record.read_bytes() == before, "record changed")
        s.check("G06 the hold names decisions-read and decisions-ack, and asks to spawn again",
                "handsoff.py decisions-read --run fixture" in held.stderr
                and "handsoff.py decisions-ack --run fixture" in held.stderr
                and "and spawn again" in held.stderr and "lane.py spawn --ack" not in held.stderr, held.stderr)
        dry = c.spawn(extra=["--dry-run"], scenario=False)
        s.check("G09 a dry run says would hold, exits 0 and writes nothing",
                dry.returncode == 0 and "would hold" in dry.stderr and c.f.record.read_bytes() == before,
                "rc %s %s" % (dry.returncode, dry.stderr))
        detached = c.spawn(extra=["--detach"], scenario=False)
        nowait = c.spawn(extra=["--detach", "--no-wait"], scenario=False)
        s.check("I01 --detach and --detach --no-wait hold in the caller, with no worker and no record line",
                detached.returncode == 7 and nowait.returncode == 7 and c.f.record.read_bytes() == before,
                "%s %s" % (detached.returncode, nowait.returncode))
        resumed = c.resume("claude", "L1", ["--brief", str(c.f.brief), "--home", str(c.f.root / "lane-home"),
                                            "--projects-root", str(c.f.root / "projects")])
        s.check("G47 lane.py resume exits 7 on a line that landed during a pause",
                resumed.returncode == 7 and "resume of lane L1: HOLD" in resumed.stderr, resumed.stderr)
        worker = c.resume("claude", "L1", ["--brief", str(c.f.brief), "--detach", "--no-wait",
                                           "--home", str(c.f.root / "lane-home")])
        s.check("I02 resume --detach holds in the caller, with no worker",
                worker.returncode == 7 and c.f.record.read_bytes() == before, worker.stderr)
        held_lane = c.lane()
        rc_s, text_s = c.joined("claude", "spawn", held_lane, ["--detach", "--no-wait"], scenario=False)
        rc_r, text_r = c.joined("claude", "resume", "L1", ["--brief", str(c.f.brief), "--detach", "--no-wait",
                                                          "--home", str(c.f.root / "lane-home")], scenario=False)
        (n_s, last_s), (n_r, last_r) = summary_of(text_s), summary_of(text_r)
        s.check("SH01 enforcing, a held detached spawn and a held detached resume (exit 7) each end their joined "
                "output with one summary line, decisions HOLD (held, exit 7), naming the call and the lane",
                rc_s == 7 and rc_r == 7 and n_s == 1 and n_r == 1 and last_s.startswith(SUMMARY)
                and "decisions HOLD (held, exit 7): spawn of lane %s: " % held_lane in last_s
                and "decisions HOLD (held, exit 7): resume of lane L1: " in last_r
                and c.f.record.read_bytes() == before, "%s %s | %s | %s" % (rc_s, rc_r, last_s, last_r))
        beat = c.resume("claude", "L1", ["--beat", "--home", str(c.f.root / "lane-home")])
        s.check("G48 a no-work beat is not held", beat.returncode != 7 and "HOLD" not in beat.stderr, beat.stderr)
        moved = c.spawn(extra=["--source-pass", "0" * 32, "--source-disposition", "fixture"], scenario=False)
        s.check("G52 a recorded movement passes the hold and meets publication's own check",
                moved.returncode != 7 and "HOLD" not in moved.stderr and moved.returncode != 0, moved.stderr)
        c.ack()
        burst = [c.spawn().returncode]
        with c.dec.open("a") as handle:
            handle.write("a line landing in the burst\n")
        burst += [c.spawn().returncode, c.spawn().returncode]
        c.ack()
        burst += [c.spawn().returncode, c.spawn().returncode]
        s.check("I03 a burst: the first starts, a line lands, two are held, one ack admits the rest",
                burst == [0, 7, 7, 0, 0], burst)
        with c.f.record.open("a") as handle:
            handle.write('{"event": "observation", torn\n')
        opened = c.lanes_opened()
        spawned = c.spawn(scenario=False)
        torn = c.resume("claude", "L1", ["--brief", str(c.f.brief), "--home", str(c.f.root / "lane-home"),
                                         "--projects-root", str(c.f.root / "projects")])
        s.check("F1 a spawn or a resume onto a damaged record exits 2, nothing started, whatever the mode",
                spawned.returncode == 2 and torn.returncode == 2 and "damaged record row" in spawned.stderr
                and c.lanes_opened() == opened, spawned.stderr + torn.stderr)
    finally:
        c.close()

    c = Case(s, s.root / "enforce")
    try:
        c.bound()
        other = c.f.root / "other.jsonl"
        other.write_text(json.dumps(c.opened()) + "\n")
        c.ack()
        stale = c.spawn(extra=["--record", str(other)], scenario=False)
        s.check("I05 --record names the record that decides, and the printed commands carry it",
                stale.returncode == 7 and "--record %s" % other in stale.stderr, stale.stderr)
        c.dec.write_text("the first line\nanother\n")
        default_stale = c.spawn(scenario=False)
        s.check("I05 control: the default record's own state holds with no --record in the text",
                default_stale.returncode == 7 and "--record" not in default_stale.stderr, default_stale.stderr)
        c.dec.unlink()
        gone = c.spawn(scenario=False)
        s.check("G25 a bound file gone exits 2 enforcing, with what clears it",
                gone.returncode == 2 and "cannot be read" in gone.stderr and "put it back" in gone.stderr
                and "HOLD" not in gone.stderr, gone.stderr)
        rc_g, text_g = c.joined("claude", "spawn", c.lane(), ["--detach", "--no-wait"], scenario=False)
        n_g, last_g = summary_of(text_g)
        s.check("SH02 enforcing, a detached spawn the check cannot decide (exit 2) ends with one summary line "
                "naming the refusal, refused (exit 2): the decisions check: …, and no HOLD",
                rc_g == 2 and n_g == 1 and last_g.startswith(SUMMARY + "refused (exit 2): the decisions check: ")
                and "HOLD" not in last_g, "%s | %s" % (rc_g, last_g))
    finally:
        c.close()

    c = Case(s, s.enforcing("enforce-broken", broken_state))
    try:
        c.bound()
        crashed = c.spawn(scenario=False)
        s.check("G46 a check that raises exits 2 enforcing, never passes",
                crashed.returncode == 2 and "the decisions check failed" in crashed.stderr
                and not c.lanes_opened(), crashed.stderr)
    finally:
        c.close()
    c = Case(s, s.enforcing("enforce-noimport", unimportable))
    try:
        c.bound()
        crashed = c.spawn(scenario=False)
        s.check("G46 a handsoff.py that will not import exits 2 enforcing",
                crashed.returncode == 2 and "the decisions check failed" in crashed.stderr, crashed.stderr)
    finally:
        c.close()

    c = Case(s, s.root / "enforce")
    try:
        c.dec.write_text("a line\n")
        c.record({"ts": stamp(), "run": "fixture", "event": "lane-open", "lane": "P1", "class": "fixture"},
                 {"ts": stamp(), "run": "fixture", "event": "observation", "phase": "", "what": "AUTHOR: a relay"})
        plain = c.spawn()
        s.check("G29 a plain lane run is clear, even with an AUTHOR line", plain.returncode == 0, plain.stderr)
        c.f.record.unlink()
        fresh = c.spawn()
        s.check("G30 no record yet is clear", fresh.returncode == 0, fresh.stderr)
        c.bound()
        c.add({"event": "run-close", "items": "done"})
        closed = c.spawn()
        s.check("G31 a closed run is clear, with its warning",
                closed.returncode == 0 and "is closed" in closed.stderr, closed.stderr)
    finally:
        c.close()

    t = Case(s, s.trialing())
    try:
        t.bound()
        t.ack()
        with t.dec.open("a") as handle:
            handle.write("a line the trial sees\n")
        went = t.spawn()
        s.check("G40 trial: the spawn goes on and its helper starts",
                went.returncode == 0 and t.lanes_opened() == ["L1"], went.stderr)
        s.check("G41 trial: the text prints and asks for no second spawn",
                "trial, nothing held" in went.stderr and "a line the trial sees" in went.stderr
                and "and spawn again" not in went.stderr, went.stderr)
        lines = t.trials()
        good = len(lines) == 1 and lines[0].get("run") == "fixture" and lines[0].get("size") == t.dec.stat().st_size \
            and lines[0].get("digest") == hashlib.sha256(t.dec.read_bytes()).hexdigest() \
            and lines[0].get("event") == "observation" and not lines[0]["what"].startswith(("AUTHOR", "ack:"))
        s.check("G42 trial: one observation with run, digest and size, never an AUTHOR or ack line", good, lines)
        s.check("G43 trial: its line leaves the state held", t.state()["state"] == "hold", t.state())
        t.spawn()
        t.spawn()
        s.check("F5 trial: a burst on one digest and head logs once", len(t.trials()) == 1, len(t.trials()))
        with t.dec.open("a") as handle:
            handle.write("a second line\n")
        t.spawn()
        s.check("F5 trial: a new digest logs again", len(t.trials()) == 2, len(t.trials()))
        t.add({"event": "run-resume", "session": "sid-next", "head": "next head", "pid_src": "none"})
        t.spawn()
        s.check("F5 trial: a new head logs its own", len(t.trials()) == 3, len(t.trials()))
        t.dec.unlink()
        logged = len(t.trials())
        undecided = t.spawn()
        s.check("G25t trial: a bound file gone prints, logs once and goes on",
                undecided.returncode == 0 and "CANNOT DECIDE" in undecided.stderr and len(t.trials()) == logged + 1,
                undecided.stderr)
        t.spawn()
        s.check("G25t trial: the same unknown logs once a head", len(t.trials()) == logged + 1, len(t.trials()))
    finally:
        t.close()
    t = Case(s, s.trialing())     # the closing summary under trial, on a fixture of its own (the F5 counts above stay whole)
    try:
        t.bound()
        t.ack()
        first = t.lane()
        rc0, text0 = t.joined("claude", "spawn", first, [])
        with t.dec.open("a") as handle:
            handle.write("a line the summary names\n")
        lane = t.lane()
        rc1, text1 = t.joined("claude", "spawn", lane, ["--detach", "--no-wait"])
        n1, last1 = summary_of(text1)
        went = t.await_close(lane, 0)
        s.check("SH03 trial: a detached spawn the trial would hold goes on (exit 0, its lane closes) and ends its "
                "joined output with one summary line, decisions HOLD (trial), naming the lane and why",
                rc0 == 0 and rc1 == 0 and n1 == 1 and last1.startswith(SUMMARY) and went
                and "decisions HOLD (trial): spawn of lane %s: content no accepted ack covers" % lane in last1
                and "trial, nothing held" in text1, "%s %s %s | %s" % (rc0, rc1, went, last1))
        waited = t.lane()
        rc2, text2 = t.joined("claude", "spawn", waited, ["--detach"])
        n2, last2 = summary_of(text2)
        closes = t.closes(first)
        rc3, text3 = t.joined("claude", "resume", first, ["--brief", str(t.f.brief), "--detach", "--no-wait",
                                                         "--home", str(t.f.root / "lane-home"),
                                                         "--projects-root", str(t.f.root / "projects")])
        n3, last3 = summary_of(text3)
        resumed = t.await_close(first, closes)
        s.check("SH04 trial: a waiting --detach spawn and a detached resume each end with one summary line naming "
                "the trial HOLD of their own call (the waiting one after its close and beside its own warning)",
                rc2 == 0 and n2 == 1 and "decisions HOLD (trial): spawn of lane %s: " % waited in last2
                and "--detach without --no-wait" in last2 and last2.startswith(SUMMARY)
                and rc3 == 0 and n3 == 1 and last3.startswith(SUMMARY) and resumed
                and "decisions HOLD (trial): resume of lane %s: " % first in last3,
                "%s %s %s | %s | %s" % (rc2, rc3, resumed, last2, last3))
    finally:
        t.close()
    t = Case(s, s.trialing("trial-broken", broken_state))
    try:
        t.bound()
        crashed = t.spawn()
        s.check("G46 trial: a check that raises prints, logs and goes on",
                crashed.returncode == 0 and "the decisions check failed" in crashed.stderr and len(t.trials()) == 1,
                crashed.stderr)
    finally:
        t.close()
    source = (s.wrappers / "lane.py").read_text(encoding="utf-8")
    enforced = (s.root / "enforce" / "lane.py").read_text(encoding="utf-8")
    trialled = (s.root / "trial" / "lane.py").read_text(encoding="utf-8")
    other = TRIAL_LINE if SHIPPED_MODE == "enforce" else ENFORCE_LINE
    s.check("G44 the shipped mode is the pinned one, one word from the other (controls: the enforce copy "
            "reads enforce, the trial copy trial)",
            source.count(MODE_LINE) == 1 and other not in source
            and enforced.count(ENFORCE_LINE) == 1 and TRIAL_LINE not in enforced
            and trialled.count(TRIAL_LINE) == 1 and ENFORCE_LINE not in trialled,
            "shipped %s, pinned %s" % (re.findall(r'DECISIONS_HOLD_MODE = "[^"]*"', source), SHIPPED_MODE))


def part_codex(s):
    shipped, c = shipped_case(s, "codex")
    try:
        s.check("G44c codex-lane.py as shipped reads lane.py's one mode constant and holds as it says (%s)"
                % SHIPPED_MODE, shipped_holds(shipped, c, c.lanes_opened),
                "rc %s %s" % (shipped.returncode, shipped.stderr))
    finally:
        c.close()
    c = Case(s, s.enforcing())
    try:
        c.bound()
        c.ack()
        first = c.spawn("codex")
        s.check("G17c after a current ack a Codex spawn starts its helper", first.returncode == 0, first.stderr)
        with c.dec.open("a") as handle:
            handle.write("an owner line for Codex\n")
        before = c.f.record.read_bytes()
        stage = c.f.root / "stage-source"
        stage.mkdir()
        (stage / "kept.txt").write_text("a staged file\n")
        held = c.spawn("codex", extra=["--stage-from", str(stage)], scenario=False)
        s.check("G07 codex-lane.py spawn exits 7 on the same state", held.returncode == 7, held.stderr)
        s.check("G08 codex: no record line", c.f.record.read_bytes() == before, "record changed")
        s.check("I04 a held Codex spawn leaves no staged copy, since the check precedes prepare",
                not list((c.f.store / "spawn-records").glob("*-cwd-*")), "a stage is left")
        dry = c.resume("codex", "L1", ["--brief", str(c.f.brief), "--dry-run"])
        s.check("G49 codex-lane.py resume --dry-run says would hold", "would hold" in dry.stderr, dry.stderr)
        resumed = c.resume("codex", "L1", ["--brief", str(c.f.brief)])
        s.check("G49 codex-lane.py resume exits 7", resumed.returncode == 7, resumed.stderr)
        c.dec.unlink()
        gone = c.spawn("codex", scenario=False)
        s.check("G25c a bound file gone exits 2 enforcing on Codex", gone.returncode == 2, gone.stderr)
    finally:
        c.close()
    t = Case(s, s.trialing())
    try:
        t.bound()
        went = t.spawn("codex")
        s.check("G40c trial: a Codex spawn goes on and logs",
                went.returncode == 0 and "trial, nothing held" in went.stderr and len(t.trials()) == 1, went.stderr)
    finally:
        t.close()


def part_handsoff(s):
    c = Case(s)
    try:
        c.dec.write_text("the first line\n")
        made = c.hands("run-open", "--envelope-usd", "1000", "--run", "bind", "--session", "sid-bind", "--head", "fixture head",
                       "--regime", "single", "--regime-src", "owner", "--handoff", str(c.ho),
                       "--detail", "fixture", "--viewer", "none", "--decisions-file", str(c.dec))
        opened = rows(c.f.store / "spawn-records" / "bind.jsonl")
        s.check("H01 run-open --decisions-file binds the canonical path",
                made.returncode == 0 and opened and opened[-1].get("decisions_file") == os.path.realpath(c.dec),
                made.stderr)
        missing = c.hands("run-open", "--envelope-usd", "1000", "--run", "bind2", "--session", "sid-bind2", "--head", "fixture head",
                          "--regime", "single", "--regime-src", "owner", "--handoff", str(c.ho),
                          "--detail", "fixture", "--viewer", "none", "--decisions-file", str(c.f.root / "absent.md"))
        s.check("H02 run-open with a missing file is refused and writes nothing",
                missing.returncode == 2 and not (c.f.store / "spawn-records" / "bind2.jsonl").exists(), missing.stderr)
        c.bound()
        s.check("G23 a bound file with no ack holds on the whole file",
                c.state()["state"] == "hold" and c.state()["lines"] == ["the first line"], c.state())
        read = c.hands("decisions-read", "--run", "fixture")
        s.check("G10 decisions-read needs no --decisions-file on a bound run",
                read.returncode == 0 and "the first line" in read.stdout, read.stderr)
        unbound = c.hands("decisions-read", "--run", "no-such-run")
        s.check("G10 control: no record is exit 2", unbound.returncode == 2, unbound.stderr)
        acked = c.ack("the first read")
        s.check("G01a the ack verb accepts the current digest", acked.returncode == 0, acked.stderr)
        last = c.rows()[-1]
        s.check("G01b the ack carries path, digest, size and coverage",
                last.get("decisions_file") == os.path.realpath(c.dec) and last.get("size") == 15
                and last.get("digest") and last.get("decisions_seen") == 1, last)
        s.check("G02 clear after a current ack", c.state()["state"] == "clear", c.state())
        s.check("G16 one ack admits a burst: a second read changes nothing", c.state()["state"] == "clear", c.state())
        c.dec.write_text("the first line\nan appended line\n")
        s.check("G03h an appended line holds, shown as unread",
                c.state()["state"] == "hold" and c.state()["lines"] == ["an appended line"], c.state())
        size = len(c.rows())
        stale = c.hands("decisions-ack", "--run", "fixture", "--ack", "x", "--ack-digest", "0" * 64)
        s.check("G11 a stale digest holds 6 and records nothing",
                stale.returncode == 6 and len(c.rows()) == size, stale.stderr)
        bad = c.hands("decisions-ack", "--run", "fixture", "--ack", "x", "--ack-digest", "abc")
        s.check("G12 a malformed digest is refused, exit 2", bad.returncode == 2, bad.stderr)
        plain = c.hands("decisions-ack", "--run", "fixture", "--ack", "x")
        s.check("G13 a file-backed ack with no digest holds 6", plain.returncode == 6, plain.stderr)
        none = c.hands("decisions-ack", "--run", "fixture", "--ack-digest", "0" * 64)
        s.check("G13 control: no --ack is refused", none.returncode == 2, none.stderr)
        dry = c.hands("decisions-ack", "--run", "fixture", "--ack", "x", "--ack-digest", c.digest(), "--dry-run")
        s.check("G14 a dry ack records nothing", dry.returncode == 0 and len(c.rows()) == size, dry.stderr)
        c.ack("the second read")
        s.check("G15 a current ack clears the hold", c.state()["state"] == "clear", c.state())
        c.dec.write_text("the first line\nan appended lime\n")
        s.check("G20 an edit of the same size holds", c.state()["state"] == "hold", c.state())
        c.dec.write_text("the first line\n")
        s.check("G21 a cut file holds", c.state()["state"] == "hold", c.state())
        c.dec.write_text("the first line\nan appended line\n")
        os.utime(c.dec, None)
        s.check("G22 a touch alone holds nothing", c.state()["state"] == "clear", c.state())
        c.dec.unlink()
        gone = c.state()
        s.check("G24 a bound file gone is unknown, never clear, with what clears it",
                gone["state"] == "unknown" and "put it back" in gone["route"], gone)
        c.dec.write_text("the first line\nan appended line\n")

        other = c.f.root / "refs-decisions.md"
        other.write_text("a helper's staged copy\n")
        wrong = c.hands("decisions-ack", "--run", "fixture", "--decisions-file", str(other), "--ack", "x",
                        "--ack-digest", hashlib.sha256(other.read_bytes()).hexdigest())
        s.check("G36 an ack on another file is refused, exit 2", wrong.returncode == 2, wrong.stderr)
        right = c.hands("decisions-ack", "--run", "fixture", "--decisions-file", str(c.dec), "--ack", "the file",
                        "--ack-digest", hashlib.sha256(c.dec.read_bytes()).hexdigest())
        s.check("G37 control: the bound file acks", right.returncode == 0, right.stderr)
        absent = c.hands("gate", "--run", "fixture", "--to", "item one", "--decisions-file", str(c.f.root / "absent.md"))
        s.check("G51 a named path that does not exist keeps its own message",
                absent.returncode == 2 and "is not a file at this call" in absent.stderr, absent.stderr)
    finally:
        c.close()

    c = Case(s)
    try:
        c.bound()
        held = c.hands("gate", "--run", "fixture", "--to", "item one")
        s.check("G50 gate with no --decisions-file holds on the bound file", held.returncode == 6, held.stderr)
        closed = c.hands("close", "--run", "fixture", "--items", "none")
        s.check("I06 close with the file omitted holds the same way", closed.returncode == 6, closed.stderr)
        c.ack()
        late = c.f.run([sys.executable, "-B", "-c", LATE, str(c.f.wrappers), str(c.dec)])
        s.check("I06 a close's final recheck fires on the bound file, with the file omitted",
                late.returncode == 6 and "arrived while the close was preparing" in late.stdout + late.stderr
                and not [r for r in c.rows() if r.get("event") == "run-close"], late.stdout + late.stderr)
        c.dec.write_text("the first line\n")
        c.ack()
        c.add({"event": "run-resume", "session": "sid-b", "head": "b", "pid_src": "none"})
        fresh = c.state()
        s.check("G34 a fresh head holds on its predecessor's ack",
                fresh["state"] == "hold" and "acknowledged nothing yet" in fresh["why"], fresh)
        whole = c.hands("decisions-read", "--run", "fixture")
        s.check("F2 a fresh head's decisions-read shows the whole file",
                "the first line" in whole.stdout and "this head has acknowledged nothing yet" in whole.stdout,
                whole.stdout)
        s.check("F2 the hold's own view carries the file too", fresh["lines"] == ["the first line"], fresh)
        c.ack("the fresh head's read")
        s.check("G35 its own ack clears it", c.state()["state"] == "clear", c.state())
        c.dec.write_text("the first line\nnewer\n")
        after = c.hands("decisions-read", "--run", "fixture")
        s.check("F2 control: after its own ack it reads only what is new",
                "newer" in after.stdout and "this head has acknowledged nothing yet" not in after.stdout
                and "1 unread line" in after.stdout, after.stdout)
    finally:
        c.close()

    # The successor's start message, driven in its own order (review V-T8-G2b, change 1: the clause
    # asking for the ack stood before the run-resume step, and the hold counts only an ack made after
    # the head's own run-resume, so a head that followed the text in order was held at its first
    # spawn). Each case is a record shaped like a hand-over: the old head's ack, its head-exit and the
    # starter's head-successor for the new head. G61 runs the message's two steps in the order the
    # message under test gives them, its run-resume being the command the message carries, run as
    # written; its controls are the review's: the other order holds, and no new ack holds.
    def handed_over():
        c = Case(s)
        c.dec.write_text("the first line\n")
        c.record(c.opened())
        c.ack("the old head's read")
        c.add({"event": "head-exit", "band": "80", "context": "80 %", "pack": True, "session": "sid-fixture"})
        c.add({"event": "head-successor", "session_id": "sid-next", "pid": 1, "model": "fixture",
               "effort": "max"})
        return c

    def drive(c, order, argv):
        codes = []
        for step in order:
            done = c.f.run(argv) if step == "resume" else c.ack("the new head's read")
            codes.append("%s %d%s" % (step, done.returncode,
                                      "" if done.returncode == 0 else " " + (done.stdout + done.stderr)[-200:]))
        return codes

    argv = []
    c = handed_over()
    try:
        shown =c.f.run([sys.executable, "-B", "-c", MESSAGE, str(c.f.wrappers), "fixture", str(c.ho)])
        steps = message_steps(shown.stdout)
        s.check("G60 the start message carries both steps, its run-resume through the script under test",
                steps is not None and str(c.f.wrappers / "handsoff.py") in " ".join(steps[1]),
                shown.stdout[-400:] + shown.stderr[-200:])
        order, argv = steps if steps else (["ack", "resume"], [])
        codes = drive(c, order, argv) if argv else ["no run-resume command in the message"]
        got = c.state()
        s.check("G61 a successor that follows its start message in order is clear at its first spawn",
                got["state"] == "clear" and all(code.split()[1:2] == ["0"] for code in codes)
                and [r.get("event") for r in c.rows()].count("run-resume") == 1,
                ["the order read from the message: " + " then ".join(order), codes, got])
    finally:
        c.close()

    c = handed_over()
    try:
        codes = drive(c, ["ack", "resume"], argv) if argv else ["no run-resume command"]
        got = c.state()
        s.check("G61 control (the review's): the ack first, then run-resume, holds",
                got["state"] == "hold" and "acknowledged nothing yet" in got["why"]
                and all(code.split()[1:2] == ["0"] for code in codes), [codes, got])
    finally:
        c.close()

    c = handed_over()
    try:
        codes = drive(c, ["resume"], argv) if argv else ["no run-resume command"]
        got = c.state()
        s.check("G61 control (the review's): run-resume with no new ack holds",
                got["state"] == "hold" and all(code.split()[1:2] == ["0"] for code in codes), [codes, got])
    finally:
        c.close()

    c = Case(s)
    try:
        c.dec.write_text("the first line\n")
        c.record(c.opened())
        c.ack()
        s.check("G33 control: clear before the new head", c.state()["state"] == "clear", c.state())
        c.add({"event": "run-close", "items": "done"})
        s.check("G31h a closed run is clear", c.state()["state"] == "clear", c.state())
        c.add({"event": "run-resume", "session": "sid-b", "head": "b", "pid_src": "none"})
        s.check("G32 a closed run reopened holds again", c.state()["state"] == "hold", c.state())
    finally:
        c.close()

    c = Case(s)
    try:
        c.dec.write_text("the first line\n")
        c.record(c.opened(bound=False))
        digest = hashlib.sha256(c.dec.read_bytes()).hexdigest()
        gated = c.hands("gate", "--run", "fixture", "--to", "item one", "--decisions-file", str(c.dec),
                        "--ack", "the first read", "--ack-digest", digest)
        kinds = [r.get("event") for r in c.rows() if r.get("decisions_file") == os.path.realpath(c.dec)]
        s.check("H03 a gate that names the file binds it, on its ack and on its own event",
                gated.returncode == 0 and "observation" in kinds and "gate" in kinds, gated.stdout + gated.stderr)
        c.dec.write_text("the first line\nanother\n")
        s.check("H03 control: the bound file then holds a spawn with no flag anywhere", c.state()["state"] == "hold", c.state())
        other = c.f.root / "other.jsonl"
        other.write_text(c.f.record.read_text())
        c.f.record.unlink()
        read = c.hands("decisions-read", "--run", "fixture", "--record", str(other))
        digest = re.search(r"^digest: (\S+)$", read.stdout, re.M)
        acked = c.hands("decisions-ack", "--run", "fixture", "--record", str(other), "--ack", "read",
                        "--ack-digest", digest.group(1) if digest else "none")
        s.check("I05 the two printed commands run on a named record",
                read.returncode == 0 and acked.returncode == 0 and "another" in read.stdout
                and str(rows(other)[-1].get("what")).startswith("ack: "), read.stderr + acked.stderr)
    finally:
        c.close()

    c = Case(s)
    try:
        c.record(c.opened(bound=False))
        s.check("G26 a run with no decisions file is clear", c.state()["state"] == "clear", c.state())
        c.add({"event": "observation", "phase": "", "what": "AUTHOR: a relay from him"})
        relay = c.state()
        s.check("G27 an unread AUTHOR relay holds", relay["state"] == "hold", relay)
        shown = c.f.run([sys.executable, "-B", "-c", TEXT, str(c.f.wrappers), json.dumps(relay), "enforce"])
        s.check("F12 a no-file relay prints no read command, only the ack",
                "  read:" not in shown.stdout and "decisions-ack" in shown.stdout
                and "--ack-digest" not in shown.stdout, shown.stdout)
        acked = c.hands("decisions-ack", "--run", "fixture", "--ack", "read the relay")
        s.check("G28 an ack with no digest clears a no-file relay",
                acked.returncode == 0 and c.state()["state"] == "clear", acked.stderr)
    finally:
        c.close()

    # A run's own parked question is never his word (his item 57 of 2026-11-09; review V-T8-G2b,
    # point 5 (iii)): an `AUTHOR-QUESTION:` observation, the tag runs once wrote, holds no spawn, no
    # gate or close (decisions_pending) and is no owner line in a derived pack; a relay of his words
    # on the same record still holds and is still listed (the control, the same probes).
    c = Case(s)
    try:
        c.record(c.opened(bound=False))
        for what in ("AUTHOR-QUESTION: shall the run install tonight?", "author-question: the same, lower case"):
            c.add({"event": "observation", "phase": "", "what": what})
        asked = c.state()
        seen = json.loads(c.f.run([sys.executable, "-B", "-c", AUTHORED, str(c.f.wrappers),
                                   str(c.f.record)]).stdout or "{}")
        s.check("G29 a run's own AUTHOR-QUESTION observation holds no spawn, no gate or close, and is no owner line",
                asked["state"] == "clear" and seen.get("pending") == 0 and seen.get("owner") == [],
                [asked, seen])
        c.add({"event": "observation", "phase": "", "what": "AUTHOR: yes, install tonight"})
        relay = c.state()
        seen = json.loads(c.f.run([sys.executable, "-B", "-c", AUTHORED, str(c.f.wrappers),
                                   str(c.f.record)]).stdout or "{}")
        s.check("G29 with a relay after the questions, the relay alone holds and is the one owner line",
                relay["state"] == "hold" and seen.get("pending") == 1 and len(seen.get("owner", [])) == 1
                and "install tonight" in seen["owner"][0] and "QUESTION" not in seen["owner"][0].upper(),
                [relay, seen])
    finally:
        c.close()

    c = Case(s)
    try:
        c.record(c.opened(bound=False))
        c.add({"event": "observation", "phase": "", "what": "AUTHOR: yes, install tonight"})
        relay = c.state()
        seen = json.loads(c.f.run([sys.executable, "-B", "-c", AUTHORED, str(c.f.wrappers),
                                   str(c.f.record)]).stdout or "{}")
        s.check("G29 control: a relay of his words alone holds, is pending at a gate and is his owner line",
                relay["state"] == "hold" and seen.get("pending") == 1 and len(seen.get("owner", [])) == 1
                and "install tonight" in seen["owner"][0], [relay, seen])
    finally:
        c.close()

    c = Case(s)
    try:
        c.bound("".join("line %02d\n" % n for n in range(30)))
        state = c.state()
        shown = c.f.run([sys.executable, "-B", "-c", TEXT, str(c.f.wrappers), json.dumps(state), "enforce"]).stdout
        s.check("F13 the bounded view keeps the newest lines and says how many earlier ones were cut",
                "line 29" in shown and "line 18" in shown and "line 17" not in shown
                and "18 earlier line(s) cut" in shown, shown)
        trial = c.f.run([sys.executable, "-B", "-c", TEXT, str(c.f.wrappers), json.dumps(state), "trial"]).stdout
        s.check("F5 the trial's text asks for no second spawn",
                "and spawn again" not in trial and "and spawn again" in shown, trial)
        one = dict(state, lines=["x" * 9000])
        long_line = c.f.run([sys.executable, "-B", "-c", TEXT, str(c.f.wrappers), json.dumps(one), "enforce"]).stdout
        s.check("F13 a line past the byte bound still shows its head", "| " + "x" * 100 in long_line, long_line[:200])
    finally:
        c.close()

    c = Case(s)
    try:
        c.bound()
        c.ack()
        whole = c.f.record.read_text()
        c.f.record.write_text(whole + '{"event": "observation", torn\n')
        s.check("G45 an unparseable record line is unknown, never clear, with the route",
                c.state()["state"] == "unknown" and "--repair-projection" in c.state()["route"], c.state())
        repaired = c.f.run([sys.executable, "-B", "-c", REPAIR, str(c.f.wrappers), str(c.f.record), "accepts"])
        s.check("F9 a repaired record goes on where the strict reader admits the line",
                json.loads(repaired.stdout)["state"] == "clear", repaired.stdout + repaired.stderr)
        refused = c.f.run([sys.executable, "-B", "-c", REPAIR, str(c.f.wrappers), str(c.f.record), "refuses"])
        s.check("F9 control: a line the strict reader refuses stays unknown",
                json.loads(refused.stdout)["state"] == "unknown", refused.stdout + refused.stderr)
        spawned = c.f.run([sys.executable, "-B", "-c", SPAWN_AFTER_REPAIR, str(c.f.wrappers), str(c.f.record)])
        got = json.loads(spawned.stdout) if spawned.returncode == 0 else {}
        s.check("F5 of CR-tools2 (fails on old): a damaged line the strict reader admits no longer stops the spawn's lane check",
                got.get("fresh") == "clear", spawned.stdout + spawned.stderr)
        s.check("F5 control: a lane id already on the record is still refused", "case-equivalent" in got.get("same", ""), got)
        s.check("F5 control: damage no repair admits still cannot prove absence", "cannot check lane ids" in got.get("strict", ""), got)
        c.f.record.write_text(whole + '{"event": "observation", "phase": "", "what": "a wri')
        healed = c.f.run([sys.executable, "-B", "-c", HEAL, str(c.f.wrappers), str(c.f.record)])
        s.check("G54 a torn line a writer finishes during the second look is no refusal",
                json.loads(healed.stdout)["state"] == "clear", healed.stdout + healed.stderr)
    finally:
        c.close()

    c = Case(s)
    live = subprocess.Popen([sys.executable, "-c", "import time\ntime.sleep(60)\n"])
    try:
        c.bound()
        time.sleep(1.2)
        c.add({"event": "run-resume", "session": "sid-peer", "head": "peer", "pid": live.pid, "pid_src": "arg"})
        peer = c.hands("decisions-ack", "--run", "fixture", "--ack", "x", "--ack-digest", c.digest())
        s.check("G38 a peer session cannot acknowledge for the lead, exit 9", peer.returncode == 9, peer.stdout + peer.stderr)
        lead = c.hands("decisions-ack", "--run", "fixture", "--ack", "x", "--ack-digest", c.digest(),
                       "--i-am-pid", str(live.pid))
        s.check("G39 control: the lead itself can", lead.returncode == 0, lead.stdout + lead.stderr)
    finally:
        live.kill()
        live.wait()
        c.close()

    c = Case(s)
    try:
        c.bound()
        c.ack("read the morning's line")
        made = c.hands("boundary", "--run", "fixture", "--from", "item1", "--to", "item2", "--disposition", "d",
                       "--waste", "none", "--next", "n", "--meter-line", "billed: head $1.00 · lanes $0.00 · session $1.00")
        body = c.ho.read_text()
        s.check("P01 a boundary writes the ack into the hand-off's In flight",
                "- Acknowledged: read the morning's line (at " in body, made.stdout + made.stderr)
        again = c.hands("handoff", "--run", "fixture", "--inflight-from-record")
        twice = c.ho.read_text().count("- Acknowledged: read the morning's line")
        s.check("P02 a re-derivation does not double the line", twice <= 1, "%d %s" % (twice, again.stderr))
    finally:
        c.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wrappers", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--fixture-root", default=os.environ.get("TMPDIR") or "/tmp")
    parser.add_argument("--part", choices=("all", "lane", "codex", "handsoff"), default="all")
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    for name in ("lane.py", "codex-lane.py", "handsoff.py"):
        if not (Path(args.wrappers) / name).is_file():
            print("PROBE FAILED: no %s under %s" % (name, args.wrappers))
            return 2
    if "def decisions_spawn_check" not in (Path(args.wrappers) / "lane.py").read_text(encoding="utf-8"):
        if args.part == "all":   # a bare run where the hold was taken out; a named part stays strict
            print("UNRUN these wrappers carry no spawn hold")
            return 0
        print("PROBE FAILED: lane.py under %s carries no spawn hold" % args.wrappers)
        return 2
    s = Suite(args)
    before = manifest(s.wrappers)
    if args.part in ("all", "lane"):
        part_lane(s)
    if args.part in ("all", "codex"):
        part_codex(s)
    if args.part in ("all", "handsoff"):
        part_handsoff(s)
    after = manifest(s.wrappers)
    s.check("Z01 the wrappers are byte-identical across the part", before == after and len(before) > 0,
            sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))[:5])
    control = s.root / "manifest-control"
    control.mkdir()
    target = control / "lane.py"
    shutil.copyfile(s.wrappers / "lane.py", target)
    target.chmod((s.wrappers / "lane.py").stat().st_mode)
    unchanged = manifest(control)
    data = bytearray(target.read_bytes())
    data[0] ^= 1
    target.write_bytes(bytes(data))
    s.check("Z02 control: the same manifest catches one changed byte under the same mode",
            manifest(control) != unchanged)
    return s.finish()


if __name__ == "__main__":
    sys.exit(main())
