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

print("== a verify event from another model family (judged against its verifier's brief) ==")
C1_BRIEF = brief("brief-C1.md", "You are wiki-compile (definition: .claude/agents/wiki-compile.md), lane C1 of run\n"
                                "run-fixture · model opus · effort xhigh.")
V1_BRIEF = brief("brief-V1.md", "You are verifier (definition: .claude/agents/verifier.md), lane V1 of run\n"
                                "run-fixture · model other-family-1 · effort xhigh.")
V1_OPUS = brief("brief-V1-opus.md", "You are verifier (definition: .claude/agents/verifier.md), lane V1 of run\n"
                                    "run-fixture · model opus · effort xhigh.")
# The ledger shape of the register entry: compile lane C1 on opus, verifier V1 on another family, and the
# head-written verify event carrying lane C1, verifier V1 and the verifier's model and effort.
CROSS = [dict(OPEN, ts=stamp(at(0))),
         {"event": "lane_open", "lane": "C1", "role": "compile", "ts": stamp(at(1)), "model": "opus", "effort": "xhigh"},
         {"event": "lane_close", "lane": "C1", "ts": stamp(at(2))},
         {"event": "lane_open", "lane": "V1", "role": "verify", "ts": stamp(at(3)), "model": "other-family-1", "effort": "xhigh"},
         {"event": "verify", "lane": "C1", "verifier": "V1", "ts": stamp(at(4)), "model": "other-family-1", "effort": "xhigh"},
         {"event": "lane_close", "lane": "V1", "ts": stamp(at(5))}]
p = cross = ledger("cross.jsonl", CROSS, mtime_min=10)
r = run(p, "--brief", f"C1={C1_BRIEF}", "--brief", f"V1={V1_BRIEF}")
check("X1 a verify event on model other-family-1 for compile lane C1 (opus) is judged against verifier V1's brief -> exit 0",
      r.returncode == 0 and "config offences 0" in r.stdout and "3 events over 2 lanes checked" in r.stdout and "UNCHECKED" not in r.stdout, out(r))
r = run(p, "--brief", f"C1={C1_BRIEF}", "--brief", f"V1={V1_OPUS}")
check("X1 control: the same event against a verifier brief whose slot is opus fires on the verify line, naming V1",
      r.returncode == 1 and 5 in offence_lines(r)
      and re.search(r'(?m)^OFFENCE line 5 config: lane V1 \(verifier of lane C1\) model "other-family-1" absent', r.stdout) is not None, out(r))
p = ledger("noverifier.jsonl", [dict(OPEN, ts=stamp(at(0))),
                                {"event": "lane_open", "lane": "C1", "ts": stamp(at(1)), "model": "opus", "effort": "xhigh"},
                                {"event": "verify", "lane": "C1", "ts": stamp(at(2)), "model": "other-family-1", "effort": "xhigh"}], mtime_min=5)
r = run(p, "--brief", f"C1={C1_BRIEF}")
r1 = run(cross, "--brief", f"C1={C1_BRIEF}", "--brief", f"V1={V1_BRIEF}")
check("X2 the verifier field decides the brief: with it the event reads V1's (clean), without it its own lane C1's (fires)",
      r1.returncode == 0 and r.returncode == 1 and offence_lines(r) == [3]
      and 'OFFENCE line 3 config: lane C1 model "other-family-1" absent' in r.stdout, out(r1) + out(r))
r = run(ledger("cross-nobrief.jsonl", CROSS, mtime_min=10), "--brief", f"C1={C1_BRIEF}")
check("X3 a verifier with no brief leaves its lane unchecked (exit 2), never judged against the compile brief",
      r.returncode == 2 and "UNCHECKED lane V1 config: no brief named" in r.stdout and "OFFENCE" not in r.stdout, out(r))
real_lane, dead, shape = getattr(mod, "config_lane", None), None, None
if real_lane:
    # The wrong lane in the right return type (review advice A5), so only a control that checks which lane
    # was chosen can catch it; a control that checks the return type alone passes it.
    mod.config_lane = lambda ev: (ev.get("lane") or "(no lane)", None)
    dead = mod.controls()
    # The right lane in the wrong return type: caught on its type alone, and told apart from the leg above.
    mod.config_lane = lambda ev: (ev["verifier"] if ev.get("event") == "verify" and isinstance(ev.get("verifier"), str)
                                  and ev["verifier"].strip() else ev.get("lane") or "(no lane)")
    shape = mod.controls()
    mod.config_lane = real_lane
