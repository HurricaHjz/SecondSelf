#!/usr/bin/env python3
"""test_item_bars.py — what writes the console's item bars: --item on a spawn, item-done, the close.

  python3 test_item_bars.py [--wrappers DIR] [--fixture-root DIR] [--part all|lane|codex|handsoff]

Each leg runs in one part only: test_lane.sh runs `lane`, test_codex_lane.sh `codex` and
test_handsoff.sh `handsoff`. What the console draws from these records is test_watch.sh's. Every
fixture sits under a removed mktemp folder, with real workers on test_a3.py's stub provider, so no
model is called, and the wrappers are read and never written, which the part's last legs prove
against a changed byte.

Lines read `OK <leg>` or `BAD <leg>  [why]`, and the last line is `PASS n/n` or `FAIL k/n`.
Exit 0 every leg passed, 1 a leg failed, 2 PROBE FAILED: a premise of the suite broke. A bare run on
wrappers with no --item prints one UNRUN line and exits 0, since this file can outlive that fix.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_a3 import Fixture, events_for, rows  # noqa: E402


def stamp(offset=0):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() + offset))


def manifest(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


class Suite:
    def __init__(self, args):
        self.wrappers = Path(args.wrappers).resolve()
        self.root = Path(tempfile.mkdtemp(prefix="item-bars.", dir=str(Path(args.fixture_root).resolve())))
        self.passed = self.failed = 0

    def check(self, name, good, why=""):
        if good:
            self.passed += 1
            print("OK %s" % name, flush=True)
        else:
            self.failed += 1
            print("BAD %s  [%s]" % (name, str(why)[:300].replace("\n", " ")), flush=True)

    def fixture(self):
        f = Fixture(self.wrappers, self.root)
        f.env["AIMYTH_STATE_DIR"] = str(f.root / "state")
        f.ho = f.root / "handoff.md"
        f.ho.write_text("# Hand-off\n\n## In flight\n- pack written: 2026-01-01T00:00:00+0000\n- Next: one\n"
                        "- Needs: nothing\n- Decided: nothing\n\n## Trace\n\n## Findings ledger\n")
        return f

    def finish(self):
        total = self.passed + self.failed
        shutil.rmtree(self.root, ignore_errors=True)
        print(("PASS %d/%d" % (self.passed, total)) if not self.failed else "FAIL %d/%d" % (self.failed, total))
        return 1 if self.failed else 0


def opened(f):
    return {"ts": stamp(-30), "run": "fixture", "event": "run-open", "session": "sid-fixture",
            "head": "fixture head", "regime": "single", "regime_src": "owner", "handoff": str(f.ho),
            "detail": "fixture", "pid_src": "none", "session_kind": "head",
            "expect_items": {"item1": 1000, "item2": 1000, "item3": 1000}}


def write(f, *lines):
    f.record.write_text("".join(json.dumps(dict({"ts": stamp(), "run": "fixture"}, **row)) + "\n" for row in lines))


def spawn(f, family, lane, extra=()):
    f.scenario(family, events_for(family, "clean"))
    command = f.command(family, extra=list(extra))
    command[command.index("--lane") + 1] = lane
    return f.run(command, timeout=60)


def lane_open(f, lane):
    return next((r for r in rows(f.record) if r.get("event") == "lane-open" and r.get("lane") == lane), {})


def part_wrapper(s, family, tag):
    f = s.fixture()
    try:
        write(f, opened(f))
        named = spawn(f, family, "LA", ["--item", "item2"])
        s.check("IB%s1 (fails on old) --item is recorded on lane-open and the spawn runs" % tag,
                named.returncode == 0 and lane_open(f, "LA").get("item") == "item2", named.stderr)
        s.check("IB%s2 a named spawn draws no warning" % tag, "no --item" not in named.stderr, named.stderr)
        bare = spawn(f, family, "LB")
        s.check("IB%s3 (fails on old) a hands-off spawn with no --item warns, runs and records no item" % tag,
                bare.returncode == 0 and "no --item" in bare.stderr and "item" not in lane_open(f, "LB"), bare.stderr)
        worker = spawn(f, family, "LC", ["--item", "item3", "--detach"])
        s.check("IB%s4 (fails on old) a detached worker carries --item onto its lane-open" % tag,
                worker.returncode == 0 and lane_open(f, "LC").get("item") == "item3", worker.stdout + worker.stderr)
        empty = spawn(f, family, "LD", ["--item", "   "])
        s.check("IB%s5 (fails on old) an empty --item is refused, exit 2, nothing started" % tag,
                empty.returncode == 2 and not lane_open(f, "LD"), empty.stderr)
    finally:
        f.cleanup()
    f = s.fixture()
    try:
        plain = spawn(f, family, "LP")
        s.check("IB%s6 a plain lane run draws no warning" % tag,
                plain.returncode == 0 and "no --item" not in plain.stderr, plain.stderr)
    finally:
        f.cleanup()


def part_handsoff(s):
    def hands(f, *args):
        return f.run([sys.executable, "-B", str(f.wrappers / "handsoff.py")] + list(args))

    f = s.fixture()
    try:
        write(f, opened(f), {"event": "gate", "item": "item1", "decision": "allow"})
        done = hands(f, "item-done", "--run", "fixture", "item1", "item2 N2 · build", "--note", "the build passed")
        last = rows(f.record)[-1]
        s.check("IBH1 (fails on old) item-done writes one event naming each item by its key, with no meter",
                done.returncode == 0 and last.get("event") == "item-done" and last.get("items") == ["item1", "item2"]
                and last.get("note") == "the build passed" and "meter" not in last, done.stdout + done.stderr)
        size = len(rows(f.record))
        dry = hands(f, "item-done", "--run", "fixture", "item3", "--dry-run")
        s.check("IBH2 a dry item-done records nothing", dry.returncode == 0 and len(rows(f.record)) == size, dry.stderr)
        typo = hands(f, "item-done", "--run", "fixture", "item33")
        s.check("IBH3 a name the record does not hold is written with a warning",
                typo.returncode == 0 and "not on this record" in typo.stdout + typo.stderr, typo.stdout)
        placeholder = hands(f, "item-done", "--run", "fixture", "item3", "--note", "done at 14:3x")
        s.check("IBH4 a placeholder clock in the note is refused as elsewhere", placeholder.returncode == 2, placeholder.stderr)
        hands(f, "item-done", "--run", "fixture", "item3")
        with f.record.open("a") as handle:
            handle.write(json.dumps({"ts": stamp(), "run": "fixture", "event": "run-close", "items": "all"}) + "\n")
        late = hands(f, "item-done", "--run", "fixture", "item3")
        s.check("IBH5 a closed run takes no completion, exit 2", late.returncode == 2, late.stderr)
    finally:
        f.cleanup()

    f = s.fixture()
    try:
        source = (f.wrappers / "handsoff.py")
        code = ("import json, sys\nsys.dont_write_bytecode = True\nsys.path.insert(0, sys.argv[1])\nimport handsoff\n"
                "rows = json.load(open(sys.argv[2]))\nprint(json.dumps(handsoff.items_unresolved(rows)))\n")
        cases = f.root / "cases.json"

        def unresolved(*lines):
            cases.write_text(json.dumps(list(lines)))
            out = f.run([sys.executable, "-B", "-c", code, str(source.parent), str(cases)])
            return [row[0] for row in json.loads(out.stdout)] if out.returncode == 0 else out.stderr

        gate = {"event": "gate", "item": "item1", "ts": "t1"}
        s.check("IBH6 (fails on old) a gated item with no completion is unresolved", unresolved(gate) == ["item1"], unresolved(gate))
        s.check("IBH7 a boundary from it ends it",
                unresolved(gate, {"event": "phase-boundary", "from": "item1", "to": "item2"}) == [],
                "boundary")
        s.check("IBH8 item-done ends it", unresolved(gate, {"event": "item-done", "items": ["item1"]}) == [], "item-done")
        s.check("IBH9 a lane's --item starts one, and a boundary's `to` alone does not",
                unresolved({"event": "lane-open", "lane": "L", "item": "item3"},
                           {"event": "phase-boundary", "from": "item9", "to": "item4"}) == ["item3"], "lane")
        s.check("IBH14 (fails on old) an event whose phase names a declared item starts it, and a stray phase does not",
                unresolved({"event": "run-open", "expect_items": {"item2": 1}},
                           {"event": "decision", "phase": "item2", "ts": "t1"},
                           {"event": "observation", "phase": "closing", "ts": "t2"}) == ["item2"], "phase")
        s.check("IBH10 item0 is left out once measured orientation and the first allowed gate on item1 settle it",
                unresolved({"event": "gate", "item": "item0", "orientation_tokens": 100}, dict(gate, decision="allow")) == ["item1"], "item0")
        s.check("IBH15 (fails on old) with no orientation evidence item0 stays listed, as the board reads it",
                unresolved({"event": "gate", "item": "item0"}, dict(gate, decision="allow")) == ["item0", "item1"], "item0 unsettled")
        s.check("IBH16 (fails on old) a lane with no --item starts the item in hand, as the board reads it",
                unresolved({"event": "phase-boundary", "from": "item1", "to": "item2"}, {"event": "lane-open", "lane": "L"}) == ["item2"], "inferred")
        s.check("IBH17 control: a boundary's target with no lane under it is no start",
                unresolved({"event": "phase-boundary", "from": "item1", "to": "item2"}) == [], "bare boundary")
    finally:
        f.cleanup()

    f = s.fixture()
    try:
        write(f, opened(f), {"event": "gate", "item": "item1", "decision": "allow"},
              {"event": "gate", "item": "item2", "decision": "allow"}, {"event": "item-done", "items": ["item2"]})
        meter = "billed (list): head $1.00 · lanes $0.00 · session $1.00"
        dry = hands(f, "close", "--run", "fixture", "--items", "two of three", "--dry-run", "--meter-line", meter)
        s.check("IBH11 (fails on old) close lists the started item with no completion before it writes, and names item-done",
                dry.returncode == 0 and "1 item(s) started with no completion record" in dry.stdout
                and "item1 (started " in dry.stdout and "item-done" in dry.stdout and '"items_unresolved": ["item1"]' in dry.stdout,
                dry.stdout + dry.stderr)
        made = hands(f, "close", "--run", "fixture", "--items", "two of three", "--meter-line", meter)
        last = [r for r in rows(f.record) if r.get("event") == "run-close"]
        s.check("IBH12 (fails on old) the close goes on and carries the list, converting nothing",
                made.returncode == 0 and last and last[0].get("items_unresolved") == ["item1"]
                and not [r for r in rows(f.record) if r.get("event") == "item-done" and "item1" in r["items"]],
                made.stdout + made.stderr)
    finally:
        f.cleanup()
    f = s.fixture()
    try:
        write(f, opened(f), {"event": "gate", "item": "item1", "decision": "allow"}, {"event": "item-done", "items": ["item1"]})
        clean = hands(f, "close", "--run", "fixture", "--items", "one", "--dry-run", "--meter-line",
                      "billed (list): head $1.00 · lanes $0.00 · session $1.00")
        s.check("IBH13 control: a run with every started item ended lists none, and the event carries no key",
                clean.returncode == 0 and "no completion record" not in clean.stdout
                and "items_unresolved" not in clean.stdout, clean.stdout + clean.stderr)
    finally:
        f.cleanup()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wrappers", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--fixture-root", default=os.environ.get("TMPDIR") or "/tmp")
    parser.add_argument("--part", choices=("all", "lane", "codex", "handsoff"), default="all")
    args = parser.parse_args()
    for name in ("lane.py", "codex-lane.py", "handsoff.py"):
        if not (Path(args.wrappers) / name).is_file():
            print("PROBE FAILED: no %s under %s" % (name, args.wrappers))
            return 2
    if "def item_warning" not in (Path(args.wrappers) / "lane.py").read_text(encoding="utf-8"):
        if args.part == "all":   # a bare run where --item was taken out; a named part stays strict
            print("UNRUN these wrappers carry no --item")
            return 0
        print("PROBE FAILED: lane.py under %s carries no --item" % args.wrappers)
        return 2
    s = Suite(args)
    before = manifest(s.wrappers)
    if args.part in ("all", "lane"):
        part_wrapper(s, "claude", "L")
    if args.part in ("all", "codex"):
        part_wrapper(s, "codex", "C")
    if args.part in ("all", "handsoff"):
        part_handsoff(s)
    after = manifest(s.wrappers)
    s.check("IBZ1 the wrappers are byte-identical across the part", before == after and len(before) > 0,
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
    s.check("IBZ2 control: the same manifest catches one changed byte under the same mode", manifest(control) != unchanged)
    return s.finish()


if __name__ == "__main__":
    sys.exit(main())
