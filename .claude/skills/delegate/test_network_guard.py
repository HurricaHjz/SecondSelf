#!/usr/bin/env python3
"""test_network_guard.py — the suite for the host guard (DW-20261024-2): a helper reaches only the
web addresses its brief names, as far as each launcher can hold it, and the record says where it
cannot.

  python3 test_network_guard.py [--wrappers DIR] [--fixture-root DIR] [--part all|codex|lane]
                                [--capture-probe FILE] [--only LEG]...

Each leg runs in one part only: test_codex_lane.sh runs `codex` and test_lane.sh `lane` (the
Claude launcher's legs, named as test_item_bars.py names its parts); a bare run takes both. Every fixture is test_a3.py's (a fixture vault, routing table and lane home, its
stub provider standing in for `claude` and `codex`), under one removed mktemp folder, so no model,
account reader or network is reached: the stub provider records the environment each lane was
given, and where a leg asks, runs a copy of the capture tool (capture_probe.py, read only, copied
into the fixture) inside the lane against a stand-in `curl` that logs its call and fetches nothing.
Every leg runs with LLM_WIKI_LANE_NETWORK=planted.test in the calling environment, so no leg can
pass by the variable's absence alone.

The guard's mode is one constant, lane.py's NETWORK_GUARD_MODE ("trial" as shipped; plan decision
D6). Production code carries no test hook, so the enforce legs run on a copy of the wrappers whose
constant reads "enforce"; a tree without the constant (the base) gets an unchanged copy, and its
legs report BAD rather than stopping the suite. Each rule carries a planted case that must fire, a
case that must not, and the cannot-decide case. N20 (the owner's choice (a) of 9 November 2026)
proves the fence's limit is stated in plain words, printed and recorded, at every Codex spawn,
resume and beat with shell network, and never without it; N21 adds a worker started directly, and
N22 a resume with an unrelated --config extra, which keeps its shell network and hosts (review
V-T8-G2, 10 November 2026). The last leg of each part proves the suite wrote
nothing beside the scripts: a checksum-and-mode manifest of the wrappers folder before and after,
with no __pycache__, its control one changed byte in a copy in the same copied folder under the
same permissions, which the same comparison must catch.

Lines read `OK <leg>` or `BAD <leg> — [why]`, and the last line is `PASS n/n` or `FAIL k/n`. Exit 0
every leg passed, 1 a leg failed, 2 PROBE FAILED: a premise of the suite broke. The process
bounds (120 s for a launcher or capture run, 60 s for a direct call) are ceilings set by
judgement, unmeasured; the whole suite took about 80 s on this Mac.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_a3 import Fixture, PROVIDER, events_for, rows  # noqa: E402

PLANTED = "planted.test"
GRANTED = "example.org"
OTHER = "other.test"
MODE_LINE = re.compile(r'^NETWORK_GUARD_MODE = "(?P<mode>[^"]*)"$', re.M)
# The design's own texts (DW-20261024-2, EFFECT), as the record must carry them.
COOPERATIVE = ("cooperative: the Codex sandbox opens every host; only tools that read "
               "LLM_WIKI_LANE_NETWORK refuse an unnamed one")
UNBOUND_BASH = ("the fence holds only the network commands it names and inline transport imports; "
                "programs it lets run (npm, npx, pip, git, renderers, installers, script files) are "
                "not bound to hosts")
SEARCH_CLAUDE = "server-side, not bound to named hosts"
SEARCH_CODEX = "server-side (web_search = live), not bound to named hosts"
CAPTURE_REFUSAL = ("the lane's network grant (LLM_WIKI_LANE_NETWORK) does not name other.test; "
                   "nothing was fetched")
# The fence's limit in plain words (the owner's choice (a) of 9 November 2026, his walk-through's
# Part 4, item 48), as codex-lane.py prints it and records it as network_limit.
LIMIT = ("the network fence on this helper is one only cooperating tools respect: the helper's own "
         "commands can still reach any address")

# Prepended to test_a3.py's stub provider: one line per start, recording what the lane's
# environment held, and, where captures.json names URLs, the capture tool run inside the lane with
# that environment (its write grant set to the fixture, as a lane's tool would see one).
PRELUDE = r'''
import json as _json, os as _os, subprocess as _sp, sys as _sys
if "--version" not in _sys.argv:
    _root = _os.environ["A3_FIXTURE"]
    _seen = {"lane": _os.environ.get("LLM_WIKI_LANE_ID"), "family": _os.environ.get("A3_FAMILY"),
             "has": "LLM_WIKI_LANE_NETWORK" in _os.environ,
             "value": _os.environ.get("LLM_WIKI_LANE_NETWORK"),
             "seen_var": "CODEX_LANE_NETWORK_SEEN" in _os.environ,
             "stated_var": "CODEX_LANE_LIMIT_STATED" in _os.environ, "captures": []}
    _caps = _os.path.join(_root, "captures.json")
    if _os.path.exists(_caps):
        for _i, _url in enumerate(_json.load(open(_caps))):
            _work = _os.path.join(_root, "cap-%s-%d" % (_seen["lane"], _i))
            _p = _sp.run([_sys.executable, "-B", _os.path.join(_root, "capture_probe.py"), "capture",
                          _url, "--work", _work, "--curl", _os.path.join(_root, "bin", "curl-stub")],
                         env=dict(_os.environ, LLM_WIKI_LANE_WRITES=_root), capture_output=True,
                         text=True, timeout=120)
            _seen["captures"].append({"url": _url, "rc": _p.returncode, "out": _p.stdout[-700:],
                                      "err": _p.stderr[-300:]})
    with open(_os.path.join(_root, "childenv.jsonl"), "a") as _h:
        _h.write(_json.dumps(_seen) + "\n")
'''

CURL_STUB = r'''
import json, os, sys
with open(os.path.join(os.environ["A3_FIXTURE"], "curl.log"), "a") as h:
    h.write(json.dumps(sys.argv[1:]) + "\n")      # one line per call: the -w format holds newlines
sys.exit(7)
'''


def curl_urls(f):
    """The URL of each stand-in curl call, in order (the last argument of each)."""
    path = f.root / "curl.log"
    out = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                argv = json.loads(line)
            except ValueError:
                continue
            out.append(argv[-1] if argv else None)
    return out


def guard_lines(text, words):
    """The stderr lines of this guard's trial refusals naming `words` (the GPT start check's trial
    line shares the prefix, so a bare count of the prefix would count it too)."""
    return [line for line in text.splitlines() if "would refuse (trial state)" in line and words in line]

# Direct calls into the wrappers of one tree, in a fresh process under the fixture's environment:
# the refusals these legs test are raised before any process starts (design, MERGE TARGET).
DRIVER = r'''
import argparse, contextlib, importlib.util, io, json, os, sys
sys.dont_write_bytecode = True
tree, call, payload = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
sys.path.insert(0, tree)
def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(tree, file))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
err, out = io.StringIO(), {}
try:
    with contextlib.redirect_stderr(err):
        if call == "parse":
            lane = load("lane", "lane.py")
            out["declared"] = lane.parse_declarations(payload["brief"], payload.get("vault"))
        elif call == "decide":
            codex = load("codex_lane_under_test", "codex-lane.py")
            args = argparse.Namespace(run="fixture", network=payload.get("flag", False),
                                      config=payload.get("config"))
            declared = codex.lane.parse_declarations(payload["brief"])
            fields, export = codex.network_decision(args, declared, payload["open"], payload["src"],
                                                    payload["rows"], opened=payload.get("opened"))
            out["fields"], out["export"] = fields, export
        elif call == "shell":
            codex = load("codex_lane_under_test", "codex-lane.py")
            args = argparse.Namespace(network=payload.get("flag", False), config=payload.get("config"))
            out["shell"] = list(codex.shell_network(args, ["%s" % pair for pair in payload["pairs"]]))
        elif call == "policy":
            lane = load("lane", "lane.py")
            policy = lane.run_network_policy("fixture", payload["rows"])
            policy.pop("host_re", None)
            out["policy"] = policy
        elif call == "items":
            lane = load("lane", "lane.py")
            policy = lane.run_network_policy("fixture", [])
            declared = lane.parse_declarations(payload["brief"])
            out["items"] = list(lane.network_host_items(declared, policy["host_re"], policy["unread"]))
except SystemExit as exc:
    out["exit"] = exc.code
except Exception as exc:
    out["crash"] = "%s: %s" % (type(exc).__name__, exc)
out["stderr"] = err.getvalue()
print(json.dumps(out, default=str))
'''


def stamp(offset=0):
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() + offset))


def manifest(root):
    """{relative path: (sha256, mode)} of every file under root, and whether a __pycache__ exists."""
    files, pycache = {}, False
    for path in sorted(Path(root).rglob("*")):
        if "__pycache__" in path.parts:
            pycache = True
            continue
        if path.is_file():
            files[str(path.relative_to(root))] = (hashlib.sha256(path.read_bytes()).hexdigest(),
                                                  oct(stat.S_IMODE(path.stat().st_mode)))
    return files, pycache


def opened_row(f):
    return {"ts": stamp(-60), "run": "fixture", "event": "run-open", "session": "sid-fixture",
            "head": "fixture head", "regime": "single", "regime_src": "owner", "handoff": str(f.ho),
            "detail": "fixture", "pid_src": "none", "session_kind": "head"}


class Suite:
    def __init__(self, args):
        self.args = args
        self.wrappers = Path(args.wrappers).resolve()
        for name in ("lane.py", "codex-lane.py", "handsoff.py"):
            if not (self.wrappers / name).is_file():
                raise SystemExit("PROBE FAILED: no %s under --wrappers %s" % (name, self.wrappers))
        base = Path(args.fixture_root or os.environ.get("TMPDIR") or "/tmp").resolve()
        if not base.is_dir():
            raise SystemExit("PROBE FAILED: the fixture root %s is not a directory" % base)
        self.root = Path(tempfile.mkdtemp(prefix="network-guard.", dir=str(base)))
        self.capture = Path(args.capture_probe).resolve() if args.capture_probe else \
            (self.wrappers.parent / "gather" / "capture_probe.py")
        if args.part in ("all", "codex") and not self.capture.is_file():
            shutil.rmtree(self.root, ignore_errors=True)
            raise SystemExit("PROBE FAILED: no capture tool at %s (pass --capture-probe)" % self.capture)
        self.passed = self.failed = 0
        self.trees = {}
        self.before = manifest(self.wrappers)

    # ------------------------------------------------------------------ plumbing
    def check(self, name, good, why=""):
        if self.args.only and not any(o in name for o in self.args.only):
            return
        if good:
            self.passed += 1
            print("OK %s" % name, flush=True)
        else:
            self.failed += 1
            # The reason after " — ", where B-T2's leg-name comparator cuts a failure's reason.
            print("BAD %s — [%s]" % (name, str(why)[:600].replace("\n", " ")), flush=True)

    def tree(self, mode):
        """The wrappers as shipped for "shipped"; otherwise a copy whose constant reads `mode`
        (or, for "fault", whose handsoff.py raises on import). A tree without the constant is
        copied unchanged, so its legs fail where the line is absent."""
        if mode == "shipped":
            return self.wrappers
        if mode in self.trees:
            return self.trees[mode]
        dest = self.root / ("tree-" + mode)
        shutil.copytree(self.wrappers, dest, ignore=shutil.ignore_patterns("__pycache__"))
        if mode == "fault":
            (dest / "handsoff.py").write_text('raise RuntimeError("planted import fault")\n')
        else:
            path = dest / "lane.py"
            text = path.read_text(encoding="utf-8")
            if len(MODE_LINE.findall(text)) > 1:
                raise SystemExit("PROBE FAILED: lane.py assigns NETWORK_GUARD_MODE more than once")
            path.write_text(MODE_LINE.sub('NETWORK_GUARD_MODE = "%s"' % mode, text), encoding="utf-8")
        self.trees[mode] = dest
        return dest

    def fixture(self, tree, hands_off=True, network=(GRANTED,), grants="json", capture=False):
        f = Fixture(tree, self.root)
        for key in list(f.env):
            if key.startswith(("LLM_WIKI_LANE", "AIMYTH_HANDSOFF", "LLM_WIKI_FENCE")) \
                    and key != "LLM_WIKI_LANE_HOME":
                f.env.pop(key)
        unread = f.root / "bin" / "usage-unread"
        unread.write_text("#!/bin/sh\necho 'stand-in: no account in this suite' >&2\nexit 1\n")
        unread.chmod(0o755)
        f.env.update(LLM_WIKI_LANE_NETWORK=PLANTED, USAGE_CLAUDE_BIN=str(unread),
                     USAGE_CODEX_BIN=str(unread), AIMYTH_STATE_DIR=str(f.root / "state"))
        for name in ("claude", "codex"):
            (f.root / "bin" / name).write_text("#!" + sys.executable + "\n" + PRELUDE + PROVIDER)
        curl = f.root / "bin" / "curl-stub"
        curl.write_text("#!" + sys.executable + "\n" + CURL_STUB)
        curl.chmod(0o755)
        if capture:
            shutil.copy2(self.capture, f.root / "capture_probe.py")
        # A second class whose definition allows WebSearch (N09's Claude lane holding it).
        (f.root / "vault/.claude/agents/fixture-search.md").write_text(
            "---\nname: fixture-search\ndescription: fixture\ntools: Read, Bash, WebSearch\n---\nFixture role.\n")
        route = json.loads(f.routing.read_text())
        route["classes"]["fixture-search"] = dict(route["classes"]["fixture"])
        f.routing.write_text(json.dumps(route))
        f.ho = f.root / "handoff.md"
        f.ho.write_text("# Hand-off\n\n## In flight\n- pack written: 2026-01-01T00:00:00+0000\n- Next: one\n"
                        "- Needs: nothing\n- Decided: nothing\n\n## Trace\n\n## Findings ledger\n")
        if hands_off:
            f.record.write_text(json.dumps(opened_row(f)) + "\n")
            path = f.store / "spawn-records" / "fixture-grants.json"
            if grants == "json":
                path.write_text(json.dumps({"run": "fixture", "grants": [], "writes": [],
                                            "on_limit": "stop", "viewer": "none",
                                            "network": list(network)}))
            elif grants == "garbage":
                path.write_text("not json {\n")
            elif grants == "mode-key":
                path.write_text(json.dumps({"run": "fixture", "grants": [], "writes": [],
                                            "network": list(network), "network_guard": "enforce"}))
        return f

    def brief(self, f, name, *lines):
        path = f.root / name
        path.write_text("Reply with the single word OK.\n" + "".join(line + "\n" for line in lines))
        return path

    def start(self, f, family, lane, brief=None, extra=(), verb="spawn", cls=None):
        f.scenario(family, events_for(family, "clean"))
        more = []
        if verb != "spawn":
            more = (["--brief", str(brief)] if brief else []) + \
                (["--home", str(f.root / "lane-home"), "--projects-root", str(f.root / "projects")]
                 if family == "claude" else [])
        command = f.command(family, verb, more + list(extra))
        command[command.index("--lane") + 1] = lane
        if verb == "spawn" and brief:
            command[command.index("--brief") + 1] = str(brief)
        if cls:
            command[command.index("--class") + 1] = cls
        return f.run(command, timeout=120)

    def codex_net(self, f):
        return ["--write", str(f.root / "work"), "--network"]

    @staticmethod
    def seen(f, lane):
        path = f.root / "childenv.jsonl"
        out = []
        if path.exists():
            for line in path.read_text().splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("lane") == lane:
                    out.append(row)
        return out

    @staticmethod
    def event(f, lane, kind, last=True):
        found = [r for r in rows(f.record) if r.get("event") == kind and r.get("lane") == lane]
        return (found[-1] if last else found[0]) if found else {}

    @staticmethod
    def store_files(f):
        return sorted(str(p.relative_to(f.store)) for p in f.store.rglob("*") if p.is_file())

    def nothing_written(self, f, lane, before_bytes, before_files, result):
        """Exit 2, the record byte-identical, no lane line, the stand-in never started, and no new
        file in the store but the lane's empty A3 gate lock (a foreground start takes it before its
        checks; checkpoint 2-r3's finding, so the claim is never 'nothing at all')."""
        after = f.record.read_bytes() if f.record.exists() else b""
        new = sorted(set(self.store_files(f)) - set(before_files))
        others = [p for p in new if not p.endswith(".lock")]
        return (result.returncode == 2 and after == before_bytes and not self.seen(f, lane)
                and not others), {"rc": result.returncode, "new": new, "stderr": result.stderr[-400:]}

    def driver(self, tree, call, payload, env):
        proc = subprocess.run([sys.executable, "-B", "-c", DRIVER, str(tree), call, json.dumps(payload)],
                              env=env, capture_output=True, text=True, timeout=60)
        try:
            return json.loads(proc.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"crash": (proc.stdout + proc.stderr)[-600:]}

    # ------------------------------------------------------------------ premises
    def n00(self):
        text = (self.wrappers / "lane.py").read_text(encoding="utf-8")
        found = MODE_LINE.findall(text)
        enforce = MODE_LINE.findall((self.tree("enforce") / "lane.py").read_text(encoding="utf-8"))
        self.check("N00 the guard's one constant ships trial: NETWORK_GUARD_MODE assigned once in "
                   "lane.py, \"trial\" (control: the enforce copy reads \"enforce\" once)",
                   found == ["trial"] and enforce == ["enforce"], {"shipped": found, "copy": enforce})
        codex = (self.wrappers / "codex-lane.py").read_text(encoding="utf-8")
        own = re.findall(r'^NETWORK_GUARD_MODE\b', codex, re.M)
        self.check("N00b codex-lane.py holds no mode of its own: it reads lane.py's (0 assignments; "
                   "control: lane.network_guard_mode is called through network_guard_apply)",
                   not own and "lane.network_guard_apply(" in codex, {"own": own})

    # ------------------------------------------------------------------ the Codex part
    def part_codex(self):
        self.n00()
        for mode in ("shipped", "enforce"):
            self.codex_export(mode)
        self.direct_rules()
        self.codex_resume()
        self.codex_config()
        self.codex_grants_unread()
        self.codex_mode_constant()
        self.codex_detach_and_search()
        self.codex_limit_line()
        self.codex_review_t8()
        self.last_leg("codex")

    def codex_review_t8(self):
        """N21 and N22, the review V-T8-G2's line-3 faults (10 November 2026), in both modes.
        N21 (its point 2): a worker started directly with shell network has no caller to print the
        limit line, so it prints the line itself; a worker whose detaching caller printed it (handed
        CODEX_LANE_LIMIT_STATED=1) prints none, and the lane never sees that variable. N22 (fold F5
        of review V-T2c): a resume that brings an unrelated --config extra keeps the shell network a
        lane-open's --config extra opened, and its hosts; the resume with no extra is the control."""
        line_of = lambda lane: "codex-lane.py: lane fixture/%s has shell network: %s." % (lane, LIMIT)
        for mode in ("shipped", "enforce"):
            tag = "trial" if mode == "shipped" else "enforce"
            f = self.fixture(self.tree(mode))
            try:
                b = self.brief(f, "hosts.md", "HOST+: %s" % GRANTED)
                r = self.start(f, "codex", "W1", b, self.codex_net(f) + ["--as-worker"])
                opened = self.event(f, "W1", "lane-open")
                self.check("N21a.%s must appear: a worker started directly (spawn --network --as-worker, no "
                           "detaching caller) prints the plain limit line once and its lane-open carries "
                           "network_limit (review V-T8-G2 point 2)" % tag,
                           r.returncode == 0 and r.stderr.count(LIMIT) == 1 and line_of("W1") in r.stderr
                           and opened.get("network") is True and opened.get("network_limit") == LIMIT,
                           {"rc": r.returncode, "count": r.stderr.count(LIMIT),
                            "field": opened.get("network_limit"), "stderr": r.stderr[-400:]})
                f.env["CODEX_LANE_LIMIT_STATED"] = "1"
                try:
                    r = self.start(f, "codex", "W2", b, self.codex_net(f) + ["--as-worker"])
                finally:
                    f.env.pop("CODEX_LANE_LIMIT_STATED", None)
                opened = self.event(f, "W2", "lane-open")
                seen = self.seen(f, "W2")
                self.check("N21b.%s printed once, not twice: a worker handed CODEX_LANE_LIMIT_STATED=1 (its "
                           "detaching caller printed the line) prints none, still records network_limit, and "
                           "the lane never sees the variable (control: N21a's line on the same fixture)" % tag,
                           r.returncode == 0 and r.stderr.count(LIMIT) == 0
                           and opened.get("network_limit") == LIMIT and seen and seen[-1]["has"]
                           and seen[-1].get("stated_var") is False,
                           {"rc": r.returncode, "count": r.stderr.count(LIMIT), "seen": seen[-1:],
                            "field": opened.get("network_limit")})
                pb = self.brief(f, "plain.md")
                r = self.start(f, "codex", "W3", pb, ["--write", str(f.root / "work"), "--as-worker"])
                opened = self.event(f, "W3", "lane-open")
                self.check("N21c.%s must not appear: a worker started directly without shell network prints no "
                           "limit line and records no network_limit" % tag,
                           r.returncode == 0 and LIMIT not in r.stderr and "network_limit" not in opened
                           and opened.get("network") is False,
                           {"rc": r.returncode, "stderr": r.stderr[-300:]})
                follow = self.brief(f, "follow.md", "Continue.")
                r = self.start(f, "codex", "F5", b, ["--write", str(f.root / "work"), "--config",
                                                     "sandbox_workspace_write.network_access=true"])
                spawned = r.returncode == 0 and self.event(f, "F5", "lane-open").get("network") is True
                results = {}
                for case, extra in (("control", []), ("unrelated", ["--config", 'model_verbosity="low"'])):
                    r = self.start(f, "codex", "F5", follow, extra, verb="resume")
                    row = self.event(f, "F5", "lane-resumed")
                    child = self.seen(f, "F5")
                    results[case] = {"rc": r.returncode, "network": row.get("network"),
                                     "hosts": row.get("network_hosts"), "src": row.get("network_src"),
                                     "limit": r.stderr.count(LIMIT), "field": row.get("network_limit"),
                                     "child": child[-1]["value"] if child else None}
                kept = lambda v: (v["rc"] == 0 and v["network"] is True and v["hosts"] == [GRANTED]
                                  and v["limit"] == 1 and v["field"] == LIMIT and v["child"] == GRANTED)
                self.check("N22.%s keep it: a lane whose shell network a --config extra opened, resumed with an "
                           "unrelated --config extra (model_verbosity=\"low\"), keeps its shell network and its "
                           "host (lane-resumed network true, network_hosts [example.org], the lane's variable "
                           "example.org, the limit line printed and recorded) (fold F5 of review V-T2c; "
                           "control: the resume with no extra does the same)" % tag,
                           spawned and kept(results["control"]) and kept(results["unrelated"]), results)
            finally:
                f.cleanup()

    def codex_limit_line(self):
        """N20 (the owner's choice (a) of 9 November 2026, item 48): at every Codex spawn, resume or
        beat with shell network, one plain line states the fence's limit and the call's record line
        carries the same words as network_limit; a call without shell network carries neither. In
        both modes, since the statement never depends on the mode."""
        line_of = lambda lane: "codex-lane.py: lane fixture/%s has shell network: %s." % (lane, LIMIT)
        for mode in ("shipped", "enforce"):
            tag = "trial" if mode == "shipped" else "enforce"
            f = self.fixture(self.tree(mode))
            try:
                b = self.brief(f, "hosts.md", "HOST+: %s" % GRANTED)
                follow = self.brief(f, "follow.md", "Continue.")
                r = self.start(f, "codex", "M1", b, self.codex_net(f))
                opened = self.event(f, "M1", "lane-open")
                self.check("N20a.%s must appear: a Codex spawn with --network prints the plain limit line once "
                           "(the fence is one only cooperating tools respect; the helper's own commands can "
                           "still reach any address) and its lane-open carries the same words as "
                           "network_limit" % tag,
                           r.returncode == 0 and r.stderr.count(LIMIT) == 1 and line_of("M1") in r.stderr
                           and opened.get("network_limit") == LIMIT,
                           {"rc": r.returncode, "count": r.stderr.count(LIMIT), "field": opened.get("network_limit"),
                            "stderr": r.stderr[-400:]})
                r = self.start(f, "codex", "M1", follow, verb="resume")
                resumed = self.event(f, "M1", "lane-resumed")
                self.check("N20b.%s must appear: a resume carrying the lane's shell network prints the line once "
                           "and its lane-resumed carries network_limit" % tag,
                           r.returncode == 0 and r.stderr.count(LIMIT) == 1 and line_of("M1") in r.stderr
                           and resumed.get("network") is True and resumed.get("network_limit") == LIMIT,
                           {"rc": r.returncode, "count": r.stderr.count(LIMIT),
                            "field": resumed.get("network_limit"), "stderr": r.stderr[-400:]})
                r = self.start(f, "codex", "M1", None, ["--beat"], verb="resume")
                beat = self.event(f, "M1", "hold-beat")
                self.check("N20c.%s must appear: the supervisor's beat of that lane (its shell network carried) "
                           "prints the line once and its hold-beat carries network_limit" % tag,
                           r.returncode == 0 and r.stderr.count(LIMIT) == 1 and beat.get("ok") is True
                           and beat.get("network_limit") == LIMIT,
                           {"rc": r.returncode, "count": r.stderr.count(LIMIT), "field": beat.get("network_limit"),
                            "stderr": r.stderr[-400:]})
                pb = self.brief(f, "plain.md")
                r = self.start(f, "codex", "M2", pb, ["--write", str(f.root / "work")])
                opened = self.event(f, "M2", "lane-open")
                spawn_ok = r.returncode == 0 and LIMIT not in r.stderr and "network_limit" not in opened \
                    and opened.get("network") is False
                r = self.start(f, "codex", "M2", follow, verb="resume")
                resumed = self.event(f, "M2", "lane-resumed")
                resume_ok = r.returncode == 0 and LIMIT not in r.stderr and "network_limit" not in resumed
                r = self.start(f, "codex", "M2", None, ["--beat"], verb="resume")
                beat = self.event(f, "M2", "hold-beat")
                beat_ok = r.returncode == 0 and LIMIT not in r.stderr and beat.get("ok") is True \
                    and "network_limit" not in beat
                self.check("N20d.%s must not appear: a Codex lane without shell network (--write alone) prints no "
                           "limit line and carries no network_limit at its spawn, its resume or its beat "
                           "(control: N20a's line on the same fixture)" % tag,
                           spawn_ok and resume_ok and beat_ok,
                           {"spawn": spawn_ok, "resume": resume_ok, "beat": beat_ok, "stderr": r.stderr[-300:]})
            finally:
                f.cleanup()
        f = self.fixture(self.wrappers)
        try:
            b = self.brief(f, "hosts.md", "HOST+: %s" % GRANTED)
            r = self.start(f, "codex", "M3", b, ["--write", str(f.root / "work"), "--config",
                                                 "sandbox_workspace_write.network_access=true"])
            opened = self.event(f, "M3", "lane-open")
            self.check("N20e must appear: shell network opened by a --config extra (no --network flag) prints the "
                       "line once and records network_limit",
                       r.returncode == 0 and r.stderr.count(LIMIT) == 1 and opened.get("network") is True
                       and opened.get("network_limit") == LIMIT,
                       {"rc": r.returncode, "count": r.stderr.count(LIMIT), "field": opened.get("network_limit"),
                        "stderr": r.stderr[-300:]})
            r = self.start(f, "codex", "M4", b, self.codex_net(f) + ["--detach"])
            logs = sorted(f.store.rglob("*detach*M4*"))
            log = logs[0].read_text() if logs else ""
            deadline = time.time() + 60
            while time.time() < deadline and not self.event(f, "M4", "lane-open"):
                time.sleep(0.2)
            opened = self.event(f, "M4", "lane-open")
            self.check("N20f must appear once: a detached Codex --network spawn prints the line once, in the "
                       "caller's stderr and none in the worker's detach log, and the worker's lane-open carries "
                       "network_limit",
                       r.returncode == 0 and r.stderr.count(LIMIT) == 1 and logs and log.count(LIMIT) == 0
                       and opened.get("network_limit") == LIMIT,
                       {"rc": r.returncode, "caller": r.stderr.count(LIMIT), "log": log.count(LIMIT),
                        "field": opened.get("network_limit"), "logs": [p.name for p in logs]})
        finally:
            f.cleanup()

    def codex_export(self, mode):
        tag = "trial" if mode == "shipped" else "enforce"
        f = self.fixture(self.tree(mode), capture=(mode == "shipped"))
        try:
            if mode == "shipped":
                (f.root / "captures.json").write_text(json.dumps(
                    ["https://%s/x" % GRANTED, "https://%s/x" % OTHER]))
            b = self.brief(f, "hosts.md", "HOST+: %s" % GRANTED)
            r = self.start(f, "codex", "N01", b, self.codex_net(f))
            env = self.seen(f, "N01")
            opened = self.event(f, "N01", "lane-open")
            coop = r.stderr.count(COOPERATIVE)
            self.check("N01.%s must not fire, the export: Codex --network, brief HOST+: example.org, run "
                       "grant [example.org]: the lane's environment holds LLM_WIKI_LANE_NETWORK=example.org "
                       "(not the inherited planted.test); lane-open network true from --network, "
                       "network_hosts [example.org], network_enforcement cooperative, nothing would refuse; "
                       "the cooperative line printed once" % tag,
                       r.returncode == 0 and len(env) == 1 and env[0]["value"] == GRANTED
                       and opened.get("network") is True and opened.get("network_src") == "--network"
                       and opened.get("network_hosts") == [GRANTED]
                       and opened.get("network_enforcement") == COOPERATIVE
                       and (opened.get("network_guard") or {}).get("would_refuse") == []
                       and (opened.get("network_guard") or {}).get("mode") == tag and coop == 1,
                       {"rc": r.returncode, "env": env, "open": {k: opened.get(k) for k in (
                           "network", "network_src", "network_hosts", "network_enforcement", "network_guard")},
                        "coop": coop, "stderr": r.stderr[-300:]})
            self.check("N12iv.%s inherited grant, Codex --network with HOST+: the lane carries exactly "
                       "example.org, and the lane-open records network_inherited_dropped planted.test" % tag,
                       len(env) == 1 and env[0]["has"] and env[0]["value"] == GRANTED
                       and opened.get("network_inherited_dropped") == PLANTED,
                       {"env": env, "dropped": opened.get("network_inherited_dropped")})
            if mode == "shipped":
                caps = (env[0].get("captures") if env else None) or []
                curl = curl_urls(f)
                first = caps[0] if caps else {}
                second = caps[1] if len(caps) > 1 else {}
                self.check("N02a each way, a granted host fetches: inside the lane the capture tool on "
                           "https://example.org/x passes its start check and calls the stand-in curl once "
                           "(it then fails at its fetch stage, the stand-in fetching nothing)",
                           len(caps) == 2 and "PROBE FAILED: start" not in first.get("out", "")
                           and curl == ["https://%s/x" % GRANTED]
                           and "PROBE FAILED: fetch" in first.get("out", ""),
                           {"first": first, "curl": curl})
                self.check("N02b each way, an ungranted host is refused: the capture tool on "
                           "https://other.test/x fails at its start stage with the grant's own words "
                           "and the stand-in curl's log gains no call",
                           CAPTURE_REFUSAL in second.get("out", "") and second.get("rc") not in (0, None)
                           and "PROBE FAILED: start" in second.get("out", "")
                           and curl == ["https://%s/x" % GRANTED],
                           {"second": second, "curl": curl})
                (f.root / "captures.json").unlink()
            # N03: shell network, no hosts (rule 1).
            nb = self.brief(f, "nohosts.md")
            before, files = f.record.read_bytes(), self.store_files(f)
            r = self.start(f, "codex", "N03", nb, self.codex_net(f))
            if tag == "enforce":
                ok, why = self.nothing_written(f, "N03", before, files, r)
                self.check("N03.enforce must fire, rule 1: Codex --network, no HOST+, run grant "
                           "[example.org]: exit 2 naming the rule, the record byte-identical, no lane "
                           "line, the stand-in never started, no new store file but the A3 gate lock",
                           ok and "names no hosts" in r.stderr, why)
            else:
                env = self.seen(f, "N03")
                opened = self.event(f, "N03", "lane-open")
                would = (opened.get("network_guard") or {}).get("would_refuse") or []
                self.check("N03.trial rule 1 logged: the spawn proceeds, the lane carries the run "
                           "grant's hosts (example.org, the 2026-10-25 08:20 fix shape), "
                           "network_guard.would_refuse names the rule, one would-refuse line on stderr",
                           r.returncode == 0 and len(env) == 1 and env[0]["value"] == GRANTED
                           and len(would) == 1 and "names no hosts" in would[0]
                           and len(guard_lines(r.stderr, "names no hosts")) == 1,
                           {"rc": r.returncode, "env": env, "would": would, "stderr": r.stderr[-400:]})
            # N04 launcher leg (ii): a granted and an ungranted host.
            mb = self.brief(f, "mixed.md", "HOST+: %s, %s" % (GRANTED, OTHER))
            before, files = f.record.read_bytes(), self.store_files(f)
            r = self.start(f, "codex", "N04", mb, self.codex_net(f))
            env = self.seen(f, "N04")
            if tag == "enforce":
                ok, why = self.nothing_written(f, "N04", before, files, r)
                self.check("N04.enforce must fire, rule 4 through the launcher: HOST+: example.org, "
                           "other.test against [example.org]: exit 2 naming other.test and the grant, "
                           "nothing written", ok and OTHER in r.stderr and "network grant" in r.stderr, why)
            else:
                opened = self.event(f, "N04", "lane-open")
                self.check("N04.trial rule 4 logged through the launcher: the lane carries example.org "
                           "alone (never other.test), and the lane-open's network_hosts says the same",
                           r.returncode == 0 and len(env) == 1 and env[0]["value"] == GRANTED
                           and opened.get("network_hosts") == [GRANTED],
                           {"rc": r.returncode, "env": env, "hosts": opened.get("network_hosts")})
            # N05: hosts, no shell network (rule 2).
            hb = self.brief(f, "hosts-nonet.md", "HOST+: %s" % GRANTED)
            before, files = f.record.read_bytes(), self.store_files(f)
            r = self.start(f, "codex", "N05", hb, ["--write", str(f.root / "work")])
            if tag == "enforce":
                ok, why = self.nothing_written(f, "N05", before, files, r)
                self.check("N05.enforce must fire, rule 2: HOST+: example.org with no shell network: "
                           "exit 2, nothing written", ok and "grants no shell network" in r.stderr, why)
            else:
                env = self.seen(f, "N05")
                opened = self.event(f, "N05", "lane-open")
                would = (opened.get("network_guard") or {}).get("would_refuse") or []
                self.check("N05.trial rule 2 logged: the spawn proceeds, the variable unset (no shell "
                           "network, so no export), the rule on the lane-open",
                           r.returncode == 0 and len(env) == 1 and not env[0]["has"]
                           and opened.get("network") is False and len(would) == 1
                           and "grants no shell network" in would[0],
                           {"rc": r.returncode, "env": env, "would": would})
            # N12iii: a Codex lane without network carries no variable, and nothing fires.
            pb = self.brief(f, "plain.md")
            r = self.start(f, "codex", "N12", pb)
            env = self.seen(f, "N12")
            opened = self.event(f, "N12", "lane-open")
            self.check("N12iii.%s must not fire, inherited grant: a Codex spawn without network and "
                       "without HOST+ runs, carries no LLM_WIKI_LANE_NETWORK, records the dropped "
                       "planted.test and no network_guard" % tag,
                       r.returncode == 0 and len(env) == 1 and not env[0]["has"]
                       and opened.get("network") is False and "network_guard" not in opened
                       and opened.get("network_inherited_dropped") == PLANTED,
                       {"rc": r.returncode, "env": env, "open": {k: opened.get(k) for k in (
                           "network", "network_guard", "network_inherited_dropped")}})
        finally:
            f.cleanup()

    def direct_rules(self):
        """N04, N06, N10: direct calls, each in trial (the shipped tree) and enforce (the copy)."""
        f = self.fixture(self.wrappers)
        try:
            ro = [opened_row(f)]
            for mode in ("shipped", "enforce"):
                tag = "trial" if mode == "shipped" else "enforce"
                tree = self.tree(mode)

                def decide(brief, open_=True, src="--network", rows_=ro, opened=None):
                    return self.driver(tree, "decide", {"brief": brief, "open": open_, "src": src,
                                                        "rows": rows_, "opened": opened}, f.env)
                for case, brief, want, refused in (
                        ("i", "HOST+: %s" % OTHER, [], OTHER),
                        ("ii", "HOST+: %s, %s" % (GRANTED, OTHER), [GRANTED], OTHER),
                        ("iii", "HOST+: sub.%s" % GRANTED, ["sub.%s" % GRANTED], None)):
                    d = decide(brief)
                    if refused and tag == "enforce":
                        good = d.get("exit") == 2 and refused in d.get("stderr", "") \
                            and "network grant (%s" % GRANTED in d.get("stderr", "")
                        what = "refused (exit 2), naming %s and the grant" % refused
                    elif refused:
                        would = ((d.get("fields") or {}).get("network_guard") or {}).get("would_refuse") or []
                        good = d.get("export") == want and len(would) == 1 and refused in would[0]
                        what = "logged naming %s; exported %s" % (refused, want or "nothing")
                    else:
                        good = d.get("export") == want and "exit" not in d and \
                            ((d.get("fields") or {}).get("network_guard") or {}).get("would_refuse") == []
                        what = "admitted, exporting %s (must not fire: a subdomain of a granted host)" % want
                    self.check("N04%s.%s rule 4, run grant [example.org], %s: %s" % (case, tag, brief, what),
                               good, d)
                for item in ("https://example.org", "example.org:443", "*.example.org", "com"):
                    d = decide("HOST+: %s" % item)
                    if tag == "enforce":
                        good = d.get("exit") == 2 and repr(item.lower()) in d.get("stderr", "")
                    else:
                        would = ((d.get("fields") or {}).get("network_guard") or {}).get("would_refuse") or []
                        good = d.get("export") == [] and any(repr(item.lower()) in w for w in would)
                    self.check("N06.%s rule 3, malformed item %s: %s, never exported"
                               % (tag, item, "refused naming it" if tag == "enforce" else "logged naming it"),
                               good, d)
                for label, brief, words, good_items in (
                        ("an empty item", "HOST+: %s, , sub.%s" % (GRANTED, GRANTED), "an empty item",
                         [GRANTED, "sub.%s" % GRANTED]),
                        ("an empty declaration", "HOST+:", "an empty HOST+ declaration", [])):
                    d = decide(brief)
                    if tag == "enforce":
                        good = d.get("exit") == 2 and words in d.get("stderr", "")
                    else:
                        would = ((d.get("fields") or {}).get("network_guard") or {}).get("would_refuse") or []
                        good = any(words in w for w in would) and d.get("export") == good_items
                    self.check("N06.%s rule 3, %s: %s, the good items alone exported"
                               % (tag, label, "refused" if tag == "enforce" else "logged"), good, d)
                d = decide("HOST+: none")
                if tag == "enforce":
                    good = d.get("exit") == 2 and "names no hosts" in d.get("stderr", "") \
                        and "empty set" in d.get("stderr", "")
                else:
                    would = ((d.get("fields") or {}).get("network_guard") or {}).get("would_refuse") or []
                    good = d.get("export") == [] and len(would) == 1 and "empty set" in would[0]
                self.check("N10.%s HOST+: none declares the empty set: with --network rule 1 fires, and "
                           "nothing is exported (never the run grant: the declaration bounds it)" % tag,
                           good, d)
                d = decide("HOST+: %s" % GRANTED, rows_=[])
                self.check("N04p.%s must not fire, a plain lane run (no run-open): the declared host is "
                           "exported, no run grant is read" % tag,
                           d.get("export") == [GRANTED] and "exit" not in d
                           and ((d.get("fields") or {}).get("network_guard") or {}).get("grant") is None, d)
            # The grammar (N10): direct parses on the shipped tree.
            tree = self.wrappers
            cases = (("bare", "HOST+: %s" % GRANTED, 1),
                     ("fenced", "```\nHOST+: %s\n```" % GRANTED, 0),
                     ("block quote", "> HOST+: %s" % GRANTED, 0),
                     ("backticks", "Write `HOST+: %s` to name it." % GRANTED, 0),
                     ("double quotes", 'Write "HOST+: %s" to name it.' % GRANTED, 0),
                     ("after a bullet", "- HOST+: %s" % GRANTED, 1))
            for label, brief, want in cases:
                d = self.driver(tree, "parse", {"brief": brief}, f.env)
                hosts = ((d.get("declared") or {}).get("hosts"))
                self.check("N10 grammar, %s HOST+: %s" % (label, "declares" if want else "declares nothing"),
                           isinstance(hosts, list) and len(hosts) == want, d)
            d = self.driver(tree, "parse", {"brief": "HOST+: %s WEB+: search: one" % GRANTED}, f.env)
            self.check("N10 grammar, HOST+ and an unquoted WEB+ on one line: refused by the existing "
                       "one-declaration rule (exit 2), in both modes as before",
                       d.get("exit") == 2 and "markers stand unquoted on one line" in d.get("stderr", ""), d)
            # N18: the reader when handsoff.py cannot be imported.
            fault = self.tree("fault")
            d = self.driver(fault, "policy", {"rows": ro}, f.env)
            pol = d.get("policy") or {}
            self.check("N18 cannot decide, reader unavailable: beside a handsoff.py that raises on import, "
                       "run_network_policy reads the run grant as none, naming the import error, and the "
                       "mode is still the constant's (trial)",
                       pol.get("grant") == [] and "planted import fault" in str(pol.get("grant_src"))
                       and pol.get("mode") == "trial", d)
            d = self.driver(fault, "items", {"brief": "HOST+: %s" % GRANTED}, f.env)
            items = d.get("items") or [None, None, None]
            self.check("N18b cannot decide, the host rule unavailable: with no HOST_RE every item is "
                       "unjudged, named so, and none is admitted",
                       items[0] == [] and len(items[1] or []) == 1 and "unjudged" in items[1][0]["why"], d)
            # N13's property, direct: the resolved list.
            for label, pairs, want in (
                    ("the network key true", ["sandbox_workspace_write.network_access=true"],
                     [True, "--config sandbox_workspace_write.network_access"]),
                    ("the network key false (must not fire)", ["sandbox_workspace_write.network_access=false"],
                     [False, None]),
                    ("sandbox_mode (cannot decide)", ['sandbox_mode="danger-full-access"'],
                     [True, "cannot decide: --config sandbox_mode may open the sandbox's network"]),
                    ("an unrelated key (must not fire)", ['model_verbosity="low"'], [False, None])):
                d = self.driver(tree, "shell", {"pairs": pairs, "config": pairs}, f.env)
                self.check("N13 shell_network reads %s as %s" % (label, want), d.get("shell") == want, d)
        finally:
            f.cleanup()

    def codex_resume(self):
        for mode in ("shipped", "enforce"):
            tag = "trial" if mode == "shipped" else "enforce"
            f = self.fixture(self.tree(mode))
            try:
                b = self.brief(f, "hosts.md", "HOST+: %s" % GRANTED)
                spawn = self.start(f, "codex", "R1", b, self.codex_net(f))
                follow = self.brief(f, "follow.md", "Continue.")
                r = self.start(f, "codex", "R1", follow, verb="resume")
                env = self.seen(f, "R1")
                resumed = self.event(f, "R1", "lane-resumed")
                self.check("N07a.%s must not fire, a resume with no flag: lane-resumed network true, "
                           "network_src carried from lane-open, the lane carries example.org" % tag,
                           spawn.returncode == 0 and r.returncode == 0 and len(env) == 2
                           and env[1]["value"] == GRANTED and resumed.get("network") is True
                           and resumed.get("network_src") == "carried from lane-open",
                           {"spawn": spawn.returncode, "rc": r.returncode, "env": env,
                            "resumed": {k: resumed.get(k) for k in ("network", "network_src",
                                                                    "network_hosts", "config_match")},
                            "stderr": r.stderr[-300:]})
                r = self.start(f, "codex", "R1", None, ["--beat"], verb="resume")
                env = self.seen(f, "R1")
                beat = self.event(f, "R1", "hold-beat")
                self.check("N07b.%s must not fire, the supervisor's beat (no --network): the "
                           "configuration hash matches the lane-open's and the beat runs carrying "
                           "example.org" % tag,
                           r.returncode == 0 and len(env) == 3 and env[2]["value"] == GRANTED
                           and beat.get("ok") is True,
                           {"rc": r.returncode, "env": env[2:], "beat": {k: beat.get(k) for k in (
                               "ok", "config_match", "config_src")}, "stderr": r.stderr[-400:]})
                wb = self.brief(f, "widen.md", "HOST+: %s" % OTHER)
                before, files = f.record.read_bytes(), self.store_files(f)
                r = self.start(f, "codex", "R1", wb, verb="resume")
                if tag == "enforce":
                    ok, why = self.nothing_written(f, "R1-none", before, files, r)
                    self.check("N07d.enforce must fire, a resume names a new host: HOST+: other.test on "
                               "a lane opened with example.org: exit 2, the record byte-identical",
                               ok and "widens the lane's hosts" in r.stderr and len(self.seen(f, "R1")) == 3, why)
                else:
                    env = self.seen(f, "R1")
                    resumed = self.event(f, "R1", "lane-resumed")
                    would = (resumed.get("network_guard") or {}).get("would_refuse") or []
                    self.check("N07d.trial a new host logged: the resume proceeds, other.test is not "
                               "exported (the variable unset), the widening on lane-resumed",
                               r.returncode == 0 and len(env) == 4 and not env[3]["has"]
                               and any("widens the lane's hosts" in w for w in would),
                               {"rc": r.returncode, "env": env[3:], "would": would})
                # N07c: a lane spawned without network, resumed adding it, by the flag and by --config.
                nb = self.brief(f, "plain.md")
                self.start(f, "codex", "R2", nb, ["--write", str(f.root / "work")])
                for how, extra in (("--network", ["--network"]),
                                   ("--config", ["--config", "sandbox_workspace_write.network_access=true"])):
                    before, files = f.record.read_bytes(), self.store_files(f)
                    count = len(self.seen(f, "R2"))
                    r = self.start(f, "codex", "R2", follow, extra, verb="resume")
                    if tag == "enforce":
                        after = f.record.read_bytes()
                        self.check("N07c.enforce must fire, a resume adds shell network by %s: exit 2, "
                                   "the record byte-identical, the stand-in not started" % how,
                                   r.returncode == 2 and after == before and len(self.seen(f, "R2")) == count
                                   and "adds no shell network" in r.stderr,
                                   {"rc": r.returncode, "stderr": r.stderr[-300:]})
                    else:
                        resumed = self.event(f, "R2", "lane-resumed")
                        env = self.seen(f, "R2")
                        would = (resumed.get("network_guard") or {}).get("would_refuse") or []
                        self.check("N07c.trial adding shell network by %s logged: the resume proceeds "
                                   "with network and rule 5's export (the run grant, example.org)" % how,
                                   r.returncode == 0 and resumed.get("network") is True
                                   and any("adds no shell network" in w for w in would)
                                   and env and env[-1]["value"] == GRANTED,
                                   {"rc": r.returncode, "would": would, "env": env[-1:]})
            finally:
                f.cleanup()

    def codex_config(self):
        """N13 through the launcher: shell network opened by a --config extra."""
        for mode in ("shipped", "enforce"):
            tag = "trial" if mode == "shipped" else "enforce"
            f = self.fixture(self.tree(mode))
            try:
                nb = self.brief(f, "nohosts.md")
                for case, pair, opens, src in (
                        ("i", "sandbox_workspace_write.network_access=true", True,
                         "--config sandbox_workspace_write.network_access"),
                        ("ii", "sandbox_workspace_write.network_access=false", False, None),
                        ("iii", 'sandbox_mode="danger-full-access"', True,
                         "cannot decide: --config sandbox_mode may open the sandbox's network")):
                    lane_id = "C" + case
                    before, files = f.record.read_bytes(), self.store_files(f)
                    r = self.start(f, "codex", lane_id, nb, ["--write", str(f.root / "work"), "--config", pair])
                    env = self.seen(f, lane_id)
                    opened = self.event(f, lane_id, "lane-open")
                    if not opens:
                        self.check("N13%s.%s must not fire, --config %s: network false, no rule fires, the "
                                   "variable unset" % (case, tag, pair),
                                   r.returncode == 0 and opened.get("network") is False
                                   and "network_guard" not in opened and env and not env[0]["has"],
                                   {"rc": r.returncode, "open": opened.get("network"), "env": env})
                    elif tag == "enforce":
                        ok, why = self.nothing_written(f, lane_id, before, files, r)
                        self.check("N13%s.enforce must fire, --config %s opens shell network with no "
                                   "HOST+: refused by rule 1, nothing written" % (case, pair),
                                   ok and "names no hosts" in r.stderr and src in r.stderr, why)
                    else:
                        would = (opened.get("network_guard") or {}).get("would_refuse") or []
                        self.check("N13%s.trial --config %s: network true, network_src %r, rule 1 logged, "
                                   "the lane carries the run grant's hosts" % (case, pair, src),
                                   r.returncode == 0 and opened.get("network") is True
                                   and opened.get("network_src") == src and len(would) == 1
                                   and env and env[0]["value"] == GRANTED,
                                   {"rc": r.returncode, "src": opened.get("network_src"), "would": would,
                                    "env": env})
            finally:
                f.cleanup()

    def codex_grants_unread(self):
        """N14, N15: the run's grants file missing or unreadable (cannot decide: no grant)."""
        messages = {}
        for mode in ("shipped", "enforce"):
            tag = "trial" if mode == "shipped" else "enforce"
            for case, grants, words in (("N14", "missing", "the run's grants file is missing"),
                                        ("N15", "garbage", "the run's grants file is unreadable (")):
                f = self.fixture(self.tree(mode), grants=grants)
                try:
                    b = self.brief(f, "hosts.md", "HOST+: %s" % GRANTED)
                    before, files = f.record.read_bytes(), self.store_files(f)
                    r = self.start(f, "codex", case, b, self.codex_net(f))
                    if tag == "enforce":
                        ok, why = self.nothing_written(f, case, before, files, r)
                        messages[case] = r.stderr
                        self.check("%s.enforce cannot decide, the grants file %s: every declared host "
                                   "refuses, naming the file as %s" % (case, grants, words),
                                   ok and words in r.stderr, why)
                    else:
                        env = self.seen(f, case)
                        opened = self.event(f, case, "lane-open")
                        would = (opened.get("network_guard") or {}).get("would_refuse") or []
                        self.check("%s.trial cannot decide, the grants file %s: logged with the same "
                                   "reason, the variable unset" % (case, grants),
                                   r.returncode == 0 and env and not env[0]["has"]
                                   and any(words in w for w in would),
                                   {"rc": r.returncode, "env": env, "would": would})
                finally:
                    f.cleanup()
        self.check("N15b the unreadable file's refusal is distinct from the missing file's (missing is "
                   "never called corrupt)",
                   "unreadable (" in messages.get("N15", "") and "unreadable" not in messages.get("N14", "x")
                   and "missing" in messages.get("N14", ""), messages)

    def codex_mode_constant(self):
        """N16, N17 under one constant: nothing but the constant moves the mode."""
        f = self.fixture(self.tree("strict"))
        try:
            nb = self.brief(f, "nohosts.md")
            r = self.start(f, "codex", "M1", nb, self.codex_net(f))
            opened = self.event(f, "M1", "lane-open")
            guard = opened.get("network_guard") or {}
            self.check("N16 cannot decide, an unknown constant value (\"strict\" in a copy): read as "
                       "trial, the source naming the value; rule 1 logged, the spawn proceeds",
                       r.returncode == 0 and guard.get("mode") == "trial"
                       and "unknown NETWORK_GUARD_MODE 'strict'" in str(guard.get("mode_src"))
                       and len(guard.get("would_refuse") or []) == 1, {"rc": r.returncode, "guard": guard})
        finally:
            f.cleanup()
        f = self.fixture(self.wrappers, grants="mode-key")
        try:
            f.env["NETWORK_GUARD_MODE"] = "enforce"
            nb = self.brief(f, "nohosts.md")
            r = self.start(f, "codex", "M2", nb, self.codex_net(f))
            guard = self.event(f, "M2", "lane-open").get("network_guard") or {}
            self.check("N17 no grant or environment variable moves the mode: a grants file holding "
                       "network_guard enforce and NETWORK_GUARD_MODE=enforce in the environment leave the "
                       "shipped tree in trial (the spawn proceeds, rule 1 logged)",
                       r.returncode == 0 and guard.get("mode") == "trial"
                       and len(guard.get("would_refuse") or []) == 1, {"rc": r.returncode, "guard": guard})
            h = subprocess.run([sys.executable, "-B", str(self.wrappers / "handsoff.py"), "run-open", "--envelope-usd", "1000",
                                "--run", "fixture2", "--session", "sid-fixture2", "--head", "fixture head",
                                "--regime", "single", "--regime-src", "owner", "--handoff", str(f.ho),
                                "--detail", "fixture", "--viewer", "none", "--network-guard", "enforce"],
                               env=f.env, capture_output=True, text=True, timeout=60)
            self.check("N17b no flag moves the mode: handsoff.py run-open --network-guard is an unknown "
                       "option (exit 2, every required argument given), so no run can raise or lower it",
                       h.returncode == 2 and "unrecognized arguments: --network-guard" in h.stderr
                       and not (f.store / "spawn-records" / "fixture2.jsonl").exists(),
                       {"rc": h.returncode, "stderr": h.stderr[-300:]})
        finally:
            f.cleanup()

    def codex_detach_and_search(self):
        """N09 for Codex: the cooperative line once, from the caller, on a detached spawn; --search."""
        f = self.fixture(self.wrappers)
        try:
            b = self.brief(f, "hosts.md", "HOST+: %s" % GRANTED)
            r = self.start(f, "codex", "D1", b, self.codex_net(f) + ["--detach"])
            logs = sorted(f.store.rglob("*detach*D1*"))
            log = logs[0].read_text() if logs else ""
            opened = self.event(f, "D1", "lane-open")
            env = self.seen(f, "D1")
            self.check("N09a cannot decide, recorded once: a detached Codex --network spawn prints the "
                       "cooperative line once in the caller's stderr and none in the worker's detach log; "
                       "the worker's lane-open records network_enforcement cooperative; the lane never "
                       "sees the caller's hand-over variable",
                       r.returncode == 0 and r.stderr.count(COOPERATIVE) == 1 and logs
                       and log.count(COOPERATIVE) == 0
                       and opened.get("network_enforcement") == COOPERATIVE
                       and env and env[0]["value"] == GRANTED and not env[0]["seen_var"],
                       {"rc": r.returncode, "caller": r.stderr.count(COOPERATIVE),
                        "log": log.count(COOPERATIVE), "logs": [str(p.name) for p in logs], "env": env,
                        "stderr": r.stderr[-300:]})
            nb = self.brief(f, "nohosts.md")
            r = self.start(f, "codex", "D2", nb, self.codex_net(f) + ["--detach"])
            logs = sorted(f.store.rglob("*detach*D2*"))
            log = logs[0].read_text() if logs else ""
            would = (self.event(f, "D2", "lane-open").get("network_guard") or {}).get("would_refuse") or []
            self.check("N09f trial lines print once, from the caller: a detached Codex --network spawn "
                       "with no HOST+ prints rule 1's would-refuse line once in the caller's stderr and "
                       "none in the worker's detach log; the worker's lane-open records it",
                       r.returncode == 0 and len(guard_lines(r.stderr, "names no hosts")) == 1 and logs
                       and not guard_lines(log, "names no hosts") and len(would) == 1,
                       {"rc": r.returncode, "caller": guard_lines(r.stderr, "names no hosts"),
                        "log": guard_lines(log, "names no hosts"), "would": would})
            hb = self.brief(f, "hosts2.md", "HOST+: %s" % GRANTED)
            env = dict(f.env, CODEX_LANE_NETWORK_SEEN=OTHER)
            f.scenario("codex", events_for("codex", "clean"))
            command = f.command("codex", extra=self.codex_net(f) + ["--as-worker"])
            command[command.index("--lane") + 1] = "D3"
            command[command.index("--brief") + 1] = str(hb)
            w = subprocess.run(command, env=dict(env, A3_SCENARIO=f.env["A3_SCENARIO"],
                                                 A3_FAMILY="codex"),
                               capture_output=True, text=True, timeout=120)
            seen = self.seen(f, "D3")
            self.check("N09g a worker whose caller exported otherwise says so: run as a worker with the "
                       "caller's export other.test handed over, it names the change in its log (stderr), "
                       "records and exports its own (example.org), prints no cooperative line, and the "
                       "lane never sees the hand-over variable",
                       w.returncode == 0 and "grants changed between the caller's read and this worker's" in w.stderr
                       and seen and seen[0]["value"] == GRANTED and not seen[0]["seen_var"]
                       and w.stderr.count(COOPERATIVE) == 0,
                       {"rc": w.returncode, "seen": seen, "stderr": w.stderr[-400:]})
            r = self.start(f, "codex", "S1", self.brief(f, "plain.md"), ["--search"])
            opened = self.event(f, "S1", "lane-open")
            self.check("N09b cannot decide, recorded: a Codex --search lane-open records web_search "
                       "server-side, not bound to named hosts (no shell network, no network_guard)",
                       r.returncode == 0 and opened.get("web_search") == SEARCH_CODEX
                       and opened.get("network") is False and "network_guard" not in opened,
                       {"rc": r.returncode, "open": {k: opened.get(k) for k in (
                           "web_search", "network", "network_guard")}})
        finally:
            f.cleanup()

    # ------------------------------------------------------------------ the Claude part
    def part_claude(self):
        for mode in ("shipped", "enforce"):
            self.claude_legs(mode)
        self.claude_unbound()
        self.last_leg("lane")

    def claude_legs(self, mode):
        tag = "trial" if mode == "shipped" else "enforce"
        f = self.fixture(self.tree(mode))
        try:
            hb = self.brief(f, "hosts.md", "HOST+: %s" % GRANTED)
            before, files = f.record.read_bytes(), self.store_files(f)
            r = self.start(f, "claude", "L1", hb)
            if tag == "enforce":
                ok, why = self.nothing_written(f, "L1", before, files, r)
                self.check("N08.enforce must fire: lane.py spawn with a brief carrying HOST+: example.org "
                           "exits 2, pointed to codex-lane.py --network; the stand-in claude never "
                           "started, the record byte-identical",
                           ok and "codex-lane.py --network" in r.stderr, why)
            else:
                env = self.seen(f, "L1")
                opened = self.event(f, "L1", "lane-open")
                would = (opened.get("network_guard") or {}).get("would_refuse") or []
                self.check("N08.trial logged: the Claude spawn proceeds, its child has no "
                           "LLM_WIKI_LANE_NETWORK, the lane-open records network_inherited_dropped "
                           "planted.test and the would-refuse reason, one stderr line",
                           r.returncode == 0 and len(env) == 1 and not env[0]["has"]
                           and opened.get("network_inherited_dropped") == PLANTED and len(would) == 1
                           and "codex-lane.py --network" in would[0]
                           and len(guard_lines(r.stderr, "declares hosts")) == 1,
                           {"rc": r.returncode, "env": env, "would": would, "stderr": r.stderr[-300:]})
            pb = self.brief(f, "plain.md")
            r = self.start(f, "claude", "L2", pb)
            env = self.seen(f, "L2")
            opened = self.event(f, "L2", "lane-open")
            self.check("N12i.%s must not fire, inherited grant: a Claude spawn with no HOST+ runs, its "
                       "child carries no LLM_WIKI_LANE_NETWORK, the lane-open records "
                       "network_inherited_dropped planted.test and no network_guard" % tag,
                       r.returncode == 0 and len(env) == 1 and not env[0]["has"]
                       and opened.get("network_inherited_dropped") == PLANTED and "network_guard" not in opened,
                       {"rc": r.returncode, "env": env, "open": {k: opened.get(k) for k in (
                           "network_inherited_dropped", "network_guard")}, "stderr": r.stderr[-300:]})
            qb = self.brief(f, "quoted.md", "Name hosts with `HOST+: %s` in a Codex brief." % GRANTED)
            r = self.start(f, "claude", "L3", qb)
            opened = self.event(f, "L3", "lane-open")
            self.check("N10c.%s must not fire, a quoted HOST+ is a mention: the Claude spawn runs with no "
                       "network_guard" % tag, r.returncode == 0 and "network_guard" not in opened,
                       {"rc": r.returncode, "stderr": r.stderr[-300:]})
            follow = self.brief(f, "follow.md", "Continue.")
            r = self.start(f, "claude", "L2", follow, verb="resume")
            env = self.seen(f, "L2")
            resumed = self.event(f, "L2", "lane-resumed")
            self.check("N12ii.%s inherited grant on a Claude resume: the resumed child carries no "
                       "LLM_WIKI_LANE_NETWORK and lane-resumed records network_inherited_dropped" % tag,
                       r.returncode == 0 and len(env) == 2 and not env[1]["has"]
                       and resumed.get("network_inherited_dropped") == PLANTED,
                       {"rc": r.returncode, "env": env, "stderr": r.stderr[-300:]})
            before = f.record.read_bytes()
            r = self.start(f, "claude", "L2", hb, verb="resume")
            if tag == "enforce":
                self.check("N08r.enforce must fire, a Claude resume whose brief names hosts: exit 2, the "
                           "record byte-identical, the stand-in not started",
                           r.returncode == 2 and f.record.read_bytes() == before and len(self.seen(f, "L2")) == 2,
                           {"rc": r.returncode, "stderr": r.stderr[-300:]})
            else:
                resumed = self.event(f, "L2", "lane-resumed")
                would = (resumed.get("network_guard") or {}).get("would_refuse") or []
                self.check("N08r.trial a Claude resume whose brief names hosts: logged on lane-resumed, "
                           "the resume proceeds", r.returncode == 0 and len(would) == 1,
                           {"rc": r.returncode, "would": would})
        finally:
            f.cleanup()

    def claude_unbound(self):
        """N09 for Claude: what no host list binds, recorded on the lane-open, refused never."""
        f = self.fixture(self.wrappers)
        try:
            mcp = f.root / "mcp.json"
            mcp.write_text('{"mcpServers": {}}\n')
            pb = self.brief(f, "plain.md")
            r = self.start(f, "claude", "U1", pb)
            opened = self.event(f, "U1", "lane-open")
            self.check("N09c cannot decide, recorded: a Claude lane whose tools include Bash records "
                       "network_unbound in the design's words, and no web_search (its class allows none)",
                       r.returncode == 0 and opened.get("network_unbound") == UNBOUND_BASH
                       and "web_search" not in opened, {"rc": r.returncode, "open": {
                           k: opened.get(k) for k in ("network_unbound", "web_search", "tools")}})
            r = self.start(f, "claude", "U2", pb, cls="fixture-search")
            opened = self.event(f, "U2", "lane-open")
            self.check("N09d cannot decide, recorded: a Claude lane holding WebSearch records web_search "
                       "server-side, not bound to named hosts",
                       r.returncode == 0 and "WebSearch" in (opened.get("tools") or [])
                       and opened.get("web_search") == SEARCH_CLAUDE,
                       {"rc": r.returncode, "open": {k: opened.get(k) for k in ("web_search", "tools")},
                        "stderr": r.stderr[-300:]})
            r = self.start(f, "claude", "U3", pb, ["--mcp-config", str(mcp)])
            opened = self.event(f, "U3", "lane-open")
            self.check("N09e cannot decide, recorded: a Claude lane given a tool server (--mcp-config) "
                       "records it as unbound beside Bash's clause",
                       r.returncode == 0 and str(opened.get("network_unbound", "")).startswith(UNBOUND_BASH)
                       and "tool servers (--mcp-config)" in str(opened.get("network_unbound")),
                       {"rc": r.returncode, "unbound": opened.get("network_unbound"), "stderr": r.stderr[-300:]})
        finally:
            f.cleanup()

    # ------------------------------------------------------------------ the last leg
    def last_leg(self, part):
        """N11: the wrappers byte-identical and no __pycache__; control: one changed byte in a copy
        of a file, in a copied folder, under the same permissions, which the comparison catches."""
        after = manifest(self.wrappers)
        copy = self.root / ("manifest-control-" + part)
        shutil.copytree(self.wrappers, copy, ignore=shutil.ignore_patterns("__pycache__"))
        held = manifest(copy)
        target = copy / "lane.py"
        mode = stat.S_IMODE(target.stat().st_mode)
        data = bytearray(target.read_bytes())
        data[0] = data[0] ^ 1
        target.write_bytes(bytes(data))
        os.chmod(target, mode)
        changed = manifest(copy)
        caught = sorted(k for k in set(held[0]) | set(changed[0]) if held[0].get(k) != changed[0].get(k))
        self.check("N11.%s the wrappers folder is byte-identical (hash and mode) before and after, with no "
                   "__pycache__ (control: one changed byte of lane.py in a copied folder, same mode, is "
                   "caught as exactly that file)" % part,
                   after == self.before and not after[1] and caught == ["lane.py"]
                   and held[0] == {k: v for k, v in self.before[0].items()},
                   {"changed": sorted(k for k in set(after[0]) | set(self.before[0])
                                      if after[0].get(k) != self.before[0].get(k)),
                    "pycache": after[1], "caught": caught})

    def finish(self):
        shutil.rmtree(self.root, ignore_errors=True)
        total = self.passed + self.failed
        if not total:
            print("PROBE FAILED: no leg ran (--only matched nothing?)")
            return 2
        print(("PASS %d/%d" % (self.passed, total)) if not self.failed else "FAIL %d/%d" % (self.failed, total))
        return 1 if self.failed else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wrappers", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--fixture-root", default=None)
    ap.add_argument("--part", choices=("all", "codex", "lane"), default="all",
                    help="codex: codex-lane.py's legs; lane: lane.py's (the Claude launcher), as "
                         "test_item_bars.py names its parts")
    ap.add_argument("--capture-probe", default=None,
                    help="capture_probe.py, read only (default: ../gather/capture_probe.py beside the wrappers)")
    ap.add_argument("--only", action="append", default=[])
    args = ap.parse_args()
    try:
        suite = Suite(args)
    except SystemExit as exc:
        print(exc.code if isinstance(exc.code, str) else "PROBE FAILED: suite set-up")
        return 2
    try:
        if args.part in ("all", "codex"):
            suite.part_codex()
        if args.part in ("all", "lane"):
            suite.part_claude()
    except SystemExit as exc:
        print(exc.code if isinstance(exc.code, str) else "PROBE FAILED: exit %r" % exc.code)
        shutil.rmtree(suite.root, ignore_errors=True)
        return 2
    return suite.finish()


if __name__ == "__main__":
    sys.exit(main())