check("X4 the controls catch a planted check that reads a verify event's lane, not its verifier, in the right return type, and pass the real one",
      real_lane is not None and dead == ["verify event read through its verifier field"] and mod.controls() == [], repr(dead))
check("X4 control: the controls also catch the right lane returned as a bare string, a fault of type, not of lane choice",
      real_lane is not None and shape == ["verify event read through its verifier field"], repr(shape))

print("== a verify event whose verifier field is present but unusable (left unchecked, never read as its compile lane) ==")
# The planted harm: the verify event's model and effort equal compile brief C1's slots, so a check that falls
# back to the compile lane reads it clean against the wrong brief.
def unusable_ledger(name, verifier, extra=(), model="opus"):
    rows = [dict(OPEN, ts=stamp(at(0))),
            {"event": "lane_open", "lane": "C1", "role": "compile", "ts": stamp(at(1)), "model": "opus", "effort": "xhigh"},
            {"event": "lane_close", "lane": "C1", "ts": stamp(at(2))},
            {"event": "lane_open", "lane": "V1", "role": "verify", "ts": stamp(at(3)), "model": "other-family-1", "effort": "xhigh"},
            {"event": "verify", "lane": "C1", "verifier": verifier, "ts": stamp(at(4)), "model": model, "effort": "xhigh"},
            {"event": "lane_close", "lane": "V1", "ts": stamp(at(5))}] + list(extra)
    return ledger(name, rows, mtime_min=10)


for n, (label, value) in enumerate([("an integer", 7), ("an empty string", ""), ("null", None), ("a list", ["V1"]),
                                    ("an object", {"lane": "V1"}), ("a whitespace string", "   ")]):
    r = run(unusable_ledger("unusable-%d.jsonl" % n, value), "--brief", f"C1={C1_BRIEF}", "--brief", f"V1={V1_BRIEF}")
    check("X5 a verifier field holding " + label + " -> exit 2, the verify line UNCHECKED, no offence, not proven clean",
          r.returncode == 2 and re.search(r"(?m)^UNCHECKED line 5 config: the verify event's verifier field is present but unusable", r.stdout) is not None
          and "not proven clean" in r.stdout and "OFFENCE" not in r.stdout, out(r))
r = run(unusable_ledger("usable.jsonl", "V1", model="other-family-1"), "--brief", f"C1={C1_BRIEF}", "--brief", f"V1={V1_BRIEF}")
check("X6 control: a usable verifier V1 whose event carries V1's own model -> exit 0, nothing unchecked",
      r.returncode == 0 and "UNCHECKED" not in r.stdout and "config offences 0" in r.stdout, out(r))
r = run(unusable_ledger("usable-wrong.jsonl", "V1"), "--brief", f"C1={C1_BRIEF}", "--brief", f"V1={V1_BRIEF}")
check("X6 control: a usable verifier V1 with the compile lane's model fires against V1's brief, never reads clean as C1",
      r.returncode == 1 and re.search(r'(?m)^OFFENCE line 5 config: lane V1 \(verifier of lane C1\) model "opus" absent', r.stdout) is not None
      and "UNCHECKED" not in r.stdout, out(r))
future = {"event": "checkpoint", "lane": "C1", "ts": stamp(NOW + datetime.timedelta(hours=3))}
r = run(unusable_ledger("unusable-offence.jsonl", 7, [future]), "--brief", f"C1={C1_BRIEF}", "--brief", f"V1={V1_BRIEF}")
check("X7 an unusable verifier beside a real offence -> exit 1, the OFFENCE and the UNCHECKED line both listed",
      r.returncode == 1 and "OFFENCE line 7" in r.stdout and "UNCHECKED line 5 config:" in r.stdout, out(r))
r = run(unusable_ledger("unusable-summary.jsonl", None), "--brief", f"C1={C1_BRIEF}", "--brief", f"V1={V1_BRIEF}")
check("X8 the summary counts the unusable verifier as an unchecked config event",
      re.search(r"(?m)^summary: .* · unchecked config events 1$", r.stdout) is not None, out(r))
