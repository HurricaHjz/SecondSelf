#!/usr/bin/env python3
"""test_ledger_check.py - the ledger clock and configuration check on planted fixture ledgers.

Run: python3 test_ledger_check.py [path/to/ledger_check.py]   (default: beside this file)
Legs replay the ledger symptoms (lanes logging `effort standard` against a brief's max; lane
clocks hours fast, then a true-clock line appended after), a clean ledger that must not fire, the
tolerances, every premise failure, and a last leg proving the check wrote nothing. Fixtures live
under one mkdtemp, removed at the end. Ends `PASS n/n` or `FAIL k/n`.
"""
import datetime, hashlib, importlib.util, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "ledger_check.py")
TMP = tempfile.mkdtemp(prefix="ledger-check-test-")
P = F = 0


def check(name, cond, detail=""):
    global P, F
    if cond:
        P += 1
        print(f"ok   {name}")
    else:
        F += 1
        print(f"FAIL {name}" + ("\n     " + detail.strip().replace("\n", "\n     ") if detail else ""))


NOW = datetime.datetime.now().astimezone()
T0 = NOW - datetime.timedelta(days=2)


def stamp(dt):
    return dt.strftime("%Y-%m-%dT%H:%M%z")


def at(minutes):
    return T0 + datetime.timedelta(minutes=minutes)


