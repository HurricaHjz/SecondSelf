#!/usr/bin/env python3
"""test_basic_meter.py — the suite for the basic window meter (package A of the window-meter
design, revision 3, section 4.5): readings at run-open, at every boundary and at the close, their
deltas, lane items, and the close-only accounting, per window and never summed across windows.

Run:  python3 test_basic_meter.py [--wrappers DIR] [--only ID]... [--fixture-root DIR] [--vault DIR]
      (--wrappers defaults to this file's directory; --only selects groups: A03-A08, N10, W02)

It runs on the package-B-plus-A tree, because it uses B's reader form, and it reuses B's fixture
harness (test_limit_defaults.py beside this file): stand-in clients for `claude -p /usage` and
`codex app-server`, a stand-in `codex` for lanes, fixture stores under one mktemp -d directory
inside --fixture-root (default TMPDIR, else /tmp), removed on exit. No real model, account
reading or helper is started. Each group carries a planted case that must be caught, a clean case
and a positive control on the same run; the last group proves the suite and the new module wrote
nothing beside the scripts. On a tree without usage_windows.py (package B alone) the groups fail
with the reason, which is the base's own failure. The last line is PASS n/n or FAIL k/n; a broken
premise prints PROBE FAILED and exits 2. Timing bounds are ceilings set by judgement, unmeasured.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
GROUPS = ("A03", "A04", "A05", "A06", "A07", "A08", "A09", "N10", "W02")
METER = ("billed (list 2001-01-01) · head $12.34 · lanes $4.22 · session $16.56 · rewrites 3 "
         "($0.30) · tool uses/call head 2.00 lanes 4.00 · delegation multi (owner) · lanes 1 "
         "(reasons: (a)×1 (b)×0 (c)×0 (d)×0, none×0) · metered 1 of 1")
TWO_LINES = ("Current session: %s%% used · resets Oct 5 at 8pm (Europe/London)\n"
             "Current week (all models): 30%% used · resets Oct 9 at 9am (Europe/London)\n")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HARNESS = os.path.join(HERE, "test_limit_defaults.py")
if not os.path.isfile(HARNESS):
    print("PROBE FAILED: no test_limit_defaults.py (package B's harness) beside %s" % __file__)
    sys.exit(2)
B = load(HARNESS, "limit_defaults_harness")

# The GPT stand-in with one more mode: it appends a phase-boundary to the record before it answers.
GPT_STUB = B.GPT_STUB.replace(
    '        if mode == "closeduring":',
    '        if mode == "boundaryduring":\n'
    '            with open(read("close_record", ""), "a") as h:\n'
    '                h.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "run": read("close_run", ""),\n'
    '                                    "event": "phase-boundary", "from": "item1", "to": "item-during"}) + "\\n")\n'
    '            mode = "figure"\n'
    '        if mode == "closeduring":')
# The Claude stand-in with a slow mode that stamps its start and end.
CU_STUB = B.CU_STUB.replace(
    'if mode == "fail":',
    'if mode == "slow":\n'
    '    open(os.path.join(d, "starts"), "a").write("%.3f\\n" % time.time())\n'
    '    time.sleep(3)\n'
    '    open(os.path.join(d, "ends"), "a").write("%.3f\\n" % time.time())\n'
    'if mode == "fail":').replace("import os, sys", "import os, sys, time")
# A git stand-in that appends one helper close to the record the first time it runs: a line
# written after the close's cutoff and before its run-close.
GIT_STUB = r'''#!{py}
import json, os, sys, time
guard = os.environ["LATE_GUARD"]
if not os.path.exists(guard):
    open(guard, "w").write("1")
    with open(os.environ["LATE_RECORD"], "a") as h:
        h.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "run": os.environ["LATE_RUN"],
                            "event": "lane-closed", "lane": "LATE", "exit_class": "completed",
                            "total_cost_usd": 9.0, "close_id": "late-1"}) + "\n")
sys.exit(1)
'''


class Fx(B.Fx):
    def __init__(self, suite, tag):
        B.Fx.__init__(self, suite, tag)
        for name, body in (("gpt-server", GPT_STUB), ("cu", CU_STUB), ("git", GIT_STUB)):
            path = self.path("bin", name)
            with open(path, "w") as h:
                h.write(body.replace("{py}", sys.executable))
            os.chmod(path, 0o755)
        self.set("cu", "text", TWO_LINES % 34)

    def boundary(self, run, frm, to, *extra, env=None):
        return self.h("boundary", "--run", run, "--from", frm, "--to", to, "--disposition", "fixture",
                      "--waste", "none", "--next", "fixture next", "--meter-line", METER,
                      "--handoff", self.handoff(run), *extra, env=env)

    def close(self, run, *extra, env=None):
        return self.h("close", "--run", run, "--items", "item1=10k", "--meter-line", METER,
                      "--handoff", self.handoff(run), *extra, env=env)


def kinds(events, kind, **match):
    return B.kinds(events, kind, **match)


class Suite(B.Suite):
    def __init__(self, args):
        B.Suite.__init__(self, args)
        self.vault = os.path.realpath(args.vault or os.environ.get("CLAUDE_PROJECT_DIR")
                                      or os.path.join(self.W, os.pardir, os.pardir, os.pardir))
        self.U = os.path.join(self.W, "usage_windows.py")
        try:
            self.uw = load(self.U, "usage_windows_under_test") if os.path.isfile(self.U) else None
            self.ru = load(self.R, "read_usage_under_test")
        except Exception as exc:   # a module that does not load is a broken premise; the root goes
            shutil.rmtree(self.root, ignore_errors=True)
            raise B.Probe("a module under test does not load: %s: %s" % (type(exc).__name__, exc))

    def need(self, gid):
        if self.uw is None:
            self.check(gid, "usage_windows.py exists beside the wrappers", False,
                       "no usage_windows.py under %s (the meter is absent)" % self.W)
            return False
        return True

    # ------------------------------------------------------------------ A03 -------------------
    def a03(self):
        fx = Fx(self, "a03")
        run = "ra3"
        fx.set("cu", "mode", "slow")
        fx.set("gpt", "mode", "fail")
        p0 = fx.open_run(run)
        p1 = fx.boundary(run, "item1", "item2")
        p2 = fx.boundary(run, "item2", "item3")
        p3 = fx.close(run)
        ev = fx.events(run)
        carriers = [e for e in ev if isinstance(e.get("usage_reading"), dict)]
        names = [e.get("event") for e in carriers]
        self.check("A03", "run-open, two boundaries and a close: four readings, each embedded in exactly "
                   "those events",
                   [p.returncode for p in (p0, p1, p2, p3)] == [0, 0, 0, 0]
                   and names == ["run-open", "phase-boundary", "phase-boundary", "run-close"],
                   {"rc": [p.returncode for p in (p0, p1, p2, p3)], "carriers": names,
                    "err": (p0.stderr + p1.stderr + p3.stderr)[-500:]})
        extra = sorted({e.get("event") for e in ev} - {"run-open", "phase-boundary", "run-close"})
        self.check("A03", "no companion events (the readings ride the events themselves)",
                   not extra and not any("usage" in str(e.get("event")) for e in ev), extra)
        starts = [float(x) for x in open(os.path.join(fx.dirs["cu"], "starts")).read().split()] \
            if os.path.exists(os.path.join(fx.dirs["cu"], "starts")) else []
        b1 = kinds(ev, "phase-boundary")[0] if kinds(ev, "phase-boundary") else {}
        r1 = b1.get("usage_reading") or {}
        ev_ts = time.mktime(time.strptime(b1["ts"][:19], "%Y-%m-%dT%H:%M:%S")) if b1.get("ts") else None
        self.check("A03", "the reader starts before the dollar work and finishes after it began (the "
                   "event is built after meter_line, during the 3 s reading)",
                   ev_ts is not None and r1.get("started_ts") is not None
                   and r1["started_ts"] <= ev_ts + 1 and r1.get("finished_ts", 0) >= ev_ts
                   and r1.get("finished_ts", 0) - r1["started_ts"] >= 2.5,
                   {"reading": {k: r1.get(k) for k in ("started_ts", "finished_ts")}, "event_ts": ev_ts})
        self.check("A03", "everything ends inside the one deadline (95 s) and the valid window survives "
                   "the failed one",
                   all(isinstance(c["usage_reading"].get("elapsed_s"), (int, float))
                       and c["usage_reading"]["elapsed_s"] < 95 for c in carriers)
                   and all(c["usage_reading"]["windows"]["claude_5h"]["status"] == "measured"
                           and c["usage_reading"]["windows"]["gpt_week"]["status"] == "unmeasured"
                           for c in carriers) and len(carriers) == 4,
                   [(c.get("event"), c["usage_reading"].get("elapsed_s"),
                     {w: c["usage_reading"]["windows"][w]["status"] for w in c["usage_reading"]["windows"]})
                    for c in carriers])
        observed = fx.count("cu")
        # Clean: a dry run of each command, a gate and a run-resume take no reading.
        fx.set("cu", "mode", "text")
        run2 = "ra3c"
        q0 = fx.open_run(run2)
        base = fx.count("cu")
        before = open(fx.record(run2), "rb").read()
        d1 = fx.boundary(run2, "item1", "item2", "--dry-run")
        d2 = fx.close(run2, "--dry-run")
        d3 = fx.h("run-open", "--envelope-usd", "1000", "--run", "ra3d", "--session", "sid-ra3d", "--head", "fixture head",
                  "--regime", "single", "--regime-src", "owner", "--handoff", fx.handoff("ra3d"),
                  "--detail", "fixture", "--pid", "1", "--viewer", "none", "--dry-run")
        g = fx.h("gate", "--run", run2, "--to", "item2", "--meter-line", METER)
        rr = fx.h("run-resume", "--run", run2, "--session", "sid-later", "--head", "later head",
                  "--detail", "fixture", "--pid", "1")
        after = fx.count("cu")
        dry_close = d2.stdout
        self.check("A03", "clean: dry runs of run-open, boundary and close, a gate and a run-resume take "
                   "zero readings (control: the four real commands above took four)",
                   observed == 4 and q0.returncode == 0 and after == base and d1.returncode == 0
                   and d2.returncode == 0 and d3.returncode == 0 and '"usage_reading": null' in d1.stdout
                   and '"usage_reading_reason": "dry-run"' in dry_close,
                   {"observed": observed, "dry/gate/resume reads": after - base,
                    "rc": [d1.returncode, d2.returncode, d3.returncode, g.returncode, rr.returncode],
                    "err": (d1.stderr + d2.stderr + d3.stderr)[-400:]})
        self.check("A03", "the dry runs leave the record's bytes as they were (gate and run-resume add their "
                   "own events only, none carrying a reading)",
                   not any("usage_reading" in e for e in fx.events(run2)[1:])
                   and open(fx.record(run2), "rb").read().startswith(before),
                   [e.get("event") for e in fx.events(run2)])

    # ------------------------------------------------------------------ A04 -------------------
    def reading(self, figures, reset="resets Oct 5 at 8pm", t0=1000.0, t1=1001.0, sources=None,
                status=None):
        uw = self.uw
        obj = {"windows": {}}
        for w in uw.WINDOWS:
            fig = figures.get(w)
            obj["windows"][w] = {"used_pct": fig, "reset_text": reset if fig is not None else None,
                                 "status": (status or {}).get(w, "measured" if fig is not None else "unmeasured"),
                                 "reason": None if fig is not None else "fixture",
                                 "source": (sources or {}).get(w, w)}
        return uw.reading_from_object(obj, t0, t1, 0)

    def a04(self):
        if not self.need("A04"):
            return
        uw = self.uw
        one = {"claude_5h": 10}
        r1 = self.reading(one)
        r2 = self.reading({"claude_5h": 13}, t0=1010.0, t1=1011.0)
        d = uw.sample_delta(r1, r2)["claude_5h"]
        self.check("A04", "hit control: the same reset, 10 then 13, gives 3 pp",
                   d["delta_pp"] == 3 and d["reason"] is None, d)
        cases = [
            ("a changed reset", r1, self.reading({"claude_5h": 13}, reset="resets Oct 6 at 8pm", t0=1010, t1=1011),
             "reset changed"),
            ("an empty reset", r1, self.reading({"claude_5h": 13}, reset="", t0=1010, t1=1011), "reset unstated"),
            ("a falling counter", r1, self.reading({"claude_5h": 7}, t0=1010, t1=1011), "counter decreased"),
            ("a scope mismatch", r1, self.reading({"claude_5h": 13}, sources={"claude_5h": "elsewhere"},
                                                  t0=1010, t1=1011), "scope changed"),
            ("overlapping observations", r1, self.reading({"claude_5h": 13}, t0=1000.5, t1=1011),
             "overlapping observations"),
            ("a span of at least one window", r1, self.reading({"claude_5h": 13}, t0=1000 + 300 * 60,
                                                               t1=1001 + 300 * 60), "span at least one window"),
            ("no predecessor", None, r2, "first reading"),
        ]
        for name, a, b, reason in cases:
            got = uw.sample_delta(a, b)["claude_5h"]
            self.check("A04", "%s gives null with reason %r" % (name, reason),
                       got["delta_pp"] is None and got["reason"] == reason, got)
        failed = uw.failed_reading("stand-in failure", 1005.0, 1006.0)
        mid = uw.sample_delta(failed, r2)["claude_5h"]
        self.check("A04", "a failed middle reading is the predecessor, not skipped: unmeasured predecessor",
                   mid["delta_pp"] is None and mid["reason"] == "unmeasured predecessor", mid)
        events = [{"event": "run-open", "usage_reading": r1},
                  {"event": "phase-boundary", "usage_reading": failed},
                  {"event": "phase-boundary"}]
        self.check("A04", "the predecessor chosen from a record is the failed reading, and an event "
                   "without a reading is passed over",
                   uw.previous_reading(events) is failed, uw.previous_reading(events))
        sub = uw.coverage([{"event": "run-open", "usage_reading": r1, "usage_delta": uw.sample_delta(None, r1)},
                           {"event": "phase-boundary", "usage_reading": failed,
                            "usage_delta": uw.sample_delta(r1, failed)},
                           {"event": "phase-boundary", "usage_reading": r2,
                            "usage_delta": uw.sample_delta(failed, r2)}], "claude_5h")
        self.check("A04", "no gap is bridged with zero: the subtotal over a failed middle is none with 2 gaps",
                   sub == (0.0, 0, 2), sub)

    # ------------------------------------------------------------------ N10 -------------------
    def n10(self):
        if not self.need("N10"):
            return
        uw, ru = self.uw, self.ru
        line = "Current session: %d%% used · resets Oct 5 at 8pm (Europe/London)"
        w34 = ru.parse_claude_windows([line % 34])
        w35 = ru.parse_claude_windows([line % 35])

        def obj(w):
            return {"windows": dict(w, gpt_week={"used_pct": None, "reset_text": None,
                                                 "status": "not_requested", "reason": "x", "source": None})}
        a = uw.reading_from_object(obj(w34), 1000.0, 1001.0, 0)
        b = uw.reading_from_object(obj(w35), 1010.0, 1011.0, 0)
        d = uw.sample_delta(a, b)["claude_5h"]
        self.check("N10", "two one-line readings, 34 % then 35 %, through B's parser and A's delta give 1 pp "
                   "(the source is the canonical window name, the heading kept apart)",
                   d["delta_pp"] == 1 and a["windows"]["claude_5h"]["source"] == "claude_5h"
                   and a["windows"]["claude_5h"].get("heading") == line % 34, d)
        for r in (a, b):
            r["windows"]["claude_5h"]["source"] = r["windows"]["claude_5h"]["heading"]
        ctl = uw.sample_delta(a, b)["claude_5h"]
        self.check("N10", "positive control: keying the source on the literal heading gives scope changed",
                   ctl["reason"] == "scope changed", ctl)
        fx = Fx(self, "n10")
        run = "rn10"
        fx.set("gpt", "mode", "fail")
        fx.open_run(run)
        fx.set("cu", "text", TWO_LINES % 34)
        p1 = fx.boundary(run, "item1", "item2")
        fx.set("cu", "text", TWO_LINES % 35)
        p2 = fx.boundary(run, "item2", "item3")
        bs = kinds(fx.events(run), "phase-boundary")
        got = (bs[-1].get("usage_delta") or {}).get("claude_5h") if len(bs) == 2 else None
        self.check("N10", "end to end through the wrappers: a boundary at 34 % then one at 35 % records 1 pp",
                   p1.returncode == 0 and p2.returncode == 0 and got is not None and got.get("delta_pp") == 1,
                   {"rc": [p1.returncode, p2.returncode], "delta": got, "err": (p1.stderr + p2.stderr)[-300:]})

    # ------------------------------------------------------------------ A05 -------------------
    def lane_dry(self, fx, run, lane, *extra):
        if not os.path.exists(fx.path("lane-home", "lane-settings.json")):
            # lane.py's premises for a dry spawn: the vault contract (read from --vault, copied into
            # the fixture vault), the lane core from the wrappers' templates, then `lane.py init`.
            contract = os.path.join(self.vault, "CLAUDE.md")
            core = os.path.join(self.W, "templates", "lane-core.md")
            for need in (contract, core):
                if not os.path.isfile(need):
                    raise B.Probe("lane.py's dry spawn needs %s (pass --vault)" % need)
            shutil.copy2(contract, os.path.join(fx.vault, "CLAUDE.md"))
            tdir = os.path.join(fx.vault, ".claude", "skills", "delegate", "templates")
            os.makedirs(tdir, exist_ok=True)
            shutil.copy2(core, os.path.join(tdir, "lane-core.md"))
            init = self.run([sys.executable, "-B", os.path.join(self.W, "lane.py"), "init"], fx.env(), 60,
                            cwd=fx.root)
            if init.returncode != 0:
                raise B.Probe("lane.py init in the fixture lane home failed: %s" % init.stderr[-300:])
        p = self.run([sys.executable, "-B", os.path.join(self.W, "lane.py"), "spawn", "--run", run,
                      "--lane", lane, "--class", "critic", "--brief", fx.path("brief.md"),
                      "--reason", "(a) suite", "--model", "opus", "--effort", "high",
                      "--choice-reason", "suite pick", "--viewer", "none", "--expect-usd", "5",
                      "--delegation", "single", "--delegation-src", "head", "--grant",
                      fx.path("brief.md"), "--dry-run"] + list(extra),
                     fx.env(), 60, cwd=fx.root)
        line = None
        out = p.stdout.splitlines()
        for i, text in enumerate(out):
            if text.startswith("record line") and i + 1 < len(out):
                try:
                    line = json.loads(out[i + 1].strip())
                except ValueError:
                    pass
        return p, line

    def a05(self):
        fx = Fx(self, "a05")
        run = "ra5"
        fx.set("gpt", "figure", "40")
        fx.open_run(run)
        spawn = lambda lane, *extra: B.Suite.spawn(self, fx, run, lane, *extra)
        p0 = spawn("C0")
        lp0, l0 = self.lane_dry(fx, run, "K0")
        fx.boundary(run, "item1", "item2")
        p1 = spawn("C1")
        p2 = spawn("C2", "--item", "item-explicit")
        lp1, l1 = self.lane_dry(fx, run, "K1")
        lp2, l2 = self.lane_dry(fx, run, "K2", "--item", "item-explicit")
        opens = {e["lane"]: e for e in kinds(fx.events(run), "lane-open")}
        # The lane-open's inferred item rides under usage_item* (DW-20261021-2's rename: the
        # console reads the launchers' own `item` as a named item); the explicit `item` stays.
        got = {k: (opens.get(k, {}).get("usage_item"), opens.get(k, {}).get("usage_item_source"))
               for k in ("C0", "C1", "C2")}
        got.update({"K0": (l0 or {}).get("usage_item"),
                    "K1": ((l1 or {}).get("usage_item"), (l1 or {}).get("usage_item_source")),
                    "K2": ((l2 or {}).get("usage_item"), (l2 or {}).get("usage_item_source"))})
        self.check("A05", "Codex spawns before any boundary, at a boundary without --item, and with --item: "
                   "unassigned, inferred, explicit",
                   [p.returncode for p in (p0, p1, p2)] == [0, 0, 0]
                   and got["C0"] == (None, "unassigned") and got["C1"] == ("item2", "inferred")
                   and got["C2"] == ("item-explicit", "explicit")
                   and opens.get("C1", {}).get("usage_item_locator", {}).get("to") == "item2"
                   and "item" not in opens.get("C1", {})
                   and opens.get("C2", {}).get("item") == "item-explicit",
                   {"got": got, "rc": [p.returncode for p in (p0, p1, p2)], "err": (p0.stderr + p1.stderr)[-400:]})
        self.check("A05", "Claude (lane.py) spawns, the same three cases on the lane-open line",
                   lp0.returncode == 0 and lp1.returncode == 0 and lp2.returncode == 0
                   and (l0 or {}).get("usage_item_source") == "unassigned" and got["K1"] == ("item2", "inferred")
                   and got["K2"] == ("item-explicit", "explicit"),
                   {"got": got, "rc": [lp0.returncode, lp1.returncode, lp2.returncode],
                    "err": lp0.stderr[-600:]})
        # A boundary committed during the GPT start check's reading is seen by the lane-open.
        fx.set("gpt", "mode", "boundaryduring")
        fx.set("gpt", "close_record", fx.record(run))
        fx.set("gpt", "close_run", run)
        p3 = spawn("C3")
        fx.set("gpt", "mode", "figure")
        o3 = {e["lane"]: e for e in kinds(fx.events(run), "lane-open")}.get("C3", {})
        self.check("A05", "a stand-in GPT client that appends a phase-boundary before it answers: the Codex "
                   "lane-open carries that new boundary's to",
                   p3.returncode == 0 and o3.get("usage_item") == "item-during"
                   and o3.get("usage_item_source") == "inferred",
                   {"rc": p3.returncode, "item": o3.get("usage_item"), "src": o3.get("usage_item_source"),
                    "err": p3.stderr[-300:]})
        # After another boundary, a resume keeps the first item, and so does a beat (accounting).
        fx.boundary(run, "item-during", "item4")
        pr = fx.c("resume", "--run", run, "--lane", "C1", "--brief", fx.path("follow.md"),
                  "--codex", fx.path("bin", "codex"), "--viewer", "none")
        ev = fx.events(run)
        resumed = kinds(ev, "lane-resumed", lane="C1")
        planted = list(ev) + [{"event": "hold-beat", "lane": "C1", "harness": "codex", "invocation_id": "b1",
                               "usage": {"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 1},
                               "usage_state": "complete"}]
        rows = {h["lane"]: h for h in self.uw.close_accounting(planted, None)["usage_helpers"]} if self.uw else {}
        self.check("A05", "after another boundary, a resume and a beat keep the lane's first item",
                   pr.returncode == 0 and resumed and "usage_item" not in resumed[-1]
                   and rows.get("C1", {}).get("item") == "item2"
                   and rows.get("C1", {}).get("passes") == 3,
                   {"rc": pr.returncode, "resumed": [r.get("usage_item") for r in resumed],
                    "row": {k: rows.get("C1", {}).get(k) for k in ("item", "item_source", "passes")},
                    "err": pr.stderr[-300:]})
        legacy = [{"event": "run-open"}, {"event": "phase-boundary", "from": "a", "to": "itemL"},
                  {"event": "lane-open", "lane": "OLD", "harness": "claude", "model": "m", "effort": "e",
                   "class": "critic"},
                  {"event": "phase-boundary", "from": "itemL", "to": "itemM"},
                  {"event": "lane-closed", "lane": "OLD", "total_cost_usd": 1.0, "close_id": "o1"}]
        row = self.uw.close_accounting(legacy, None)["usage_helpers"][0] if self.uw else {}
        self.check("A05", "a legacy open is inferred from the record before it, labelled inferred-legacy",
                   row.get("item") == "itemL" and row.get("item_source") == "inferred-legacy", row)
        succ = self.uw.item_at_open(legacy[:2], None, source_pass="pass-7") if self.uw else {}
        plain = self.uw.item_at_open(legacy[:2], None) if self.uw else {}
        self.check("A05", "an A3 successor's open records that its item is set at its own open, never "
                   "forwarded (control: a plain open carries no note)",
                   succ.get("usage_item") == "itemL" and "pass-7" in str(succ.get("usage_item_note"))
                   and "never forwarded" in str(succ.get("usage_item_note")) and "usage_item_note" not in plain,
                   {"successor": succ, "plain": plain})

    # ------------------------------------------------------------------ A06 -------------------
    def a06(self):
        if not self.need("A06"):
            return
        uw = self.uw

        def cx(lane, usage, state="complete", cid=None):
            return {"event": "lane-closed", "lane": lane, "harness": "codex", "usage": usage,
                    "usage_state": state, "close_id": cid or lane + "-c"}

        def op(lane, harness="codex"):
            return {"event": "lane-open", "lane": lane, "harness": harness, "model": "m", "effort": "e",
                    "class": "critic", "item": "i", "item_source": "explicit"}
        ev = [op("S"), cx("S", {"input_tokens": 1000, "cached_input_tokens": 900, "output_tokens": 200}),
              op("X"), cx("X", {"input_tokens": 100, "cached_input_tokens": 200, "output_tokens": 5}),
              op("M"), cx("M", None, "missing"),
              op("I"), cx("I", {"input_tokens": 50, "cached_input_tokens": 10, "output_tokens": 5}, "incomplete"),
              op("Z"), cx("Z", {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}),
              op("CN", "claude"), {"event": "lane-closed", "lane": "CN", "total_cost_usd": None, "close_id": "n1"},
              op("CD", "claude"), {"event": "lane-closed", "lane": "CD", "total_cost_usd": 2.5, "close_id": "d1"},
              {"event": "lane-closed", "lane": "CD", "total_cost_usd": 2.5, "close_id": "d1"},
              {"event": "hold-beat", "lane": "CD", "observation_only": True, "invocation_id": "sb",
               "total_cost_usd": 7.0},
              op("CS", "claude"), {"event": "lane-closed", "lane": "CS", "total_cost_usd": 1.25, "close_id": "s1"},
              {"event": "lane-resumed", "lane": "CS"},
              {"event": "lane-closed", "lane": "CS", "total_cost_usd": 0.75, "close_id": "s2"}]
        rows = {h["lane"]: h for h in uw.close_accounting(ev, None)["usage_helpers"]}
        s = rows["S"]["quantities"]
        self.check("A06", "cached 900 of input 1,000 with output 200 splits 100 / 900 / 200 (not 1,000 / 900 / 200)",
                   [round(s[u] * 1e6) for u in ("fresh_input_mtokens", "cached_input_mtokens", "output_mtokens")]
                   == [100, 900, 200] and rows["S"]["complete"], s)
        self.check("A06", "cached above input is incomplete", rows["X"]["complete"] is False
                   and "cached" in " ".join(rows["X"]["incomplete"]), rows["X"])
        self.check("A06", "every Codex row reads split_complete unverified (N9)",
                   all(rows[k].get("split_complete") == "unverified" for k in ("S", "X", "M", "I", "Z"))
                   and "split_complete" not in rows["CD"], {k: rows[k].get("split_complete") for k in rows})
        self.check("A06", "a missing and an incomplete Codex close are incomplete; a complete zero close is "
                   "complete zero",
                   rows["M"]["complete"] is False and rows["I"]["complete"] is False
                   and rows["Z"]["complete"] is True and set(rows["Z"]["quantities"].values()) == {0.0},
                   {k: (rows[k]["complete"], rows[k]["incomplete"]) for k in ("M", "I", "Z")})
        self.check("A06", "a null Claude cost stays unknown (incomplete), never zero",
                   rows["CN"]["complete"] is False and "cost unknown" in " ".join(rows["CN"]["incomplete"]),
                   rows["CN"])
        self.check("A06", "a duplicate close counts once and an observation_only beat is excluded",
                   rows["CD"]["quantities"]["usd_list"] == 2.5 and rows["CD"]["passes"] == 1, rows["CD"])
        self.check("A06", "sum controls: two distinct per-pass Claude costs sum (2.0) and a complete non-zero "
                   "Codex close is complete",
                   rows["CS"]["quantities"]["usd_list"] == 2.0 and rows["CS"]["passes"] == 2
                   and rows["S"]["complete"] is True, (rows["CS"]["quantities"], rows["CS"]["passes"]))

    # ------------------------------------------------------------------ A07 -------------------
    def plan(self, expected=(4, 6), rate=(0.1, 0.2), windows=("claude_5h",), model="m"):
        return {"schema": 1,
                "rates": [{"id": "r1", "family": "claude", "model": model, "effort": "e", "class": "critic",
                           "workload": "fixture", "basis": "fixture rates, " + "set by judgement, unmeasured",
                           "pp_per_unit": {w: {"usd_list": {"low": rate[0], "high": rate[1]}} for w in windows}}],
                "helpers": [{"lane": "H", "item": "i", "family": "claude", "model": model, "effort": "e",
                             "class": "critic", "rate_id": "r1",
                             "expected_units": {"usd_list": {"low": expected[0], "high": expected[1]}}}]}

    def helper(self, cost, plan, model="m", extra=()):
        ev = [{"event": "lane-open", "lane": "H", "harness": "claude", "model": model, "effort": "e",
               "class": "critic", "item": "i", "item_source": "explicit"},
              {"event": "lane-closed", "lane": "H", "total_cost_usd": cost, "close_id": "h1"}] + list(extra)
        return self.uw.close_accounting(ev, plan)

    def a07(self):
        if not self.need("A07"):
            return
        near = lambda a, b: a is not None and abs(a - b) < 1e-9
        res = {}
        for actual in (8, 13, 6, 3):
            acc = self.helper(actual, self.plan())
            h = acc["usage_helpers"][0]
            res[actual] = (h["units"]["usd_list"], h["shares"]["claude_5h"]["difference"])
        u8, d8 = res[8]
        self.check("A07", "H2: actual 8 against 4-6 at 0.1-0.2 pp: overrun true, d = 2, D = 0.2-0.4 pp",
                   u8["overrun"] is True and near(u8["d"], 2) and near(d8["low"], 0.2) and near(d8["high"], 0.4), res[8])
        u13, d13 = res[13]
        self.check("A07", "H2: actual 13 gives D = 0.7-1.4 pp", u13["overrun"] is True and near(d13["low"], 0.7)
                   and near(d13["high"], 1.4), res[13])
        self.check("A07", "H2: actual 6 gives overrun false", res[6][0]["overrun"] is False, res[6])
        u3, d3 = res[3]
        self.check("A07", "a negative component reverses its interval (actual 3: d = -3, D = -0.6 to -0.3 pp)",
                   near(u3["d"], -3) and near(d3["low"], -0.6) and near(d3["high"], -0.3), res[3])
        inc = self.helper(8, self.plan(), extra=[{"event": "lane-resumed", "lane": "H"},
                                                 {"event": "lane-closed", "lane": "H", "total_cost_usd": None,
                                                  "close_id": "h2"}])
        iu = inc["usage_helpers"][0]["units"]["usd_list"]
        self.check("A07", "an incomplete 8 gives null, with its reason", iu["overrun"] is None and iu["reason"], iu)
        two = self.helper(10, self.plan(expected=(10, 10), windows=()) if False else {
            "schema": 1,
            "rates": [{"id": "r1", "family": "claude", "model": "m", "effort": "e", "class": "critic",
                       "workload": "fixture", "basis": "set by judgement, unmeasured",
                       "pp_per_unit": {"claude_5h": {"usd_list": {"low": 0.5, "high": 1.0}},
                                       "claude_week": {"usd_list": {"low": 0.05, "high": 0.1}}}}],
            "helpers": [{"lane": "H", "item": "i", "family": "claude", "model": "m", "effort": "e",
                         "class": "critic", "rate_id": "r1",
                         "expected_units": {"usd_list": {"low": 10, "high": 10}}}]})
        sh = two["usage_helpers"][0]["shares"]
        tot = two["usage_totals"]["shares"]
        e5, ew = sh["claude_5h"]["expected"], sh["claude_week"]["expected"]
        flat = json.dumps(two)
        self.check("A07", "N6: a two-window Claude rate gives 5-10 pp and 0.5-1.0 pp separately, never 5.5-11",
                   near(e5["low"], 5) and near(e5["high"], 10) and near(ew["low"], 0.5) and near(ew["high"], 1.0)
                   and near(tot["claude_5h"]["expected"]["high"], 10) and near(tot["claude_week"]["expected"]["high"], 1.0)
                   and "5.5" not in flat and '"high": 11' not in flat, {"helper": sh, "totals": tot})
        none = self.helper(8, None)
        self.check("A07", "a missing plan reads unestimated, with no unit comparison",
                   none["usage_totals"]["estimate"] == "unestimated" and "units" not in none["usage_helpers"][0],
                   none["usage_totals"])
        miss = self.plan()
        miss["helpers"][0]["rate_id"] = "absent"
        mr = self.helper(8, miss)
        self.check("A07", "a missing rate makes the estimate partial, never an expected zero",
                   mr["usage_totals"]["estimate"] == "partial" and mr["usage_helpers"][0]["plan"] == "no rate"
                   and "shares" not in mr["usage_helpers"][0], mr["usage_totals"])
        mm = self.helper(8, self.plan(), model="other")
        self.check("A07", "exact matching: a helper whose model differs from its planned row gets no guessed rate",
                   mm["usage_helpers"][0]["plan"] == "mismatch" and "units" not in mm["usage_helpers"][0]
                   and mm["usage_totals"]["estimate"] == "partial", mm["usage_helpers"][0].get("mismatch"))
        # CR-MET-BA2 F3: actual shares are computed apart from the expected ones; a missing
        # expectation makes the estimate partial and is carried into the item and run totals.
        def gpt_plan(units):
            return {"schema": 1,
                    "rates": [{"id": "g1", "family": "gpt", "model": "gm", "effort": "e", "class": "builder",
                               "workload": "fixture", "basis": "fixture rates, set by judgement, unmeasured",
                               "pp_per_unit": {"gpt_week": {"fresh_input_mtokens": {"low": 0.1, "high": 0.2},
                                                            "output_mtokens": {"low": 0.1, "high": 0.2}}}}],
                    "helpers": [{"lane": "G", "item": "i", "family": "gpt", "model": "gm", "effort": "e",
                                 "class": "builder", "rate_id": "g1", "expected_units": units}]}
        gev = [{"event": "lane-open", "lane": "G", "harness": "codex", "model": "gm", "effort": "e",
                "class": "builder", "item": "i", "item_source": "explicit"},
               {"event": "lane-closed", "lane": "G", "close_id": "g1", "usage_state": "complete",
                "usage": {"input_tokens": 10000000, "cached_input_tokens": 0, "output_tokens": 1000000}}]
        part = self.uw.close_accounting(gev, gpt_plan({"fresh_input_mtokens": {"low": 5, "high": 10}}))
        full = self.uw.close_accounting(gev, gpt_plan({"fresh_input_mtokens": {"low": 5, "high": 10},
                                                       "output_mtokens": {"low": 0.5, "high": 1}}))
        pa = part["usage_helpers"][0]["shares"]["gpt_week"]
        fa = full["usage_helpers"][0]["shares"]["gpt_week"]
        pt, ft = part["usage_totals"], full["usage_totals"]
        pi = part["usage_items"]["i"]["shares"]["gpt_week"]
        self.check("A07", "F3 (BA2): a partial GPT plan's actual counts every rated component (10 fresh and 1 "
                   "output Mtok at 0.1-0.2 pp = 1.1-2.2 pp), the same as with the expectation supplied",
                   (pa.get("actual") or {}).get("low") is not None and near(pa["actual"]["low"], 1.1)
                   and near(pa["actual"]["high"], 2.2) and pa["actual"] == fa.get("actual"),
                   {"partial": pa, "full": fa})
        self.check("A07", "F3 (BA2): the missing expectation makes the estimate partial and is carried into "
                   "the item and run totals, never an estimate labelled complete",
                   pt["estimate"] == "partial" and any("no expected output_mtokens" in x for x in pt["partial"])
                   and "G: no expected output_mtokens" in (pt["shares"]["gpt_week"].get("partial") or [])
                   and "G: no expected output_mtokens" in (pi.get("partial") or []),
                   {"totals": pt, "item": pi})
        self.check("A07", "F3 control: with every expectation supplied the estimate is complete, no partial "
                   "marker appears and the expected share is 0.55-2.2 pp",
                   ft["estimate"] == "complete" and not ft["partial"]
                   and "partial" not in ft["shares"]["gpt_week"] and near(fa["expected"]["low"], 0.55)
                   and near(fa["expected"]["high"], 2.2), ft)
        # CR-MET-BA2 F4: every Codex row carries split_complete, a planned helper that never opened too.
        never = self.uw.close_accounting([], gpt_plan({"fresh_input_mtokens": {"low": 5, "high": 10}}))
        nrow = never["usage_helpers"][0]
        self.check("A07", "F4 (BA2): a planned GPT helper that never opened carries split_complete "
                   "'unverified' (control: an opened GPT helper carries it too)",
                   nrow.get("item_source") == "planned, never opened"
                   and nrow.get("split_complete") == "unverified"
                   and part["usage_helpers"][0].get("split_complete") == "unverified",
                   {"never": nrow, "opened": part["usage_helpers"][0].get("split_complete")})
        # CR-MET-BA2 F2: the opening figure is run-open's own reading, never a later reading's.
        later = self.reading({"claude_5h": 34, "claude_week": 30, "gpt_week": None})
        legacy = [{"event": "run-open"},     # opened before the meter: no usage_reading key at all
                  {"event": "phase-boundary", "usage_reading": later,
                   "usage_delta": self.uw.sample_delta(None, later)}]
        lb = dict(self.uw.render_windows(legacy))
        first = self.reading({"claude_5h": 30, "claude_week": 29, "gpt_week": None}, t0=900.0, t1=901.0)
        metered = [{"event": "run-open", "usage_reading": first, "usage_delta": self.uw.sample_delta(None, first)},
                   {"event": "phase-boundary", "usage_reading": later,
                    "usage_delta": self.uw.sample_delta(first, later)}]
        mb = dict(self.uw.render_windows(metered))
        self.check("A07", "F2 (BA2): a run opened without a reading shows its opening as unmeasured, never the "
                   "first boundary's 34 %, while its latest is 34 % (control: a measured run-open shows its "
                   "own 30 %)",
                   str(lb.get("Claude 5-hour window", "")).startswith("opening unmeasured (no opening reading)")
                   and "opening 34" not in json.dumps(lb) and "latest 34 %" in str(lb.get("Claude 5-hour window"))
                   and str(mb.get("Claude 5-hour window", "")).startswith("opening 30 %"),
                   {"legacy": lb, "metered": mb})
        # Zero overrun delivery: a real close over a planned helper that overran.
        fx = Fx(self, "a07")
        run = "ra7"
        fx.set("gpt", "mode", "fail")
        plan_path = fx.path("plan.json")
        plan = self.plan()
        plan["helpers"][0].update(lane="H", item="item2")
        with open(plan_path, "w") as h:
            json.dump({"schema": 1, "usage": {"rates": plan["rates"], "helpers": plan["helpers"]}}, h)
        p0 = fx.open_run(run, "--preflight-data", plan_path)
        fx.boundary(run, "item1", "item2")
        fx.append(run, {"event": "lane-open", "lane": "H", "harness": "claude", "model": "m", "effort": "e",
                        "class": "critic", "item": "item2", "item_source": "explicit"})
        fx.append(run, {"event": "lane-closed", "lane": "H", "total_cost_usd": 8.0, "close_id": "h1",
                        "exit_class": "completed"})
        g = fx.h("gate", "--run", run, "--to", "item3", "--meter-line", METER)
        report = fx.path("report.md")
        with open(report, "w") as h:
            h.write("# Run report\n\n## Spend\n\nThe head's prose.\n\n## Warnings\n\n- none\n")
        pc = fx.close(run, "--report", report)
        ev = fx.events(run)
        rc_ev = (kinds(ev, "run-close") or [{}])[-1]
        units = (rc_ev.get("usage_comparisons") or {}).get("units") or []
        text = (pc.stdout + pc.stderr + g.stdout + g.stderr + open(report).read()).lower()
        notices = [e for e in ev if "notice" in str(e.get("event")) or "warning" in str(e.get("event"))]
        self.check("A07", "the close record holds the overrun (8 against 4-6); stdout, stderr, the gate, the "
                   "report and the record's notices show zero overrun delivery",
                   p0.returncode == 0 and pc.returncode == 0 and units and units[0].get("overrun") is True
                   and "overrun" not in text and "expected" not in text and not notices,
                   {"rc": [p0.returncode, g.returncode, pc.returncode], "units": units,
                    "hits": [w for w in ("overrun", "expected") if w in text], "err": pc.stderr[-300:]})
        # Control: a real hard dollar stop still fires (the envelope gate refuses past the envelope).
        run2 = "ra7h"
        fx.open_run(run2)
        over = METER.replace("head $12.34", "head $150.00")
        g2 = fx.h("gate", "--run", run2, "--to", "item2", "--meter-line", over)
        self.check("A07", "control: the dollar hard stop still fires (a gate past the run's $100 envelope "
                   "refuses with a non-zero exit)",
                   g2.returncode != 0, {"rc": g2.returncode, "out": (g2.stdout + g2.stderr)[-300:]})

        # Decision E3: the run's backstop is shown in points of the Claude week at the rate the
        # record carries, with that rate's source named; no dollar figure on the owner's line; the
        # points read unmeasured where the record holds no Claude-week rate.
        bs = getattr(self.uw, "backstop", None)
        wk = self.plan(rate=(0.02, 0.03), windows=("claude_5h", "claude_week"))
        ro_ev = {"event": "run-open", "usage_plan": wk, "usage_plan_sha256": "ab" * 32}
        if bs is not None:
            t1, r1 = bs([ro_ev], 100.0, 20.0, False)
            t2, r2 = bs([{"event": "run-open"}], 100.0, 20.0, False)
            t3, r3 = bs([dict(ro_ev, usage_plan=self.plan(rate=(0.02, 0.03)))], 100.0, 20.0, False)
        else:
            t1 = t2 = t3 = "absent: usage_windows.backstop"
            r1 = r2 = r3 = {}
        self.check("A07", "E3: the backstop reads 2.0-3.0 points of the Claude week and the run so far 0.4-0.6 "
                   "points at the record's rate, its source named (run-open usage_plan, rate r1, sha256), "
                   "with no dollar figure on the line; the dollars stay in the machine row",
                   t1.startswith("backstop 2.0-3.0 points of the Claude week, run so far 0.4-0.6 points")
                   and "run-open usage_plan, Claude-week rate r1" in t1 and "abababababab" in t1
                   and "$" not in t1 and "usd" not in t1.lower()
                   and r1.get("envelope_usd") == 100.0 and r1.get("backstop_pp") == {"low": 2.0, "high": 3.0},
                   {"text": t1, "row": r1})
        self.check("A07", "E3: with no rate on the record the points read unmeasured with the reason, never a "
                   "typed constant (no attachment; an attachment with no Claude-week rate)",
                   "points of the Claude week: unmeasured (no pre-flight usage attachment" in t2
                   and "unmeasured (the pre-flight attachment on run-open states no Claude-week rate" in t3
                   and "$" not in t2 + t3 and r2.get("backstop_pp") is None and r3.get("backstop_pp") is None,
                   {"t2": t2, "t3": t3})
        fx = Fx(self, "a07e")
        fx.set("gpt", "mode", "fail")
        plan_path = fx.path("plan-week.json")
        with open(plan_path, "w") as h:
            json.dump({"schema": 1, "usage": {"rates": wk["rates"], "helpers": wk["helpers"]}}, h)
        fx.open_run("ra7e", "--preflight-data", plan_path)
        pb = fx.boundary("ra7e", "item1", "item2")
        pcl = fx.close("ra7e")
        evs = fx.events("ra7e")
        pbe = (kinds(evs, "phase-boundary") or [{}])[-1]
        line_b = [l for l in pb.stdout.splitlines() if l.startswith("usage windows:")]
        line_c = [l for l in pcl.stdout.splitlines() if l.startswith("usage windows:")]
        self.check("A07", "E3 in the boundary and the close: each summary line carries the backstop in points "
                   "at the record's rate (the fixture's $100 envelope at 0.02-0.03 = 2.0-3.0 points) and no "
                   "dollar figure; the boundary event keeps the dollars in usage_backstop",
                   pb.returncode == 0 and pcl.returncode == 0 and len(line_b) == 1 and len(line_c) == 1
                   and "backstop 2.0-3.0 points of the Claude week" in line_b[0] + line_c[0]
                   and "$" not in line_b[0] + line_c[0] and "usd" not in (line_b[0] + line_c[0]).lower()
                   and (pbe.get("usage_backstop") or {}).get("envelope_usd") == 100.0,
                   {"rc": [pb.returncode, pcl.returncode], "b": line_b, "c": line_c,
                    "field": pbe.get("usage_backstop"), "err": (pb.stderr + pcl.stderr)[-300:]})
        fx.open_run("ra7f")
        pf = fx.boundary("ra7f", "item1", "item2")
        line_f = [l for l in pf.stdout.splitlines() if l.startswith("usage windows:")]
        self.check("A07", "E3 control: a run opened without an attachment shows the backstop's points as "
                   "unmeasured on its boundary line",
                   pf.returncode == 0 and len(line_f) == 1
                   and "backstop in points of the Claude week: unmeasured" in line_f[0],
                   {"rc": pf.returncode, "line": line_f, "err": pf.stderr[-300:]})

    # ------------------------------------------------------------------ A08 -------------------
    def a08(self):
        fx = Fx(self, "a08")
        run = "ra8"
        fx.set("gpt", "mode", "fail")
        p0 = fx.open_run(run)
        fx.append(run, {"event": "lane-open", "lane": "U", "harness": "claude", "model": "m", "effort": "e",
                        "class": "critic", "item": None, "item_source": "unassigned"})
        fx.append(run, {"event": "lane-closed", "lane": "U", "total_cost_usd": 1.0, "close_id": "u1"})
        fx.boundary(run, "item1", "item2")
        fx.append(run, {"event": "lane-open", "lane": "P", "harness": "claude", "model": "m", "effort": "e",
                        "class": "critic", "item": "item2", "item_source": "inferred"})
        fx.append(run, {"event": "lane-open", "lane": "LATE", "harness": "claude", "model": "m", "effort": "e",
                        "class": "critic", "item": "item2", "item_source": "inferred"})
        hand = fx.handoff(run)
        env = fx.env(PATH=fx.bin + os.pathsep + os.environ.get("PATH", ""), LATE_GUARD=fx.path("late-guard"),
                     LATE_RECORD=fx.record(run), LATE_RUN=run)
        pc = fx.close(run, "--commit", "fixture close", env=env)
        raw = open(fx.record(run), "rb").read()
        ev = fx.events(run)
        rc_ev = (kinds(ev, "run-close") or [{}])[-1]
        cutoff = rc_ev.get("usage_cutoff_bytes")
        late_at = raw.find(b'"close_id": "late-1"')
        rows = {h["lane"]: h for h in rc_ev.get("usage_helpers") or []}
        self.check("A08", "a helper close written after the cutoff is outside coverage, and "
                   "usage_cutoff_bytes is the prefix length used",
                   pc.returncode == 0 and isinstance(cutoff, int) and late_at > cutoff
                   and rows.get("LATE", {}).get("passes") == 0 and rows.get("LATE", {}).get("complete") is False
                   and raw[:cutoff].count(b"\n") == len(raw[:cutoff].split(b"\n")) - 1
                   and b"late-1" not in raw[:cutoff],
                   {"rc": pc.returncode, "cutoff": cutoff, "late_at": late_at, "late": rows.get("LATE"),
                    "err": pc.stderr[-400:]})
        self.check("A08", "unassigned and pending work: the unassigned lane sits under item unassigned and "
                   "the open lane is incomplete (pending)",
                   "U" in ((rc_ev.get("usage_items") or {}).get("unassigned") or {}).get("helpers", [])
                   and "pending" in " ".join(rows.get("P", {}).get("incomplete", [])),
                   {"items": rc_ev.get("usage_items"), "P": rows.get("P")})
        text = open(hand).read()
        labels = ("Claude 5-hour window", "Claude weekly window", "GPT weekly window")
        once = all(text.count("- **%s:**" % l) == 1 for l in labels)
        uw = self.uw
        if uw is not None:
            lines = text.split("\n")
            i = next(j for j, l in enumerate(lines) if l.startswith("## Morning report"))
            end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
            again = uw.place_bullets(lines, i, end, uw.render_windows(ev[:-1] + [rc_ev]))
            twice = "\n".join(lines)
        else:
            again, twice = None, None
        self.check("A08", "rendered twice: the three bullets appear once each and a second render changes "
                   "nothing; other prose and the dollar line are unchanged",
                   once and again == [] and twice == text and "## In flight" in text
                   and "- **Spend against the envelope:** " + METER in text
                   and "fixture finding" in text,
                   {"counts": {l: text.count("- **%s:**" % l) for l in labels}, "again": again})
        if uw is not None:
            later = uw.failed_reading("stand-in failure", time.time(), time.time() + 1)
            prev = rc_ev.get("usage_reading")
            grown = ev + [{"event": "phase-boundary", "usage_reading": later,
                           "usage_delta": uw.sample_delta(prev, later)}]
            r1, r2 = dict(uw.render_windows(ev)), dict(uw.render_windows(grown))
        else:
            r1 = r2 = {}
        self.check("A08", "a window never measured keeps one bullet text after a further failed reading, so an "
                   "already-current page stays as it is (control: a measured window's bullet changes)",
                   bool(r1) and r1.get("GPT weekly window") == r2.get("GPT weekly window")
                   and "unmeasured" in str(r1.get("GPT weekly window"))
                   and r1.get("Claude 5-hour window") != r2.get("Claude 5-hour window"),
                   {"before": r1, "after": r2})
        dry = fx.close(run, "--dry-run")
        self.check("A08", "no comparison reaches the hand-off, the report or the close dry run",
                   "usage_comparisons" not in dry.stdout and "usage_helpers" not in dry.stdout
                   and "overrun" not in text and "usage_coverage" in dry.stdout,
                   {"rc": dry.returncode, "out": dry.stdout[-300:]})
        bad = fx.path("bad-plan.json")
        with open(bad, "w") as h:
            json.dump({"schema": 1, "usage": {"rates": [{"id": "r", "family": "claude"}], "helpers": []}}, h)
        hb = fx.handoff("ra8b")
        hb_before = open(hb, "rb").read()
        pb = fx.open_run("ra8b", "--preflight-data", bad)
        self.check("A08", "a malformed attachment fails before any write (PROBE FAILED, exit 2, no record, no "
                   "grants file, the hand-off unchanged)",
                   pb.returncode == 2 and "PROBE FAILED" in pb.stderr and "--preflight-data" in pb.stderr
                   and not os.path.exists(fx.record("ra8b")) and not os.path.exists(fx.grants("ra8b"))
                   and open(hb, "rb").read() == hb_before, {"rc": pb.returncode, "err": pb.stderr[-300:]})
        good = fx.path("good-plan.json")
        plan = self.plan() if uw is not None else {"rates": [], "helpers": []}
        with open(good, "w") as h:
            json.dump({"schema": 1, "usage": {"rates": plan["rates"], "helpers": plan["helpers"],
                                              "account_expectations": {"claude_5h": {"low": 30, "high": 40}},
                                              "explain_gap_pp": {"pp": 5, "provenance": "fixture"}}}, h)
        pg = fx.open_run("ra8g", "--preflight-data", good)
        ro = (kinds(fx.events("ra8g"), "run-open") or [{}])[0]
        self.check("A08", "control: a valid attachment is pinned with its digest",
                   pg.returncode == 0 and ro.get("usage_plan_sha256") == hashlib.sha256(open(good, "rb").read()).hexdigest()
                   and (ro.get("usage_plan") or {}).get("helpers", [{}])[0].get("lane") == "H",
                   {"rc": pg.returncode, "sha": ro.get("usage_plan_sha256"), "err": pg.stderr[-300:]})
        fx.legacy_run("ra8l")
        pl = fx.close("ra8l")
        lc = (kinds(fx.events("ra8l"), "run-close") or [{}])[-1]
        self.check("A08", "a legacy run without a plan or an opening reading reads unestimated, and its account "
                   "comparison is unknown",
                   pl.returncode == 0 and (lc.get("usage_totals") or {}).get("estimate") == "unestimated"
                   and ((lc.get("usage_comparisons") or {}).get("account") or {}).get("claude_5h", {}).get("status")
                   == "unknown", {"rc": pl.returncode, "totals": lc.get("usage_totals"), "err": pl.stderr[-300:]})

    # ------------------------------------------------------------------ W02 -------------------
    def w02(self, before):
        after = self.manifest(self.W)
        copy = os.path.join(self.root, "manifest-control")
        shutil.copytree(self.W, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        target = os.path.join(copy, "handsoff.py")
        data = bytearray(open(target, "rb").read())
        data[0:1] = b"#" if data[0:1] != b"#" else b"!"
        open(target, "wb").write(bytes(data))
        planted = self.manifest(copy)
        self.check("W02", "the wrappers directory's checksum-and-mode manifest is unchanged after every group "
                   "(control: a planted same-length change shows)",
                   before == after and planted != before and len(planted) == len(before),
                   {"changed": sorted(set(before) ^ set(after))[:6]})
        pattern = re.compile(r"open\([^)]*['\"][wax]\+?b?['\"]|write_atomic|os\.(remove|unlink|rename|replace|makedirs|mkdir)\("
                             r"|shutil\.(copy|copy2|copyfile|copytree|move|rmtree)\(")
        src = open(self.U, encoding="utf-8").read() if os.path.isfile(self.U) else None
        hits = [l for l in (src or "").splitlines() if pattern.search(l)]
        control = pattern.search("    open(path, 'w').write(x)") is not None
        self.check("W02", "usage_windows.py holds no file-write call (control: a planted open(..., 'w') line hits)",
                   src is not None and not hits and control, hits[:4] if src is not None else "module absent")

    # ------------------------------------------- A09: the folds of DW-20261021-2 ---------------
    def a09(self):
        """The measured upper-bound rate at the close (critic CR-T2b finding 11) and the order of a
        boundary that line 1's model check ends with exit 11 (finding 13): no reading starts."""
        uw = self.uw
        ro = {"event": "run-open", "usage_reading": {"windows": {
            "claude_week": {"status": "measured", "used_pct": 40, "reset_text": "r", "source": "claude_week"},
            "claude_5h": {"status": "unmeasured", "used_pct": None, "absent": True},
            "gpt_week": {"status": "measured", "used_pct": 20, "reset_text": "g", "source": "p"}}}}
        close = {"windows": {
            "claude_week": {"status": "measured", "used_pct": 47.4, "reset_text": "r", "source": "claude_week"},
            "claude_5h": {"status": "unmeasured", "used_pct": None, "absent": True},
            "gpt_week": {"status": "measured", "used_pct": 20, "reset_text": "g2", "source": "p"}}}
        helpers = [{"lane": "H", "family": "claude", "passes": 1, "complete": True,
                    "quantities": {"usd_list": 10.0}}]
        plan = {"rates": [{"family": "claude", "pp_per_unit": {"claude_week": {"usd_list": {"low": 0.5, "high": 0.6}}}}]}
        rates = uw.measured_rates([ro], plan, close, helpers) if uw else {}
        week = rates.get("claude_week") or {}
        self.check("A09", "a run with 10 units and a Claude-week change of 7.4 points records the measured "
                   "upper-bound rate 0.74 per unit beside the assumed 0.5-0.6",
                   week.get("status") == "measured" and week.get("pp_per_unit", {}).get("usd_list") == 0.74
                   and week.get("pp_per_helper") == 7.4
                   and week.get("assumed_pp_per_unit") == {"usd_list": {"low": 0.5, "high": 0.6}}, rates)
        self.check("A09", "control: a window whose reset moved during the run, or one never measured, reads "
                   "unknown with its reason, never a rate",
                   (rates.get("gpt_week") or {}).get("status") == "unknown"
                   and "reset moved" in str((rates.get("gpt_week") or {}).get("reason"))
                   and (rates.get("claude_5h") or {}).get("status") == "unknown", rates)
        fx = Fx(self, "a09")
        fx.open_run("ra9")
        code = (
            "import importlib.util, json, sys\n"
            "spec = importlib.util.spec_from_file_location('hs', sys.argv[1])\n"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
            "uw = m.import_usage_windows(); starts = []\n"
            "orig = uw.UsageRead.start\n"
            "def start(self):\n    starts.append(1); return orig(self)\n"
            "uw.UsageRead.start = start\n"
            "m.head_model_check = lambda *a, **k: {'verdict': 'confirmed-swap'}\n"
            "rc = json.loads(sys.argv[2])\n"
            "m.model_verdict = lambda *a, **k: (m.EXIT_MODEL if rc else None)\n"
            "sys.argv = ['handsoff.py'] + json.loads(sys.argv[3])\n"
            "try:\n    out = m.main()\nexcept SystemExit as exc:\n    out = exc.code\n"
            "print('RESULT ' + json.dumps({'rc': out, 'starts': len(starts)}))\n")
        argv = ["boundary", "--run", "ra9", "--from", "item1", "--to", "item2", "--disposition", "fixture",
                "--waste", "none", "--next", "fixture next", "--meter-line", METER, "--handoff", fx.handoff("ra9")]
        got = {}
        for label, swap in (("swap", True), ("none", False)):
            p = self.run([sys.executable, "-B", "-c", code, self.H, json.dumps(swap), json.dumps(argv)],
                         fx.env(), 90)
            line = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
            got[label] = json.loads(line[-1][7:]) if line else {"rc": p.returncode, "err": p.stderr[-300:]}
        self.check("A09", "a boundary the model check ends with exit 11 starts no usage reading (the stand-in "
                   "count 0); control: the same boundary with no swap starts one",
                   got["swap"].get("rc") == 11 and got["swap"].get("starts") == 0
                   and got["none"].get("starts") == 1, got)

    def run_all(self):
        before = self.manifest(self.W) if self.selected("W02") else None
        for gid in GROUPS[:-1]:
            if self.selected(gid):
                print("--- %s" % gid, flush=True)
                try:
                    getattr(self, gid.lower())()
                except B.Probe:
                    raise
                except Exception as exc:   # a crash inside a group is that group's failure, named
                    self.check(gid, "group ran to its end", False, "%s: %s" % (type(exc).__name__, exc))
        if self.selected("W02"):
            print("--- W02", flush=True)
            self.w02(before)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wrappers", default=HERE)
    ap.add_argument("--only", action="append", choices=GROUPS)
    ap.add_argument("--fixture-root", default=None)
    ap.add_argument("--vault", default=None, help="the vault whose CLAUDE.md lane.py's dry spawn reads "
                    "(read only; default CLAUDE_PROJECT_DIR, else three levels above --wrappers)")
    args = ap.parse_args()
    try:
        suite = Suite(args)
    except B.Probe as exc:
        print("PROBE FAILED: %s" % exc)
        return 2
    try:
        suite.run_all()
    except B.Probe as exc:
        print("PROBE FAILED: %s" % exc)
        return 2
    finally:
        shutil.rmtree(suite.root, ignore_errors=True)
    total = suite.passed + suite.failed
    print("FAIL %d/%d" % (suite.failed, total) if suite.failed else "PASS %d/%d" % (total, total))
    return 1 if suite.failed else 0


if __name__ == "__main__":
    sys.exit(main())