real_lane = mod.config_lane
# The planted copy keeps the signature of the module under test, so only the fallback differs and a
# signature change alone can never make this leg pass.
PAIRED = isinstance(real_lane({"event": "lane_open", "lane": "C1"}), tuple)


def old_fallback(ev):
    """Today's fallback, in the tested module's own signature: an unusable verifier reads the compile lane."""
    verifier = ev.get("verifier")
    lane = verifier if ev.get("event") == "verify" and isinstance(verifier, str) and verifier else (ev.get("lane") or "(no lane)")
    return (lane, None) if PAIRED else lane


mod.config_lane = old_fallback
planted_old = mod.controls()
mod.config_lane = real_lane
check("X9 the controls catch a planted copy with the new signature and today's fallback, and pass the real one",
      planted_old == ["verify event read through its verifier field"] and mod.controls() == [], repr(planted_old))

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

ro2 = os.path.join(TMP, "readonly-cross")
os.makedirs(ro2)
for name in ("cross.jsonl", "brief-C1.md", "brief-V1.md"):
    shutil.copy2(os.path.join(TMP, name), os.path.join(ro2, name))
before2 = manifest(ro2)
for f in os.listdir(ro2):
    os.chmod(os.path.join(ro2, f), 0o444)
os.chmod(ro2, 0o555)
code = run(os.path.join(ro2, "cross.jsonl"), "--brief", f"C1={os.path.join(ro2, 'brief-C1.md')}",
           "--brief", f"V1={os.path.join(ro2, 'brief-V1.md')}").returncode
after2 = manifest(ro2)
victim = os.path.join(ro2, "brief-V1.md")    # control: one byte changed in the same folder, modes put back
os.chmod(ro2, 0o755); os.chmod(victim, 0o644)
with open(victim, "r+b") as fh:
    first = fh.read(1); fh.seek(0); fh.write(b"X" if first != b"X" else b"Y")
os.chmod(victim, 0o444); os.chmod(ro2, 0o555)
changed = manifest(ro2)
check("W3 the cross-family run on a read-only copy exits 0 with its manifest identical; a byte changed there is caught",
      code == 0 and before2 == after2 and len(before2) == 4 and changed != before2, f"exit {code} · {len(before2)} / {len(after2)} rows")

ro3 = os.path.join(TMP, "readonly-unusable")
os.makedirs(ro3)
for name in ("unusable-0.jsonl", "brief-C1.md", "brief-V1.md"):
    shutil.copy2(os.path.join(TMP, name), os.path.join(ro3, name))
before3 = manifest(ro3)
for f in os.listdir(ro3):
    os.chmod(os.path.join(ro3, f), 0o444)
os.chmod(ro3, 0o555)
code3 = run(os.path.join(ro3, "unusable-0.jsonl"), "--brief", f"C1={os.path.join(ro3, 'brief-C1.md')}",
            "--brief", f"V1={os.path.join(ro3, 'brief-V1.md')}").returncode
after3 = manifest(ro3)
victim3 = os.path.join(ro3, "brief-C1.md")    # control: one byte changed in the same folder, modes put back
os.chmod(ro3, 0o755); os.chmod(victim3, 0o644)
with open(victim3, "r+b") as fh:
    first = fh.read(1); fh.seek(0); fh.write(b"X" if first != b"X" else b"Y")
os.chmod(victim3, 0o444); os.chmod(ro3, 0o555)
changed3 = manifest(ro3)
check("W4 the unusable-verifier run on a read-only copy exits 2 with its manifest identical; a byte changed there is caught",
      code3 == 2 and before3 == after3 and len(before3) == 4 and changed3 != before3, f"exit {code3} · {len(before3)} / {len(after3)} rows")

for top in (ro, ro2, ro3):
    os.chmod(top, 0o755)
    for f in os.listdir(top):
        os.chmod(os.path.join(top, f), 0o644)
shutil.rmtree(TMP)
print(f"PASS {P}/{P + F}" if not F else f"FAIL {F}/{P + F}")
sys.exit(1 if F else 0)