def ledger(name, events, mtime_min=None, raw_lines=()):
    p = os.path.join(TMP, name)
    with open(p, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")
        for line in raw_lines:
            fh.write(line + "\n")
    if mtime_min is not None:
        t = at(mtime_min).timestamp()
        os.utime(p, (t, t))
    return p


def brief(name, first):
    p = os.path.join(TMP, name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(first + "\n\nTASK\nCompile the sources.\n")
    return p


def run(*args):
    return subprocess.run([sys.executable, "-B", CHECK, *args], capture_output=True, text=True)


def out(r):
    return f"exit {r.returncode}\n{r.stdout}{r.stderr}"


def offence_lines(r):
    return [int(n) for n in re.findall(r"(?m)^OFFENCE line (\d+) ", r.stdout)]


# the template wraps the first line, so the fixture brief does too
MAX_BRIEF = brief("brief-L1.md", "You are wiki-compile (definition: .claude/agents/wiki-compile.md), lane L1 of run\n"
                                 "run-fixture · model claude-opus-5[1m] · effort max.")
OPEN = {"event": "run_open", "run": "run-fixture"}

print("== the ledger symptoms (must fire) ==")
p = ledger("fast.jsonl", [dict(OPEN, ts=stamp(at(0))),
                          {"event": "lane_open", "lane": "L1", "ts": stamp(at(420))},
                          {"event": "checkpoint", "lane": "L1", "ts": stamp(at(425))},
                          {"event": "run_close", "lane": "head", "ts": stamp(at(30))}], mtime_min=35)
r = run(p, "--no-config")
check("S1 lane clocks 7 h fast with a true-clock line after them -> exit 1, lines 2 and 3",
      r.returncode == 1 and offence_lines(r) == [2, 3] and "last modification" in r.stdout and "appended later" in r.stdout, out(r))
p = ledger("future.jsonl", [dict(OPEN, ts=stamp(NOW - datetime.timedelta(minutes=5))),
                            {"event": "checkpoint", "lane": "L1", "ts": stamp(NOW + datetime.timedelta(hours=2))}])
r = run(p, "--no-config")
check("S2 a ts two hours after the wall clock -> exit 1", r.returncode == 1 and offence_lines(r) == [2] and "wall clock now" in r.stdout, out(r))
p = ledger("effort.jsonl", [dict(OPEN, ts=stamp(at(0))),
                            {"event": "lane_open", "lane": "L1", "ts": stamp(at(1)), "model": "claude-opus-5[1m]", "effort": "standard"}], mtime_min=5)
r = run(p, "--brief", f"L1={MAX_BRIEF}")
check("S3 `effort standard` against a brief slot of max -> exit 1 config offence (model passes)",
      r.returncode == 1 and offence_lines(r) == [2] and 'effort "standard" absent' in r.stdout and 'model "' not in r.stdout, out(r))
p = ledger("named.jsonl", [dict(OPEN, ts=stamp(at(0))),
                           {"event": "lane_open", "lane": "L1", "ts": stamp(at(1)), "model": "opus", "effort": "max", "brief": MAX_BRIEF}], mtime_min=5)
r = run(p)
check("S4 a brief named on lane_open is read: model `opus` is not the slot's verbatim string",
      r.returncode == 1 and 'model "opus" absent' in r.stdout, out(r))

print("== clean and tolerated cases (must not fire) ==")
p = ledger("clean.jsonl", [dict(OPEN, ts=stamp(at(0))),
                           {"event": "lane_open", "lane": "L1", "ts": stamp(at(1)), "model": "claude-opus-5[1m]", "effort": "max"},
                           {"event": "checkpoint", "lane": "L2", "ts": stamp(at(3))},
                           {"event": "checkpoint", "lane": "L1", "ts": stamp(at(2))},
                           {"event": "lane_open", "lane": "L3", "ts": stamp(at(4))},
                           {"event": "run_close", "lane": "head", "ts": stamp(at(9))}], mtime_min=10)
r = run(p, "--brief", f"L1={MAX_BRIEF}")
check("C1 honest ledger: verbatim config, a 1 min parallel inversion, an omitted config -> exit 0",
      r.returncode == 0 and "future-ts offences 0" in r.stdout and "config offences 0" in r.stdout
      and "1 events over 1 lanes checked" in r.stdout and "UNCHECKED" not in r.stdout, out(r))
check("C1 the same run printed its planted controls", "controls: planted" in r.stdout, out(r))
p = ledger("edge.jsonl", [dict(OPEN, ts=stamp(at(10))), {"event": "checkpoint", "lane": "L1", "ts": stamp(at(5))}], mtime_min=10)
r = run(p, "--no-config")
check("C2 a 5 min inversion sits at the tolerance and does not fire", r.returncode == 0, out(r))
p = ledger("edge6.jsonl", [dict(OPEN, ts=stamp(at(11))), {"event": "checkpoint", "lane": "L1", "ts": stamp(at(5))}], mtime_min=11)
r = run(p, "--no-config")
check("C2 a 6 min inversion fires", r.returncode == 1 and offence_lines(r) == [1], out(r))

print("== premise failures (exit 2, never clean) ==")
r = run(os.path.join(TMP, "absent.jsonl"))
check("F1 missing ledger", r.returncode == 2 and "ledger unreadable" in r.stdout, out(r))
r = run(ledger("empty.jsonl", []))
check("F2 empty ledger", r.returncode == 2 and "no parseable event" in r.stdout, out(r))
p = ledger("malformed.jsonl", [dict(OPEN, ts=stamp(at(0)))], mtime_min=5, raw_lines=['{"event": "checkpoint", "ts": '])
r = run(p, "--no-config")
check("F3 a malformed line with no offence -> not proven clean", r.returncode == 2 and "UNCHECKED line 2 malformed" in r.stdout and "not proven clean" in r.stdout, out(r))
p = ledger("nots.jsonl", [dict(OPEN, ts=stamp(at(0))), {"event": "checkpoint", "lane": "L1"},
                          {"event": "checkpoint", "lane": "L1", "ts": "2026-09-01T11:24"}, {"event": "checkpoint", "ts": "probe"}], mtime_min=5)
r = run(p, "--no-config")
check("F4 absent, offset-less and unparseable ts are listed unchecked -> exit 2",
      r.returncode == 2 and "line 2 ts absent" in r.stdout and "line 3 ts '2026-09-01T11:24'" in r.stdout and "line 4 ts 'probe'" in r.stdout, out(r))
p = ledger("nobrief.jsonl", [dict(OPEN, ts=stamp(at(0))), {"event": "lane_open", "lane": "L1", "ts": stamp(at(1)), "model": "opus", "effort": "max"}], mtime_min=5)
r = run(p)
check("F5 config present, no brief named -> exit 2 with the lane unchecked", r.returncode == 2 and "UNCHECKED lane L1 config: no brief named" in r.stdout, out(r))
r = run(p, "--no-config")
check("F5 --no-config runs the ts check alone and says so", r.returncode == 0 and "config skipped (--no-config)" in r.stdout, out(r))
for label, first in [("F6 a brief whose first line has no slot", "You are builder, lane L1 of run run-fixture."),
                     ("F6 an unfilled template slot", "You are wiki-compile, lane L1 of run run-fixture · model {{model}} · effort {{effort}}.")]:
    r = run(p, "--brief", f"L1={brief('slotless.md', first)}")
    check(label + " -> lane unchecked, exit 2", r.returncode == 2 and "no filled model/effort slot" in r.stdout, out(r))
r = run(p, "--brief", f"L1={os.path.join(TMP, 'no-such-brief.md')}")
check("F7 a named brief that is missing -> lane unchecked, exit 2", r.returncode == 2 and "brief unreadable" in r.stdout, out(r))
p = ledger("both.jsonl", [dict(OPEN, ts=stamp(NOW + datetime.timedelta(hours=3))), {"event": "checkpoint"}], mtime_min=5)
r = run(p, "--no-config")
check("F8 offences with unchecked lines -> exit 1, both listed", r.returncode == 1 and "OFFENCE line 1" in r.stdout and "UNCHECKED line 2" in r.stdout, out(r))
r = run(p, "--brief", "L1")
check("F9 a malformed --brief -> exit 2", r.returncode == 2 and "LANE=PATH" in r.stdout, out(r))
spec = importlib.util.spec_from_file_location("ledger_check_under_test", CHECK)
mod = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(mod)
check("F10 a bare run id resolves under the agent home's ingest-runs",
      mod.resolve("20990101-fixture").endswith(os.path.join(".llm-wiki", "ingest-runs", "run-20990101-fixture.jsonl")))
real = mod.future_reasons
mod.future_reasons = lambda *a: []
planted = mod.controls()
mod.future_reasons = real
check("F11 the controls catch a planted dead future-ts check, and pass the real one", len(planted) == 3 and mod.controls() == [], repr(planted))

print("== the check wrote nothing ==")
ro = os.path.join(TMP, "readonly")
os.makedirs(ro)
for name in ("fast.jsonl", "effort.jsonl", "clean.jsonl", "nobrief.jsonl", "brief-L1.md"):
    shutil.copy2(os.path.join(TMP, name), os.path.join(ro, name))


def manifest(top):
    rows = []
    for root, dirs, files in os.walk(top):
        rows.append((os.path.relpath(root, top), tuple(sorted(dirs + files))))
        for f in sorted(files):
            q = os.path.join(root, f)
            with open(q, "rb") as fh:
                rows.append((f, os.stat(q).st_mtime_ns, hashlib.sha256(fh.read()).hexdigest()))
    return rows


before = manifest(ro)
for f in os.listdir(ro):
    os.chmod(os.path.join(ro, f), 0o444)
os.chmod(ro, 0o555)
codes = [run(os.path.join(ro, "fast.jsonl"), "--no-config").returncode,
         run(os.path.join(ro, "effort.jsonl"), "--brief", f"L1={os.path.join(ro, 'brief-L1.md')}").returncode,
         run(os.path.join(ro, "clean.jsonl"), "--brief", f"L1={os.path.join(ro, 'brief-L1.md')}").returncode,
         run(os.path.join(ro, "nobrief.jsonl")).returncode]
after = manifest(ro)
check("W1 runs on the read-only copy gave 1, 1, 0, 2", codes == [1, 1, 0, 2], repr(codes))
check("W1 checksum manifest identical before and after", before == after and len(before) == 6, f"{len(before)} / {len(after)} rows")
WRITES = re.compile(r"""open\([^,()]+,\s*['"][rbt]*[wax+][rwaxbt+]*['"]|mode\s*=\s*['"][rbt]*[wax+]"""
                    r"""|os\.(?:replace|rename|remove|unlink|makedirs|mkdir|rmdir|chmod|utime|truncate)\("""
                    r"""|shutil\.|\.write(?:_text|_bytes)?\(|\.(?:touch|unlink)\(""")
with open(CHECK, encoding="utf-8") as fh:
    hits = WRITES.findall(fh.read())
control = 'open(p, "w")\nos.replace(a, b)\nshutil.rmtree(d)\nfh.write(x)\n'
check("W2 write-pattern grep: 0 hits in the check's source, control snippet hits 4",
      hits == [] and len(WRITES.findall(control)) == 4, f"source hits {hits}")

os.chmod(ro, 0o755)
for f in os.listdir(ro):
    os.chmod(os.path.join(ro, f), 0o644)
shutil.rmtree(TMP)
print(f"PASS {P}/{P + F}" if not F else f"FAIL {F}/{P + F}")
sys.exit(1 if F else 0)
