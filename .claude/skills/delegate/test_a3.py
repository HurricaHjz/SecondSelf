#!/usr/bin/env python3
"""A3 public-path fixtures. Model executables and successor starts are local fixture programs.

Each captured command includes its public result, records, journals, report bytes and actual
successor process count. The suite writes only inside its mktemp directory, which it removes.
Harness timeout ceilings are set by judgement, unmeasured; barriers choose race schedules.
"""
import argparse
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import select
import shlex
import shutil
import signal
import subprocess
import sys
import time


# CR-A3-1 M3 (spec), accepted C9 recorded provider events; quoted verbatim.
POLICY_EVENTS = [{'type': 'error', 'message': 'This content was flagged for possible cybersecurity risk. If this seems wrong, try rephrasing your request. If you’re doing authorized security work that requires more cyber permissive safeguards, apply for Daybreak access via https://platform.openai.com/settings/organization/status-and-access before retrying.'}, {'type': 'turn.failed', 'error': {'message': 'This content was flagged for possible cybersecurity risk. If this seems wrong, try rephrasing your request. If you’re doing authorized security work that requires more cyber permissive safeguards, apply for Daybreak access via https://platform.openai.com/settings/organization/status-and-access before retrying.'}}]


PROVIDER = r'''
import json,os,re,sys,time
from pathlib import Path
if "--version" in sys.argv:
    print("fixture provider 1")
    raise SystemExit(0)
root=Path(os.environ["A3_FIXTURE"])
scenario=json.loads(Path(os.environ["A3_SCENARIO"]).read_text())
family=os.environ["A3_FAMILY"]
prompt=sys.stdin.read()
if prompt=="Reply with the single word ok.":
    (root/"probe-input").write_text(prompt)
    print(json.dumps(scenario.get("probe_result",{})),flush=True)
    raise SystemExit(scenario.get("probe_exit",0))
(root/(family+"-input")).write_text(prompt)
def flag(name):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else None
# The child-started crash fixture stops before provider evidence exists.
if scenario.get("wait_before_events"):
    (root/"provider-before-events").write_text(str(os.getpid()))
    while not (root/"provider-events-release").exists():
        time.sleep(0.01)
if family=="claude":
    sid=flag("--session-id") or flag("--resume")
    project=re.sub(r"[^A-Za-z0-9]","-",str(Path.cwd().resolve()))
    target=root/"projects"/project/(sid+".jsonl")
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("a") as handle:
        for event in scenario["events"]:
            handle.write(json.dumps(event)+"\n")
            handle.flush()
            os.fsync(handle.fileno())
else:
    print(json.dumps({"type":"thread.started","thread_id":"fixture-thread"}),flush=True)
    for event in scenario["events"]:
        print(json.dumps(event),flush=True)
if scenario.get("wait"):
    (root/"provider-ready").write_text(str(os.getpid()))
    while not (root/"provider-release").exists():
        time.sleep(0.01)
if scenario.get("late_events"):
    late_pid=os.fork()
    if late_pid==0:
        (root/"late-ready").write_text(str(os.getpid()))
        until=time.monotonic()+30  # Fixture lifetime ceiling: set by judgement, unmeasured.
        while not (root/"late-release").exists() and root.exists() and time.monotonic()<until:
            time.sleep(0.01)
        if (root/"late-release").exists():
            for event in scenario["late_events"]:
                if family=="claude":
                    with target.open("a") as handle:
                        handle.write(json.dumps(event)+"\n");handle.flush();os.fsync(handle.fileno())
                else:
                    print(json.dumps(event),flush=True)
        os._exit(0)
if family=="claude":
    print(json.dumps(scenario.get("result",{"type":"result","subtype":"success","is_error":False,
          "result":"fixture final report","num_turns":1,"total_cost_usd":0.1})),flush=True)
else:
    out=flag("-o")
    if out:
        Path(out).write_text("fixture final report\n")
raise SystemExit(scenario.get("exit",0))
'''

SUCCESSOR = r'''
import fcntl,json,os,sys
from pathlib import Path
root=Path(os.environ["A3_FIXTURE"])
def values(flag):
    return [sys.argv[i+1] for i,a in enumerate(sys.argv[:-1]) if a==flag]
def value(flag):
    return values(flag)[-1]
with (root/"successor-starts").open("a+") as handle:
    fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
    handle.write(json.dumps({"argv":sys.argv[1:],"brief":Path(value("--brief")).read_text()})+"\n")
    handle.flush()
    os.fsync(handle.fileno())
record=Path(value("--record"))
with record.open("a") as handle:
    for kind in ("lane-open","lane-spawned"):
        handle.write(json.dumps({"event":kind,"run":value("--run"),"lane":value("--lane"),
            "pid":os.getpid(),"wrapper_pid":os.getpid(),"grants":values("--grant"),
            "writes":values("--write"),"effort":value("--effort")})+"\n")
    handle.flush()
    os.fsync(handle.fileno())
print("fixture successor started",flush=True)
'''

CHAIN_RECEIVER = r'''
import fcntl,json,os,subprocess,sys
from pathlib import Path
root=Path(os.environ["A3_FIXTURE"])
arguments=sys.argv[1:]
def value(flag):
    return arguments[arguments.index(flag)+1]
with (root/"successor-starts").open("a+") as handle:
    fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
    handle.seek(0)
    number=sum(bool(line.strip()) for line in handle)+1
    handle.write(json.dumps({"argv":arguments,"brief":Path(value("--brief")).read_text(),
                            "requested_model":value("--model"),"start":number})+"\n")
    handle.flush()
    os.fsync(handle.fileno())
if number > 1:
    # Bound the regression: count the forbidden start, without running a third provider.
    print("fixture repeated successor boundary; no third provider")
    raise SystemExit(0)
family="codex" if value("--model")=="gpt-6-astra" else "claude"
scenario=root/"second-scenario.json"
env=dict(os.environ,A3_FAMILY=family,A3_SCENARIO=str(scenario))
carried=[argument for argument in arguments if argument not in ("--detach","--no-wait")]
wrapper=Path(os.environ["A3_WRAPPERS"])/("codex-lane.py" if family=="codex" else "lane.py")
command=[sys.executable,"-B",str(root/"bootstrap.py"),str(wrapper),"spawn"]+carried
if family=="claude":
    command += ["--home",str(root/"lane-home"),"--projects-root",str(root/"projects"),"--no-core"]
else:
    command += ["--routing",str(root/"routing.json")]
# Codex has no native alias probe; only that family uses the typed observation seam.
if family=="codex" and os.environ.get("A3_SECOND_TRIGGER")=="fallback":
    env["A3_CONFIRMED_FALLBACK"]="1"
result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=30)
(root/"second-public-result.json").write_text(json.dumps(
    {"command":command,"returncode":result.returncode,"stdout":result.stdout,"stderr":result.stderr}))
print(result.stdout,end="")
print(result.stderr,end="",file=sys.stderr)
raise SystemExit(result.returncode)
'''


BOOTSTRAP = r'''
import importlib.util,json,os,sys
sys.dont_write_bytecode=True
path=sys.argv[1]
sys.path.insert(0,os.path.dirname(path))
spec=importlib.util.spec_from_file_location("fixture_wrapper",path)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)
shared=module.lane if hasattr(module,"lane") else module.a3_shared() if hasattr(module,"a3_shared") else module
if (os.environ.get("A3_CONFIRMED_FALLBACK") or os.environ.get("A3_FALLBACK_VERDICT")) and hasattr(shared,"A3Owner"):
    native_finish=shared.A3Owner.finish
    def confirmed_finish(self,close,*args,**kwargs):
        verdict=os.environ.get("A3_FALLBACK_VERDICT","fallback")
        close=dict(close,fallback={"detected":verdict!="stale-map","verdict":verdict,
                                  "source":"fixture supplied model observation"})
        return native_finish(self,close,*args,**kwargs)
    shared.A3Owner.finish=confirmed_finish
if os.environ.get("A3_FAIL_LOCK"):
    import errno
    def failed_lock(*args,**kwargs):
        raise OSError(errno.ENOLCK,"fixture lock unavailable")
    shared.fcntl.flock=failed_lock
target=os.environ.get("A3_BARRIER_NAME")
if target and hasattr(shared,"a3_barrier"):
    visited=set()
    def barrier(name,journal):
        if name=="native-evidence" and journal.get("evidence",{}).get("settled") and "settled-evidence" in target.split(","):
            name="settled-evidence"
        if name in target.split(",") and name not in visited:
            visited.add(name)
            os.write(int(os.environ["A3_ARRIVAL_FD"]),(json.dumps({"barrier":name,"pass_id":journal["pass_id"]})+"\n").encode())
            release=os.read(int(os.environ["A3_RELEASE_FD"]),1)
            if release==b"E":
                raise OSError("planted infrastructure failure after " + name)
            if not release:
                raise RuntimeError("fixture controller closed its release pipe")
    shared._A3_BARRIER=barrier
    if "post-launch-before-record" in target.split(","):
        original_child=shared.A3Owner.record_child
        def child_before_record(self,process):
            # Only the controller records this identity. The production owner must already
            # hold its Popen handle before child bookkeeping can fail.
            with open(os.path.join(os.environ["A3_FIXTURE"],"unrecorded-child.json"),"w") as handle:
                json.dump(shared.a3_process_identity(process.pid),handle)
            barrier("post-launch-before-record",self.journal)
            return original_child(self,process)
        shared.A3Owner.record_child=child_before_record
    if target in ("receipt-before","receipt-after"):
        original_append=shared._append_record_unlocked
        def receipt_append(record,row,*args,**kwargs):
            receipt=row.get("notice_receipt")
            context={"pass_id":(row.get("notice_payload") or {}).get("pass_id")}
            if receipt:barrier("receipt-before",context)
            result=original_append(record,row,*args,**kwargs)
            if receipt:barrier("receipt-after",context)
            return result
        shared._append_record_unlocked=receipt_append
sys.argv=[path]+sys.argv[2:]
raise SystemExit(module.main())
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rows(path):
    if not path.exists():
        return []
    answer = []
    for line in path.read_text().splitlines():
        try:
            answer.append(json.loads(line))
        except ValueError:
            answer.append({"damaged": line})
    return answer


class Fixture:
    def __init__(self, wrappers, root):
        self.wrappers = Path(wrappers).resolve()
        self.root = Path(subprocess.check_output(
            [shutil.which("mktemp"), "-d", str(Path(root) / "a3.XXXXXX")], text=True).strip())
        self.history = []
        self.processes = []
        for path in ("bin", "work", "store/spawn-records", "projects", "lane-home",
                     "user/.codex", "vault/.claude/agents", "progress"):
            (self.root / path).mkdir(parents=True, exist_ok=True)
        self.store = self.root / "store"
        self.record = self.store / "spawn-records" / "fixture.jsonl"
        self.brief = self.root / "brief.md"
        self.brief.write_text("  TASK-INPUT-CONTROL\nMaintain the fixture only.\n  ")
        definition = "---\nname: fixture\ndescription: fixture\ntools: Read, Bash\n---\nFixture role.\n"
        (self.root / "vault/.claude/agents/fixture.md").write_text(definition)
        (self.root / "vault/CUSTOMISATION.md").write_text(
            "## Settings\n- **throttle**: default\n- **delegation**: single\n")
        (self.root / "lane-home/lane-settings.json").write_text(
            json.dumps({"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
                {"type": "command", "command": "true"}]}]}}))
        (self.root / "lane-home/lane-fence.py").write_text("# fixture only\n")
        route = {"schema": 2, "order": {"model": ["sonnet"], "effort": ["max"]},
                 "classes": {"fixture": {"model": {"options": ["sonnet"], "default": "sonnet"},
                 "effort": {"options": ["max"], "default": "max"}, "grants": {"default": []},
                 "writes": [], "tools": ["Read", "Bash"], "skills": {"default": []},
                 "mcp": {"default": []}}}}
        self.routing = self.root / "routing.json"
        self.routing.write_text(json.dumps(route))
        for name in ("claude", "codex"):
            path = self.root / "bin" / name
            path.write_text("#!" + sys.executable + "\n" + PROVIDER)
            path.chmod(0o755)
        self.successor = self.root / "successor.py"
        self.successor.write_text(SUCCESSOR)
        self.bootstrap = self.root / "bootstrap.py"
        self.bootstrap.write_text(BOOTSTRAP)
        self.env = dict(os.environ, PATH=str(self.root / "bin") + os.pathsep + "/usr/bin:/bin",
                        HOME=str(self.root / "user"), CODEX_HOME=str(self.root / "user/.codex"),
                        LLM_WIKI_STORE=str(self.store), CLAUDE_PROJECT_DIR=str(self.root / "vault"),
                        LLM_WIKI_LANE_HOME=str(self.root / "lane-home"),
                        LLM_WIKI_PROGRESS_DIR=str(self.root / "progress"), A3_FIXTURE=str(self.root),
                        AIMYTH_SWAP_CMD=shlex.join([sys.executable, str(self.successor)]),
                        AIMYTH_CAFFEINATE="off", AIMYTH_VIEWER="none", PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("CLAUDE_CONFIG_DIR", None)
        self.supported = "A3_SCHEMA" in (self.wrappers / "lane.py").read_text()

    def cleanup(self):
        for proc in self.processes:
            if proc.poll() is None:
                proc.kill()
            with contextlib.suppress(Exception):
                proc.wait(timeout=10)
            for attribute in ("a3_arrival", "a3_release"):
                descriptor = getattr(proc, attribute, None)
                if descriptor is not None:
                    with contextlib.suppress(OSError):
                        os.close(descriptor)
        # Fixture model groups can survive an intentionally killed wrapper. Their identity
        # comes only from fixture journals/records, and every such process is reaped here.
        module = self.module()
        if self.supported:
            for journal in self.snapshot()["journals"]:
                child = journal.get("child")
                if child and module.a3_process_identity(child["pid"]) == child:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(child["pid"], signal.SIGKILL)
                owner=journal.get("owner")
                if owner and owner.get("pid") != os.getpid() and module.a3_process_identity(owner["pid"]) == owner:
                    with contextlib.suppress(ProcessLookupError):
                        os.kill(owner["pid"],signal.SIGKILL)
        marker=self.root/"unrecorded-child.json"
        if marker.exists():
            identity=json.loads(marker.read_text())
            if identity and module.a3_process_identity(identity["pid"])==identity:
                with contextlib.suppress(ProcessLookupError):os.killpg(identity["pid"],signal.SIGKILL)
        shutil.rmtree(self.root)

    def module(self):
        spec = importlib.util.spec_from_file_location("fixture_lane_reader", self.wrappers / "lane.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def wrapper(self, family):
        return self.wrappers / ("lane.py" if family == "claude" else "codex-lane.py")

    def command(self, family, operation="spawn", extra=()):
        command = [sys.executable, "-B", str(self.wrapper(family)), operation, "--run", "fixture",
                   "--lane", "case", "--record", str(self.record)]
        if operation == "spawn":
            command += ["--class", "fixture", "--brief", str(self.brief),
                        "--reason", "(a) fixture", "--choice-reason", "fixture configured family",
                        "--effort", "max", "--delegation", "single", "--delegation-src", "head",
                        "--viewer", "none", "--deadline-s", "20", "--silence-s", "0"]
            if family == "claude":
                command += ["--expect-usd", "1", "--home", str(self.root / "lane-home"),
                            "--routing", str(self.routing), "--projects-root", str(self.root / "projects"),
                            "--grant", str(self.root / "work"), "--grants-only", "--no-core"]
            else:
                command += ["--codex", str(self.root / "bin/codex"), "--cwd", str(self.root / "work")]
                if self.supported:
                    command += ["--expect-usd", "1", "--grant", str(self.root / "work"),
                                "--routing", str(self.routing)]
        return command + list(extra)

    def scenario(self, family, events, exit_code=0, wait=False, result=None):
        path = self.root / "scenario.json"
        data = {"events": events, "exit": exit_code, "wait": wait}
        if result is not None:
            data["result"] = result
        path.write_text(json.dumps(data))
        self.env.update(A3_SCENARIO=str(path), A3_FAMILY=family)
        return data

    def run(self, command, timeout=30):
        result = subprocess.run(command, env=self.env, capture_output=True, text=True, timeout=timeout)
        captured = {"command": command, "returncode": result.returncode,
                    "stdout": result.stdout, "stderr": result.stderr}
        self.history.append(captured)
        return result

    def snapshot(self):
        journals = []
        directory = Path(str(self.record) + ".a3")
        if directory.exists():
            for path in sorted(directory.glob("*.json")):
                try:
                    journals.append(json.loads(path.read_text()))
                except ValueError:
                    journals.append({"damaged_journal": path.read_text()})
        record = rows(self.record)
        reports = {}
        for path in (self.store / "spawn-records").glob("*report*.md"):
            if path.is_file():
                reports[path.name] = base64.b64encode(path.read_bytes()).decode()
        starts = rows(self.root / "successor-starts")
        input_bytes = {}
        for journal in journals:
            provenance = journal.get("input") or {}
            captured = {}
            for key in ("source_copy", "snapshot"):
                path = provenance.get(key)
                if path and Path(path).is_file():
                    captured[key] = base64.b64encode(Path(path).read_bytes()).decode()
            input_bytes[journal.get("pass_id", "damaged")] = captured
        inputs = {family: (self.root / (family + "-input")).read_text()
                  for family in ("claude", "codex") if (self.root / (family + "-input")).exists()}
        return {"commands": self.history, "record": record, "journals": journals, "model_inputs": inputs,
                "input": json.loads((self.root / "scenario.json").read_text())
                         if (self.root / "scenario.json").exists() else None,
                "immutable_input_bytes_base64": input_bytes,
                "report_bytes_base64": reports, "successor_start_count": len(starts),
                "successor_starts": starts,
                "notice_identities": [(n["notice_id"], n["version"], n["payload_sha256"])
                                     for j in journals for n in j.get("notices", [])]}

    def barrier(self, family, name, extra=()):
        if not self.supported:
            raise RuntimeError("unsupported-interface: native A3 barrier")
        arrival_read, arrival_write = os.pipe()
        release_read, release_write = os.pipe()
        env = dict(self.env, A3_BARRIER_NAME=name, A3_ARRIVAL_FD=str(arrival_write),
                   A3_RELEASE_FD=str(release_read))
        original = self.command(family, extra=extra)
        command = [sys.executable, "-B", str(self.bootstrap), original[2]] + original[3:]
        proc = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, pass_fds=(arrival_write, release_read))
        self.processes.append(proc)
        proc.a3_arrival, proc.a3_release = arrival_read, release_write
        os.close(arrival_write)
        os.close(release_read)
        if not select.select([arrival_read], [], [], 30)[0]:
            proc.kill()
            out, err = proc.communicate()
            raise RuntimeError("PROBE FAILED: native barrier did not arrive: " + out + err)
        arrived = json.loads(os.read(arrival_read, 65536))
        return proc, release_write, arrived

    def next_barrier(self, proc, release):
        os.write(release, b"1")
        if not select.select([proc.a3_arrival], [], [], 30)[0]:
            raise RuntimeError("PROBE FAILED: second native barrier did not arrive")
        return json.loads(os.read(proc.a3_arrival, 65536))

    def finish(self, proc, release):
        os.write(release, b"1")
        os.close(release)
        os.close(proc.a3_arrival)
        proc.a3_arrival = proc.a3_release = None
        out, err = proc.communicate(timeout=30)
        result = {"command": proc.args, "returncode": proc.returncode, "stdout": out, "stderr": err}
        self.history.append(result)
        return result


def claude_message(identifier, stop, text):
    return {"type": "assistant", "message": {"id": identifier, "model": "fixture-model",
            "stop_reason": stop, "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": 1, "output_tokens": 1}}}


def codex_message(identifier, text, refused=False):
    return {"type": "item.completed", "item": {"id": identifier,
            "type": "refusal" if refused else "agent_message", "text": text}}


def events_for(family, shape):
    if family == "claude":
        refused = claude_message("refusal", "refusal", "PROHIBITED-OUTPUT-CONTROL")
        complete = claude_message("completion", "end_turn", "WHOLE-REPORT-CONTROL")
        work = claude_message("work", "tool_use", "FURTHER-WORK")
        return {"terminal": [complete, refused], "continued": [refused, complete],
                "clean": [complete], "further": [refused, complete, work],
                "result-only": [complete, refused]}[shape]
    refused = codex_message("refusal", "PROHIBITED-OUTPUT-CONTROL", True)
    complete = {"type": "turn.completed", "usage": {"input_tokens": 1, "cached_input_tokens": 0,
                                                     "output_tokens": 1}}
    message = codex_message("completion", "WHOLE-REPORT-CONTROL")
    start = {"type": "turn.started"}
    return {"terminal": [start, message, complete, start, refused],
            "continued": [start, refused, complete],
            "clean": [start, message, complete],
            "further": [start, refused, complete, start],
            "result-only": [start, message, complete, start, refused]}[shape]


class Suite:
    def __init__(self, args):
        self.args, self.passed, self.failed = args, 0, 0
        self.controls = {}

    def check(self, group, name, condition, evidence=None):
        if condition:
            self.passed += 1
        else:
            self.failed += 1
        print(("OK " if condition else "BAD ") + group + " " + name, flush=True)
        if evidence is not None:
            print("CASE " + json.dumps({"group": group, "case": name, "passed": bool(condition),
                                       "evidence": evidence}, sort_keys=True), flush=True)

    def selected(self, group):
        return not self.args.only or group in self.args.only

    def positive(self, family):
        fixture = Fixture(self.args.wrappers, self.args.fixture_root)
        try:
            command = [sys.executable, str(fixture.successor), "--run", "fixture", "--lane", "control",
                       "--brief", str(fixture.brief), "--record", str(fixture.record),
                       "--effort", "max", "--grant", str(fixture.root / "work")]
            result = fixture.run(command)
            snapshot = fixture.snapshot()
            self.controls[family] = result.returncode == 0 and snapshot["successor_start_count"] == 1
            self.check("CONTROL+", family + " actual fixture successor", self.controls[family], snapshot)
        finally:
            fixture.cleanup()

    def basic(self, family):
        matrix = [("A02", "terminal"), ("A03", "continued"), ("A03", "clean"),
                  ("A06", "terminal"), ("A07", "result-only"), ("A08", "further")]
        for group, shape in matrix:
            if not self.selected(group) or group == "A07" and family != "claude":
                continue
            fixture = Fixture(self.args.wrappers, self.args.fixture_root)
            try:
                input_value = fixture.scenario(family, events_for(family, shape))
                result = fixture.run(fixture.command(family))
                snapshot = fixture.snapshot()
                snapshot["input"] = input_value
                closes = [r for r in snapshot["record"] if r.get("event") == "lane-closed"
                          and r.get("lane") == "case"]
                close = closes[-1] if closes else {}
                expected = "completed" if shape == "clean" else "refusal-continued" if shape == "continued" else "refusal"
                expected_starts = int(expected == "refusal")
                valid = (len(closes) == 1 and close.get("exit_class") == expected
                         and result.returncode == (0 if shape == "clean" else 3)
                         and snapshot["successor_start_count"] == expected_starts
                         and bool(close.get("pass_id")) and bool(snapshot["journals"]))
                if expected_starts:
                    valid = valid and all("PROHIBITED-OUTPUT-CONTROL" not in start["brief"]
                                          and "TASK-INPUT-CONTROL" in start["brief"]
                                          for start in snapshot["successor_starts"])
                else:
                    valid = valid and self.controls.get(family, False)
                self.check(group, family + " " + shape, valid, snapshot)
            except Exception as exc:
                self.check(group, family + " " + shape, False,
                           {"exception": repr(exc), **fixture.snapshot()})
            finally:
                fixture.cleanup()

    def ordinary_paths(self, family):
        if not (self.selected("A02") or self.selected("A10")):
            return
        for operation, detached in (("spawn", True), ("resume", False), ("resume", True)):
            fixture = Fixture(self.args.wrappers, self.args.fixture_root)
            try:
                if operation == "resume":
                    fixture.scenario(family, events_for(family, "clean"))
                    fixture.run(fixture.command(family))
                    fixture.brief = fixture.root / "follow.md"
                    fixture.brief.write_text("CURRENT-RESUME-INPUT\nContinue the fixture task.\n")
                fixture.scenario(family, events_for(family, "terminal"))
                extra = ["--detach"] if detached else []
                if operation == "resume":
                    extra += ["--brief", str(fixture.brief)]
                    if family == "claude":
                        extra += ["--home", str(fixture.root / "lane-home"),
                                  "--projects-root", str(fixture.root / "projects")]
                result = fixture.run(fixture.command(family, operation, extra), timeout=60)
                snapshot = fixture.snapshot()
                journals = [j for j in snapshot["journals"] if j.get("kind") != "beat"]
                latest = max(journals, key=lambda j: j["ordinal"]) if journals else {}
                source = fixture.brief.read_bytes()
                valid = (result.returncode == 3 and snapshot["successor_start_count"] == 1
                         and latest.get("close", {}).get("exit_class") == "refusal"
                         and latest.get("input", {}).get("source_sha256") == sha(source))
                if operation == "resume":
                    valid = valid and all("CURRENT-RESUME-INPUT" in start["brief"]
                                          and "TASK-INPUT-CONTROL" not in start["brief"]
                                          for start in snapshot["successor_starts"])
                self.check("A02" if operation == "spawn" else "A10",
                           family + " " + operation + (" detached" if detached else " foreground"),
                           valid, snapshot)
            except Exception as exc:
                self.check("A02", family + " " + operation + " path", False,
                           {"exception": repr(exc), **fixture.snapshot()})
            finally:
                fixture.cleanup()

    def guarded(self, family):
        for group, cause, flags in (
                ("A04", "stall", ["--silence-s", "0.05"]),
                ("A05", "deadline", ["--deadline-s", "1"])):
            if not self.selected(group):
                continue
            for shape in ("terminal", "clean"):
                fixture = Fixture(self.args.wrappers, self.args.fixture_root)
                try:
                    fixture.scenario(family, events_for(family, shape), wait=True)
                    result = fixture.run(fixture.command(family, extra=flags), timeout=30)
                    watch = fixture.run(fixture.command(family, "watch",
                                        ["--appear-s", "0", "--poll-s", "0.01"]))
                    snapshot = fixture.snapshot()
                    closes = [row for row in snapshot["record"] if row.get("event") == "lane-closed"
                              and row.get("lane") == "case"]
                    close = closes[-1] if closes else {}
                    refused = shape == "terminal"
                    expected_code = 3 if refused or cause == "deadline" else 5
                    valid = (result.returncode == expected_code and len(closes) == 1
                             and close.get("exit_class") == ("refusal" if refused else cause)
                             and close.get("stop_cause") == cause
                             and snapshot["successor_start_count"] == int(refused)
                             and self.controls.get(family))
                    if refused:
                        valid = valid and watch.returncode == 3 and close.get("refusal_count") == 1
                    self.check(group, family + " " + cause + " " + shape, valid, snapshot)
                except Exception as exc:
                    self.check(group, family + " " + cause + " " + shape, False,
                               {"exception": repr(exc), **fixture.snapshot()})
                finally:
                    fixture.cleanup()

    def input_holds(self, family):
        if not self.selected("A26"):
            return
        for mode in ("no-swap", "missing-snapshot", "corrupt-snapshot", "source-edited", "overlap"):
            fixture = Fixture(self.args.wrappers, self.args.fixture_root)
            try:
                fixture.scenario(family, events_for(family, "terminal"))
                if mode == "overlap":
                    fixture.brief.write_text("PROHIBITED-OUTPUT-CONTROL\n")
                if mode == "no-swap":
                    result = fixture.run(fixture.command(family, extra=["--no-swap"]))
                else:
                    proc, release, arrival = fixture.barrier(family, "published-start")
                    journal = fixture.snapshot()["journals"][0]
                    snapshot_path = Path(journal["input"]["snapshot"])
                    if mode == "missing-snapshot":
                        snapshot_path.unlink()
                    elif mode == "corrupt-snapshot":
                        snapshot_path.write_text("INTEGRITY-PLANT")
                    elif mode == "source-edited":
                        fixture.brief.write_text("MUTATED-ORIGINAL-MUST-NOT-TRAVEL")
                    result = fixture.finish(proc, release)
                captured = fixture.snapshot()
                journal = captured["journals"][0] if captured["journals"] else {}
                move = mode == "source-edited"
                valid = (captured["successor_start_count"] == int(move) and self.controls.get(family)
                         and journal.get("close", {}).get("refusal_count") == 1)
                if move:
                    valid = valid and "TASK-INPUT-CONTROL" in captured["successor_starts"][0]["brief"] \
                        and "MUTATED-ORIGINAL" not in captured["successor_starts"][0]["brief"]
                else:
                    valid = valid and journal.get("disposition", {}).get("phase") in ("resolved", "awaiting-input") \
                        and bool(journal.get("disposition", {}).get("reason")) and bool(journal.get("notices"))
                self.check("A26", family + " " + mode, valid, captured)
            except Exception as exc:
                self.check("A26", family + " " + mode, False,
                           {"exception": repr(exc), **fixture.snapshot()})
            finally:
                fixture.cleanup()

    def native_observers(self, family):
        for group, barrier in (("A11", "published-start"), ("A16", "native-evidence"),
                               ("A16", "prepared-outcome"), ("A21", "committed-journal")):
            if not self.selected(group):
                continue
            fixture = Fixture(self.args.wrappers, self.args.fixture_root)
            try:
                fixture.scenario(family, events_for(family, "terminal"))
                proc, release, arrival = fixture.barrier(family, barrier)
                before = fixture.snapshot()
                watch = fixture.run(fixture.command(family, "watch",
                    ("--appear-s", "0", "--poll-s", "0.01", "--max-wait-s", "0.05", "--format", "json")))
                during = fixture.snapshot()
                if barrier == "native-evidence":
                    evidence = during["journals"][0]["boundary"]["path"]
                    Path(evidence).unlink()
                result = fixture.finish(proc, release)
                after = fixture.snapshot()
                source_closes = [row for row in after["record"] if row.get("event") == "lane-closed"
                                 and row.get("lane") == "case"]
                expected_watch = 3 if barrier == "committed-journal" else 8
                valid = (watch.returncode == expected_watch and result["returncode"] == 3
                         and len(source_closes) == 1 and source_closes[0].get("refusal_count") == 1
                         and during["successor_start_count"] == before["successor_start_count"]
                         and after["successor_start_count"] == 1)
                self.check(group, family + " native observer at " + barrier, valid,
                           {"arrival": arrival, "before": before, "during": during, "after": after})
            except Exception as exc:
                self.check(group, family + " native observer at " + barrier, False,
                           {"exception": repr(exc), **fixture.snapshot()})
            finally:
                fixture.cleanup()

    def orphan(self, family):
        group = "A12" if family == "claude" else "A13"
        if not self.selected(group):
            return
        for shape, operation in ((shape, operation) for shape in ("clean", "terminal", "continued")
                                 for operation in (("watch", "wait") if family == "codex" else ("watch",))):
            fixture = Fixture(self.args.wrappers, self.args.fixture_root)
            try:
                fixture.scenario(family, events_for(family, shape), wait=True)
                command = fixture.command(family)
                proc = subprocess.Popen(command, env=fixture.env, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True)
                fixture.processes.append(proc)
                deadline = time.monotonic() + 30
                ready = fixture.root / "provider-ready"
                while not ready.exists() and time.monotonic() < deadline:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.01)
                if not ready.exists():
                    raise RuntimeError("PROBE FAILED: fixture provider did not acknowledge readiness")
                child_pid = int(ready.read_text())
                spawned = [row for row in rows(fixture.record)
                           if row.get("event") in ("lane-spawned", "lane-respawned")]
                if not spawned or spawned[-1].get("pid") != child_pid:
                    raise RuntimeError("PROBE FAILED: fixture child identity did not match its start")
                proc.kill()
                out, err = proc.communicate(timeout=10)
                os.killpg(child_pid, signal.SIGKILL)
                while fixture.module().pid_alive(child_pid) and time.monotonic() < deadline:
                    time.sleep(0.01)
                if fixture.module().pid_alive(child_pid):
                    raise RuntimeError("PROBE FAILED: fixture child death was not observed")
                fixture.history.append({"command": command, "returncode": proc.returncode,
                                        "stdout": out, "stderr": err})
                before = fixture.snapshot()
                command = fixture.command(family, operation,
                    ["--appear-s", "0", "--poll-s", "0.01", "--format", "json"]
                    + (["--max-wait-s", "0"] if operation == "watch" else []))
                first = fixture.run(command)
                second = fixture.run(command)
                after = fixture.snapshot()
                observations = [row for row in after["record"] if row.get("event") == "orphan-observed"]
                closes = [row for row in after["record"] if row.get("event") == "lane-closed"]
                valid = (first.returncode == second.returncode == 3 and len(observations) == 1 and not closes
                         and before["report_bytes_base64"] == after["report_bytes_base64"]
                         and after["successor_start_count"] == 0 and self.controls.get(family)
                         and len({identity[0] for identity in after["notice_identities"]}) == 1
                         and "--pass" in first.stdout and "recover" in first.stdout)
                self.check(group, family + " orphan " + shape + " through " + operation, valid, {"before": before, "after": after})
            except Exception as exc:
                self.check(group, family + " orphan " + shape + " through " + operation, False,
                           {"exception": repr(exc), **fixture.snapshot()})
            finally:
                fixture.cleanup()

    def decisions(self, family):
        if not self.selected("A15"):
            return
        for choice in ("move", "hold", "recovered"):
            fixture = Fixture(self.args.wrappers, self.args.fixture_root)
            try:
                fixture.scenario(family, events_for(family, "continued"))
                fixture.run(fixture.command(family))
                before = fixture.snapshot()
                notice = before["journals"][0]["notices"][-1]
                inspection = shlex.split(notice["payload"]["recover"])
                no_decision = fixture.run(inspection + ["--format", "json"])
                decision = inspection + ["--decision", choice, "--reason", "fixture head judgement",
                                         "--format", "json"]
                first, second = fixture.run(decision), fixture.run(decision)
                after = fixture.snapshot()
                old = [row for row in before["record"] if row.get("event") == "lane-closed"]
                new = [row for row in after["record"] if row.get("event") == "lane-closed"]
                resolved = [row for row in after["record"] if row.get("event") == "disposition-resolved"]
                valid = (no_decision.returncode == first.returncode == second.returncode == 3
                         and old == new and len(resolved) == 1
                         and after["successor_start_count"] == int(choice == "move")
                         and self.controls.get(family)
                         and set(json.loads(no_decision.stdout).get("allowed_decisions",[])) == {"move","hold","recovered"}
                         and after["journals"][0]["disposition"]["phase"] == "resolved")
                self.check("A15", family + " printed command " + choice, valid,
                           {"before": before, "after": after})
            except Exception as exc:
                self.check("A15", family + " printed command " + choice, False,
                           {"exception": repr(exc), **fixture.snapshot()})
            finally:
                fixture.cleanup()

    def notices(self, family):
        if not self.selected("A23"):
            return
        fixture = Fixture(self.args.wrappers, self.args.fixture_root)
        try:
            fixture.scenario(family, events_for(family, "continued"))
            fixture.run(fixture.command(family))
            handsoff = [sys.executable, "-B", str(fixture.wrappers / "handsoff.py")]
            common = ["--run", "fixture", "--record", str(fixture.record)]
            drain = handsoff + ["notices"] + common + ["--pending", "--format", "json"]
            initial = fixture.run(drain)
            initial_notices = json.loads(initial.stdout)["pending"]
            notice = initial_notices[-1]
            triple = ["--notice-id", notice["notice_id"], "--notice-version", str(notice["version"]),
                      "--notice-sha256", notice["payload_sha256"]]
            premature = fixture.run(handsoff + ["notices"] + common + ["--ack"] + triple
                                    + ["--route", "hands-off", "--receipt", "record:absent"])
            for previous in initial_notices[:-1]:
                previous_triple = ["--notice-id", previous["notice_id"], "--notice-version",
                                   str(previous["version"]), "--notice-sha256", previous["payload_sha256"]]
                received = fixture.run(handsoff + ["ledger"] + common +
                                       ["--observation", "fixture head received earlier version"] + previous_triple)
                previous_locator = received.stdout.split("record:", 1)[1].split()[0]
                fixture.run(handsoff + ["notices"] + common + ["--ack"] + previous_triple
                            + ["--route", "hands-off", "--receipt", "record:" + previous_locator])
            ledger = handsoff + ["ledger"] + common + ["--observation", "fixture head received notice"] + triple
            receipt = fixture.run(ledger)
            fixture.run(ledger)
            locator = receipt.stdout.split("record:", 1)[1].split()[0]
            ack = fixture.run(handsoff + ["notices"] + common + ["--ack"] + triple
                              + ["--route", "hands-off", "--receipt", "record:" + locator])
            clean = fixture.run(drain)
            inspection = shlex.split(notice["payload"]["recover"])
            fixture.run(inspection + ["--decision", "hold", "--reason", "fixture final decision"])
            stale = fixture.run(handsoff + ["notices"] + common + ["--ack"] + triple
                                + ["--route", "hands-off", "--receipt", "record:" + locator])
            update = fixture.run(drain)
            after = fixture.snapshot()
            observations = [row for row in after["record"] if row.get("notice_receipt")]
            valid = (initial.returncode == 0 and premature.returncode == 2 and receipt.returncode == 0
                     and ack.returncode == 0 and json.loads(clean.stdout)["count"] == 0
                     and stale.returncode == 0 and json.loads(update.stdout)["count"] == 1
                     and json.loads(update.stdout)["pending"][0]["version"] == notice["version"] + 1
                     and len(observations) == len(initial_notices) and after["successor_start_count"] == 0
                     and self.controls.get(family))
            self.check("A23", family + " closed pass versioned receipt and replay", valid, after)
        except Exception as exc:
            self.check("A23", family + " closed pass versioned receipt and replay", False,
                       {"exception": repr(exc), **fixture.snapshot()})
        finally:
            fixture.cleanup()

    def beats(self, family):
        if not self.selected("A25"):
            return
        for predecessor in ("clean", "continued"):
            fixture = Fixture(self.args.wrappers, self.args.fixture_root)
            try:
                fixture.scenario(family, events_for(family, predecessor))
                fixture.run(fixture.command(family))
                before = fixture.snapshot()
                fixture.scenario(family, events_for(family, "terminal"))
                extra = ["--beat"]
                if family == "claude":
                    extra += ["--home", str(fixture.root / "lane-home"),
                              "--projects-root", str(fixture.root / "projects")]
                result = fixture.run(fixture.command(family, "resume", extra))
                after = fixture.snapshot()
                old_closes = [row for row in before["record"] if row.get("event") == "lane-closed"]
                new_closes = [row for row in after["record"] if row.get("event") == "lane-closed"]
                beats = [row for row in after["record"] if row.get("event") == "hold-beat"]
                valid = (old_closes == new_closes and before["report_bytes_base64"] ==
                         after["report_bytes_base64"] and after["successor_start_count"] == 0
                         and self.controls.get(family))
                if predecessor == "continued":
                    valid = valid and result.returncode == 2 and not beats
                else:
                    valid = valid and result.returncode == 3 and len(beats) == 1 \
                        and beats[0].get("refusal_count") == 1 and beats[0].get("notice")
                self.check("A25", family + " beat after " + predecessor, valid,
                           {"before": before, "after": after})
            except Exception as exc:
                self.check("A25", family + " beat after " + predecessor, False,
                           {"exception": repr(exc), **fixture.snapshot()})
            finally:
                fixture.cleanup()

    def exercise(self, group, name, callback):
        if not self.selected(group):
            return
        fixture = Fixture(self.args.wrappers, self.args.fixture_root)
        try:
            verdict, detail = callback(fixture)
            self.check(group, name, verdict, {"detail": detail, **fixture.snapshot()})
        except Exception as exc:
            self.check(group, name, False, {"exception": repr(exc), **fixture.snapshot()})
        finally:
            fixture.cleanup()

    def extra_public(self, family):
        if family == "claude":
            for cause, subtype in (("budget", "error_max_budget_usd"),
                                   ("max-turns", "error_max_turns")):
                for refused in (False, True):
                    def budget(f, cause=cause, subtype=subtype, refused=refused):
                        f.scenario(family, events_for(family, "terminal" if refused else "clean"),
                            result={"type":"result", "subtype":subtype, "is_error":True,
                                    "result":"fixture guard", "num_turns":1})
                        r = f.run(f.command(family))
                        j = f.snapshot()["journals"][0]
                        return (r.returncode == 3 and j["close"]["exit_class"] ==
                                ("refusal" if refused else cause)
                                and j["stop_cause"] == cause
                                and f.snapshot()["successor_start_count"] == int(refused), j["close"])
                    self.exercise("A05", family + " " + cause + " refused=" + str(refused), budget)
        for variant in ("quoted", "sandbox", "unknown-policy", "same-turn", "failed-final-turn"):
            def policy(f, variant=variant):
                if variant == "same-turn":
                    events = events_for(family, "continued")
                elif variant == "failed-final-turn":
                    events = events_for(family, "continued") + (
                        [{"type":"turn.failed", "error":{"message":"fixture final turn failed"}}]
                        if family == "codex" else [claude_message("later", "tool_use", "later work")])
                else:
                    text = {"quoted":"The document quotes: I cannot help with that request.",
                            "sandbox":"sandbox denial: Operation not permitted",
                            "unknown-policy":"unfamiliar policy wording fixture"}[variant]
                    events = ([claude_message("control", "end_turn", text)] if family == "claude" else
                              [codex_message("control", text), {"type":"turn.completed"}])
                f.scenario(family, events)
                r = f.run(f.command(family))
                j = f.snapshot()["journals"][0]
                if variant == "failed-final-turn":
                    valid = r.returncode == 3 and j["close"]["exit_class"] == "refusal" and f.snapshot()["successor_start_count"] == 1
                elif variant == "same-turn":
                    valid = (r.returncode == 3 and j["disposition"]["phase"] == "awaiting-head"
                             and f.snapshot()["successor_start_count"] == 0
                             and j["disposition"].get("decision") != "recovered")
                else:
                    valid = (r.returncode == 0 and j["close"]["refusal_count"] == 0
                             and not j["notices"] and f.snapshot()["successor_start_count"] == 0)
                return valid and self.controls[family], j["close"]
            self.exercise("A08" if variant == "failed-final-turn" else "A09", family + " " + variant, policy)

    def provenance(self, family):
        def inspect(f):
            f.scenario(family, events_for(family, "terminal"))
            r = f.run(f.command(family))
            snap = f.snapshot()
            j = snap["journals"][0]
            p, d = j["input"], j["disposition"]
            source, task = Path(p["source_copy"]).read_bytes(), Path(p["snapshot"]).read_bytes()
            delivered = snap["model_inputs"][family]
            arguments = snap["successor_starts"][0]["argv"]
            def vals(flag):
                return [arguments[n+1] for n, a in enumerate(arguments[:-1]) if a == flag]
            valid = (r.returncode == 3 and p["source_sha256"] == sha(source)
                     and source == f.brief.read_bytes() and p["snapshot_sha256"] == sha(task)
                     and task.decode() in delivered and p["pass_id"] == j["pass_id"]
                     and d["brief_sha256"] == sha(Path(d["brief"]).read_bytes())
                     and d["source_snapshot_sha256"] == p["snapshot_sha256"]
                     and snap["successor_starts"][0]["brief"].endswith(task.decode())
                     and vals("--effort") == [j["start"]["effort"]]
                     and vals("--grant") == j["start"]["grants"]
                     and vals("--write") == j["start"]["writes"]
                     and float(vals("--expect-usd")[0]) == p["estimate"] == d["estimate"]
                     and bool(p["estimate_source"]) and bool(p["transformations"]))
            valid=valid and Path(j["report"]).read_bytes()==b"WHOLE-REPORT-CONTROL\n\nPROHIBITED-OUTPUT-CONTROL\n"
            if family == "codex":
                valid = valid and source != task and task == source.strip() + b"\n"
            return valid, {"provenance": p, "disposition": d}
        self.exercise("A02", family + " immutable provenance at successor boundary", inspect)

    def boundary_faults(self, family):
        for fault in ("known", "missing", "mismatched", "truncated", "snapshot-damaged", "source-edited"):
            def boundary(f, fault=fault):
                f.scenario(family, events_for(family, "clean"))
                f.run(f.command(family))
                f.brief = f.root / "resume-brief.md"
                f.brief.write_text("CURRENT-RESUME-INPUT\n")
                f.scenario(family, events_for(family, "terminal"))
                # Invoke the native resume through the same fixture barrier bootstrap.
                original = f.command
                f.command = lambda fam, operation="spawn", extra=(): original(fam, "resume", [
                    "--brief", str(f.brief)] + (["--home", str(f.root/"lane-home"),
                     "--projects-root", str(f.root/"projects")] if fam == "claude" else []) + list(extra))
                proc, release, arrival = f.barrier(family, "published-start")
                module = f.module()
                j = max(f.snapshot()["journals"], key=lambda j:j["ordinal"])
                if fault in ("missing", "mismatched", "truncated"):
                    if fault == "missing":
                        j["boundary"]["known"] = False
                    else:
                        j["boundary"].update(known=True, exists=True, size=1,
                            prefix_sha256=sha(b"z" if fault == "mismatched" else b""),
                            device=0, inode=0)
                        if fault == "truncated":
                            j["boundary"]["size"] = 10**6  # Set by judgement, unmeasured: an impossible fixture prefix.
                    module.a3_save_journal(j)
                elif fault == "snapshot-damaged":
                    Path(j["input"]["snapshot"]).write_text("damaged")
                elif fault == "source-edited":
                    f.brief.write_text("MUTATED-ORIGINAL-MUST-NOT-TRAVEL")
                f.finish(proc, release)
                snap = f.snapshot()
                j = max(snap["journals"], key=lambda j:j["ordinal"])
                if fault in ("known", "source-edited"):
                    valid = (snap["successor_start_count"] == 1
                             and "CURRENT-RESUME-INPUT" in snap["successor_starts"][0]["brief"]
                             and "TASK-INPUT-CONTROL" not in snap["successor_starts"][0]["brief"]
                             and "MUTATED-ORIGINAL" not in snap["successor_starts"][0]["brief"])
                else:
                    valid = (snap["successor_start_count"] == 0 and j["notices"]
                             and j["disposition"]["phase"] in ("awaiting-head", "awaiting-input"))
                    if fault != "snapshot-damaged":
                        valid = valid and "boundary unknown" in str(j["evidence"].get("uncertainty"))
                return bool(valid and self.controls[family]), {"fault":fault,"arrival":arrival}
            self.exercise("A10", family + " resume boundary " + fault, boundary)

    def lifecycle_faults(self, family):
        for fault in ("setup", "child-start-failed", "post-launch", "before-child-record", "after-refusal-capture",
                      "report-persistence-clean", "report-persistence-refusal"):
            def lifecycle(f, fault=fault):
                report_fault=fault.startswith("report-persistence-")
                f.scenario(family, events_for(family, "clean" if fault=="report-persistence-clean" else "terminal"))
                barrier = {"post-launch":"child-started","before-child-record":"post-launch-before-record",
                           "after-refusal-capture":"outcome-saved"}.get(fault,"published-start")
                if report_fault:barrier="settled-evidence"
                proc, release, arrival = f.barrier(family, barrier)
                native_outcome=f.snapshot()["journals"][0].get("outcome") or {}
                if report_fault:
                    report=Path(f.snapshot()["journals"][0]["report"])
                    if report.is_file():report.unlink()
                    report.mkdir()
                    result=f.finish(proc,release)
                elif fault == "child-start-failed":
                    (f.root/"bin"/family).unlink()
                    result = f.finish(proc, release)
                else:
                    os.write(release, b"E")
                    out, err = proc.communicate(timeout=30)
                    result = {"returncode":proc.returncode,"stdout":out,"stderr":err}
                    f.history.append(result)
                snap = f.snapshot()
                j = snap["journals"][0]
                closes = [r for r in snap["record"] if r.get("event") == "lane-closed"]
                child_started = fault in ("post-launch", "before-child-record", "after-refusal-capture") or report_fault
                valid = (result["returncode"] == 3 and len(closes) == 1
                         and j["child_started"] == child_started and j["execution"] == "closed"
                         and snap["successor_start_count"] == 0
                         and j["close"]["exit_class"] == ("evidence-incomplete" if fault=="report-persistence-clean" else
                              "refusal" if fault in ("after-refusal-capture","report-persistence-refusal") else
                              "error" if child_started else "spawn-failed" if fault == "child-start-failed" else "setup-failed"))
                if report_fault:
                    valid=valid and j["disposition"]["phase"]=="awaiting-head" and bool(j["close"].get("report_error"))
                if fault == "after-refusal-capture":
                    valid = valid and j["close"]["refusal_count"] == 1 and j["stop_cause"] == "infrastructure-failure"
                    valid = valid and bool(native_outcome.get("usage")) and j["close"].get("usage") == native_outcome["usage"]
                if child_started:
                    valid = valid and j["close"].get("process_exit") is not None and j.get("child_settled")
                return valid and self.controls[family], {"arrival":arrival,"result":result}
            self.exercise("A11", family + " " + fault, lifecycle)

    def crash_matrix(self, family):
        barriers = ("published-start", "child-started", "child-stop-request", "native-evidence", "outcome-saved", "before-seal",
                    "decision-sealed", "launch-intent", "successor-returned", "prepared-outcome",
                    "close-projection", "committed-journal", "notice-rendering")
        for barrier in barriers:
            group = "A22" if barrier in ("before-seal", "decision-sealed", "launch-intent", "successor-returned") else "A21"
            def crash(f, barrier=barrier):
                scenario = f.scenario(family, events_for(family, "terminal"),wait=barrier=="child-stop-request")
                if barrier == "child-started":
                    # This leg requires missing evidence; provider scheduling cannot choose the premise.
                    scenario["wait_before_events"] = True
                    (f.root/"scenario.json").write_text(json.dumps(scenario))
                proc, release, arrival = f.barrier(family, barrier,
                    extra=["--silence-s","0.05"] if barrier=="child-stop-request" else [])
                proc.kill()
                out, err = proc.communicate(timeout=10)
                f.history.append({"command":proc.args,"returncode":proc.returncode,"stdout":out,"stderr":err})
                module = f.module()
                j = f.snapshot()["journals"][0]
                child = j.get("child")
                if child and module.a3_liveness(child) == "alive":
                    os.killpg(child["pid"], signal.SIGKILL)
                    deadline = time.monotonic()+10
                    while module.a3_liveness(child) == "alive" and time.monotonic() < deadline:
                        time.sleep(0.01)
                before = f.snapshot()
                watched = f.run(f.command(family, "watch", ["--appear-s","0","--max-wait-s","0.05"]))
                observed = f.snapshot()
                command = shlex.split(module.a3_recovery_command(j))
                decision = "hold" if barrier in ("published-start","child-started") else "move"
                recovered = f.run(command + ["--decision",decision,"--reason","fixture recovery",
                                              "--repair-projection"])
                repeated = f.run(command + ["--decision",decision,"--reason","fixture replay",
                                             "--repair-projection"])
                after = f.snapshot()
                final = after["journals"][0]
                prior_starts = before["successor_start_count"]
                prior_intent = j["disposition"].get("attempted",False)
                expected_starts = prior_starts if prior_intent or decision == "hold" else 1
                closes = [r for r in after["record"] if r.get("event") == "lane-closed" and r.get("lane")=="case"]
                valid = (watched.returncode in (2,3) and observed["successor_start_count"] == prior_starts
                         and [r for r in before["record"] if r.get("event")=="lane-closed"] ==
                             [r for r in observed["record"] if r.get("event")=="lane-closed"]
                         and after["successor_start_count"] == expected_starts
                         and recovered.returncode in (2,3) and repeated.returncode in (2,3))
                if barrier == "child-started":
                    valid = valid and final["disposition"]["phase"] == "awaiting-head" and not closes
                elif barrier == "published-start":
                    valid = (valid and len(closes)==1 and closes[0]["exit_class"]=="setup-failed"
                             and closes[0]["refusal_count"]==0 and final["execution"]=="closed"
                             and final["disposition"]["decision"]=="held")
                else:
                    valid = (valid and len(closes)==1 and final["execution"]=="closed"
                             and final["evidence"].get("refusal_count")==1)
                if barrier=="outcome-saved":
                    valid=valid and "native process result 0 saved" in watched.stdout and "process outcome unknown" not in watched.stdout
                return valid and self.controls[family], {"arrival":arrival,"before":before,"observed":observed}
            self.exercise(group, family + " crash at " + barrier, crash)

    def kill_arbitration(self, family):
        for barrier in ("before-seal", "decision-sealed"):
            def kill_case(f, barrier=barrier):
                f.scenario(family, events_for(family,"terminal"))
                proc, release, arrival = f.barrier(family,barrier)
                command = f.command(family,"kill",["--reason","fixture explicit stop"])
                kill = f.run(command, timeout=30)
                during = f.snapshot()
                result = f.finish(proc,release)
                replay = f.run(command)
                snap = f.snapshot()
                j = snap["journals"][0]
                before = barrier == "before-seal"
                valid = (kill.returncode==3 and proc.returncode==3
                         and during["successor_start_count"]==0 and len([
                             r for r in snap["record"] if r.get("event")=="lane-closed" and r.get("lane")=="case"])==1
                         and snap["successor_start_count"]==int(not before)
                         and j["close"]["refusal_count"]==1
                         and j["close"]["exit_class"]==("killed" if before else "refusal")
                         and replay.returncode==(0 if before else 3))
                if before:
                    valid = valid and j["disposition"]["phase"]=="awaiting-head"
                return valid and self.controls[family], {"arrival":arrival,"during":during}
            self.exercise("A19",family+" kill "+barrier,kill_case)

    def corruption(self, family):
        for fault in ("torn-journal", "bad-phase", "conflicting-close", "stale-pass", "torn-record", "record-replaced"):
            def corrupt(f, fault=fault):
                f.scenario(family,events_for(family,"terminal"))
                proc, release, arrival = f.barrier(family,"prepared-outcome")
                proc.kill()
                proc.communicate(timeout=10)
                module=f.module()
                j=f.snapshot()["journals"][0]
                command=shlex.split(module.a3_recovery_command(j))+["--repair-projection"]
                journal=Path(module.a3_journal_path(str(f.record),j["pass_id"]))
                if fault=="torn-journal":
                    journal.write_text('{"schema":')
                elif fault=="bad-phase":
                    j["execution"]="invalid"; module.a3_save_journal(j)
                elif fault=="conflicting-close":
                    j["close"]["close_id"]="contradiction"; module.a3_save_journal(j)
                elif fault=="stale-pass":
                    command[command.index("--pass")+1]="0"*32
                elif fault=="torn-record":
                    with f.record.open("a") as h:
                        h.write(json.dumps({"event":"fixture-unrelated","lane":"other"})+'\n{"event":')
                else:
                    data=f.record.read_bytes(); f.record.unlink(); f.record.write_bytes(data)
                before=f.snapshot()
                result=f.run(command)
                after=f.snapshot()
                valid=(after["successor_start_count"]==before["successor_start_count"])
                if fault=="torn-record":
                    valid=valid and result.returncode==3 and sum(r.get("event")=="lane-closed" and
                        r.get("lane")=="case" for r in after["record"])==1 and any(
                        r.get("event")=="fixture-unrelated" for r in after["record"])
                    repeated=f.run(command)
                    valid=valid and repeated.returncode==3 and f.snapshot()["record"]==after["record"]
                else:
                    valid=valid and result.returncode==2 and "PROBE FAILED" in result.stderr
                return valid and self.controls[family],{"fault":fault,"before":before}
            self.exercise("A24",family+" "+fault,corrupt)

    def observer_requests(self, family):
        for phase in ("running", "finalising"):
            def request(f, phase=phase):
                f.scenario(family, events_for(family,"terminal"), wait=phase=="running")
                proc, release, arrival = f.barrier(family,
                    "native-evidence" if phase=="running" else "outcome-saved")
                j=f.snapshot()["journals"][0]
                path=Path(j["boundary"]["path"])
                os.utime(path,(time.time()-10,time.time()-10))
                watch=f.run(f.command(family,"watch",["--silence-s","0.01","--appear-s","0",
                    "--poll-s","0.01","--max-wait-s","0.1"]))
                during=f.snapshot()
                f.finish(proc,release)
                after=f.snapshot()
                j=after["journals"][0]
                requested=during["journals"][0].get("stop_intent")
                return (watch.returncode==8 and bool(requested)==(phase=="running")
                        and j["close"]["refusal_count"]==1 and j["close"]["exit_class"]=="refusal"
                        and (phase!="running" or j["stop_cause"]=="stall")
                        and after["successor_start_count"]==1,
                        {"arrival":arrival,"during":during})
            self.exercise("A17",family+" watch request while "+phase,request)

    def orphan_liveness(self, family):
        for variant in ("live-child", "unknown-owner", "reused-owner", "reused-child"):
            def liveness(f, variant=variant):
                f.scenario(family, events_for(family,"terminal"), wait=True)
                proc, release, arrival=f.barrier(family,"native-evidence")
                proc.kill(); proc.communicate(timeout=10)
                module=f.module(); j=f.snapshot()["journals"][0]
                child=dict(j["child"])
                command=shlex.split(module.a3_recovery_command(j))
                if variant=="unknown-owner":
                    j["owner"]["birth"]=""; module.a3_save_journal(j)
                elif variant=="reused-owner":
                    j["owner"]=dict(module.a3_process_identity(os.getpid()),birth="planted-old-birth")
                    module.a3_save_journal(j)
                elif variant=="reused-child":
                    # The controlled child is settled first; the reused PID belongs to this test.
                    os.killpg(child["pid"],signal.SIGKILL)
                    j["child"]=dict(module.a3_process_identity(os.getpid()),birth="planted-old-birth")
                    module.a3_save_journal(j)
                watched=f.run(f.command(family,"watch",["--appear-s","0","--max-wait-s","0.05"]))
                observed=f.snapshot()
                held=f.run(command+["--decision","hold","--reason","fixture head hold"])
                pending=f.snapshot()
                if variant=="unknown-owner":
                    valid=watched.returncode==8 and held.returncode==2 and module.a3_liveness(child)=="alive"
                    j["owner"]=j["original_owner"]; module.a3_save_journal(j)
                elif variant=="reused-child":
                    valid=watched.returncode==3 and held.returncode==3 and pending["journals"][0]["execution"]=="closed"
                else:
                    valid=(watched.returncode==3 and held.returncode==3
                           and pending["journals"][0]["execution"]!="closed"
                           and module.a3_liveness(child)=="alive")
                    stopped=f.run(command+["--decision","hold","--reason","fixture stop authorisation","--stop-child"])
                    valid=valid and stopped.returncode==3 and f.snapshot()["journals"][0]["execution"]=="closed"
                if module.a3_liveness(child)=="alive":
                    os.killpg(child["pid"],signal.SIGKILL)
                return (valid and observed["successor_start_count"]==0 and self.controls[family]
                        and not any(r.get("event")=="lane-closed" for r in observed["record"]),
                        {"arrival":arrival,"observed":observed,"pending":pending})
            self.exercise("A14",family+" "+variant,liveness)

    def competing_observers(self, family):
        def observers(f):
            from concurrent.futures import ThreadPoolExecutor
            f.scenario(family,events_for(family,"terminal"))
            proc,release,arrival=f.barrier(family,"outcome-saved")
            proc.kill(); proc.communicate(timeout=10)
            command=f.command(family,"watch",["--appear-s","0","--max-wait-s","0.05"])
            factory=f.command;f.command=lambda *args,**kwargs:command
            one,release_one,arrival_one=f.barrier(family,"observer-snapshot")
            two,release_two,arrival_two=f.barrier(family,"observer-snapshot")
            f.command=factory
            results=[f.finish(one,release_one),f.finish(two,release_two)]
            f.run(command)
            snap=f.snapshot()
            identifiers={n[0] for n in snap["notice_identities"]}
            observations=[r for r in snap["record"] if r.get("event")=="orphan-observed"]
            return (all(r["returncode"]==3 for r in results) and len(observations)==1 and len(identifiers)==1
                    and snap["successor_start_count"]==0 and self.controls[family]
                    and not any(r.get("event")=="lane-closed" for r in snap["record"]),arrival)
        self.exercise("A18",family+" concurrent and repeated watchers",observers)
        def reread(f):
            f.scenario(family,events_for(family,"terminal"))
            proc,release,arrival=f.barrier(family,"outcome-saved")
            proc.kill(); proc.communicate(timeout=10)
            original=f.command
            f.command=lambda fam,operation="spawn",extra=(): original(fam,"watch",[
                "--appear-s","0","--max-wait-s","0.05"]+list(extra))
            watcher,again,seen=f.barrier(family,"observer-snapshot")
            f.command=original
            killed=f.run(f.command(family,"kill",["--reason","fixture stop before observer reread"]))
            done=f.finish(watcher,again)
            snap=f.snapshot()
            return (killed.returncode==0 and done["returncode"]==3
                    and snap["successor_start_count"]==0 and self.controls[family]
                    and sum(r.get("event")=="lane-closed" for r in snap["record"])==1
                    and not any(r.get("event")=="orphan-observed" for r in snap["record"]),
                    {"owner":arrival,"observer":seen})
        self.exercise("A18",family+" kill before observer reread",reread)

    def competing_recoverers(self, family):
        def compete(f):
            from concurrent.futures import ThreadPoolExecutor
            f.scenario(family,events_for(family,"continued"))
            f.run(f.command(family))
            j=f.snapshot()["journals"][0]
            command=shlex.split(f.module().a3_recovery_command(j))+[
                "--decision","move","--reason","fixture concurrent judgement"]
            command.insert(1,"-B")
            factory=f.command;f.command=lambda *args,**kwargs:command
            claimant,release,arrival=f.barrier(family,"launch-intent")
            f.command=factory
            blocked=f.run(command)
            completed=f.finish(claimant,release)
            replay=f.run(command)
            snap=f.snapshot()
            return (blocked.returncode==2 and "gate busy" in blocked.stderr and completed["returncode"]==3 and replay.returncode==3
                    and snap["successor_start_count"]==1
                    and sum(r.get("event")=="lane-closed" and r.get("lane")=="case" for r in snap["record"])==1
                    and sum(r.get("event")=="disposition-resolved" for r in snap["record"])==1),None
        self.exercise("A15",family+" concurrent recovery and replay",compete)
        def alias(f):
            f.scenario(family,events_for(family,"terminal"))
            proc,release,arrival=f.barrier(family,"published-start")
            link=f.root/"record-alias.jsonl"; link.symlink_to(f.record)
            command=f.command(family)
            command[command.index("--record")+1]=str(link)
            blocked=f.run(command)
            during=f.snapshot()
            f.finish(proc,release)
            return (blocked.returncode==2 and "gate busy" in blocked.stderr
                    and len(during["journals"])==1 and during["successor_start_count"]==0
                    and f.snapshot()["successor_start_count"]==1),arrival
        self.exercise("A21",family+" canonical record alias shares gate",alias)

    def notice_matrix(self, family):
        def delivery(f):
            from concurrent.futures import ThreadPoolExecutor
            f.scenario(family,events_for(family,"terminal"))
            proc,release,arrival=f.barrier(family,"outcome-saved,notice-rendering")
            j=f.snapshot()["journals"][0]
            Path(j["input"]["snapshot"]).unlink()
            rendered=f.next_barrier(proc,release)
            proc.kill(); proc.communicate(timeout=10)
            j=f.snapshot()["journals"][0]
            head=[sys.executable,"-B",str(f.wrappers/"handsoff.py")]
            common=["--run","fixture","--record",str(f.record)]
            drain=head+["notices"]+common+["--pending","--format","json"]
            pending=json.loads(f.run(drain).stdout)["pending"]
            details=[]
            spec=importlib.util.spec_from_file_location("fixture_census_head",f.wrappers/"handsoff.py")
            census=importlib.util.module_from_spec(spec);spec.loader.exec_module(census)
            recorded=f.snapshot()["record"]
            opened=census.open_lane_attempts(recorded)
            planted=census.open_lane_attempts(recorded+[{"event":"lane-open","run":"fixture","lane":"census-control"}])
            valid=(bool(pending) and j["execution"]=="closed" and j["disposition"]["phase"]=="awaiting-input"
                   and len(opened)==0 and len(planted)==1)
            for notice in pending:
                triple=["--notice-id",notice["notice_id"],"--notice-version",str(notice["version"]),
                        "--notice-sha256",notice["payload_sha256"]]
                ledger=head+["ledger"]+common+["--observation","fixture head receipt"]+triple
                with ThreadPoolExecutor(max_workers=2) as pool:
                    receipts=list(pool.map(lambda _:f.run(ledger),range(2)))
                receipt=f.run(ledger)  # New process: restart after receipt, before acknowledgement.
                locator="record:"+receipt.stdout.split("record:",1)[1].split()[0]
                bad=f.run(head+["notices"]+common+["--ack"]+triple+[
                    "--route","hands-off","--receipt","record:fabricated"])
                still=json.loads(f.run(drain).stdout)["pending"]
                ack=f.run(head+["notices"]+common+["--ack"]+triple+[
                    "--route","hands-off","--receipt",locator])
                valid=(valid and all(r.returncode==0 for r in receipts) and bad.returncode==2
                       and any(n["payload_sha256"]==notice["payload_sha256"] for n in still)
                       and ack.returncode==0)
                details.append({"notice":notice,"receipt":locator})
            final=json.loads(f.run(drain).stdout)
            observations=[r for r in f.snapshot()["record"] if r.get("notice_receipt")]
            valid=valid and final["count"]==0 and len(observations)==len(pending)
            return valid and self.controls[family],{"arrival":arrival,"rendering":rendered,"receipts":details,
                                                    "open_attempts":len(opened),"open_attempt_control":len(planted)}
        self.exercise("A23",family+" b/c closed-before-render concurrent receipts and restart",delivery)
        def attended(f):
            f.scenario(family,events_for(family,"continued")); f.run(f.command(family))
            module=f.module(); head=[sys.executable,"-B",str(f.wrappers/"handsoff.py")]
            common=["--run","fixture","--record",str(f.record)]
            drain=head+["notices"]+common+["--pending","--format","json"]
            pending=json.loads(f.run(drain).stdout)["pending"]
            valid=bool(pending); displays=[]
            for notice in pending:
                triple=["--notice-id",notice["notice_id"],"--notice-version",str(notice["version"]),
                        "--notice-sha256",notice["payload_sha256"]]
                sink=f.root/("reply-%d.md"%notice["version"])
                command=head+["notices"]+common+["--ack"]+triple+[
                    "--route","attended","--receipt",str(sink),"--receipt-sha256","absent"]
                absent=f.run(command)
                text=module.a3_notice_text(notice)+"\n"
                sink.write_text(text); displays.append([notice["notice_id"],notice["version"]])
                # The emitted reply exists, but no acknowledgement has been made yet.
                replay=json.loads(f.run(drain).stdout)["pending"]
                valid=valid and absent.returncode==2 and notice in replay
                displays.append([notice["notice_id"],notice["version"]])
                command[-1]=sha(sink.read_bytes())
                ack=f.run(command); again=f.run(command)
                valid=valid and ack.returncode==again.returncode==0
            return (valid and json.loads(f.run(drain).stdout)["count"]==0 and self.controls[family],
                    {"displayed_versions":displays,"logical_versions":len(pending),
                     "replayed_displays":len(displays)-len(pending)})
        self.exercise("A23",family+" e attended reply receipt and uncertain display replay",attended)

    def capability_matrix(self, family):
        for fault in ("missing-estimate", "invalid-estimate", "missing-grants", "duplicate-grants",
                      "same-effort", "routing", "flagged-input", "isolation-unknown", "report-reference"):
            if fault=="routing" and family!="codex":
                continue
            def capability(f, fault=fault):
                f.scenario(family,events_for(family,"terminal"))
                proc,release,arrival=f.barrier(family,"outcome-saved")
                module=f.module(); j=f.snapshot()["journals"][0]
                if fault in ("missing-estimate","invalid-estimate"):
                    j["input"]["estimate"]=None if fault=="missing-estimate" else float("nan")
                elif fault=="missing-grants":
                    j["start"].pop("grants",None)
                elif fault=="duplicate-grants":
                    j["start"]["grants"]*=2
                elif fault=="same-effort":
                    j["start"]["effort"]="unavailable-effort"
                elif fault=="routing":
                    f.routing.write_text(json.dumps({"schema":2,"classes":{}}))
                elif fault=="flagged-input":
                    j["evidence"]["flagged_input"]=True
                elif fault=="isolation-unknown":
                    j["evidence"]["input_isolation_unknown"]=True
                else:
                    snapshot=Path(j["input"]["snapshot"])
                    snapshot.write_text(j["report"])
                    j["input"]["snapshot_sha256"]=sha(snapshot.read_bytes())
                module.a3_save_journal(j)
                result=f.finish(proc,release); snap=f.snapshot(); final=snap["journals"][0]
                return (result["returncode"]==3 and snap["successor_start_count"]==0
                        and final["disposition"]["phase"]=="awaiting-input"
                        and bool(final["disposition"].get("reason")) and bool(final["notices"])
                        and final["evidence"]["refusal_count"]==1 and self.controls[family]),arrival
            self.exercise("A26",family+" capability "+fault,capability)

    def kill_crashes(self, family):
        for barrier in ("prepared-outcome", "close-projection", "committed-journal"):
            def interrupted(f, barrier=barrier):
                f.scenario(family,events_for(family,"terminal"))
                proc,release,arrival=f.barrier(family,"before-seal,"+barrier)
                command=f.command(family,"kill",["--reason","fixture explicit stop"])
                requested=f.run(command)
                prepared=f.next_barrier(proc,release)
                proc.kill(); proc.communicate(timeout=10)
                first=f.run(command); second=f.run(command)
                snap=f.snapshot(); j=snap["journals"][0]
                return (requested.returncode==3 and first.returncode==second.returncode==0
                        and j["close"]["exit_class"]=="killed" and j["close"]["refusal_count"]==1
                        and snap["successor_start_count"]==0 and self.controls[family]
                        and "notice " in first.stdout and "recovery inspection:" in first.stdout
                        and sum(r.get("event")=="lane-closed" for r in snap["record"])==1), {"first":arrival,"crash":prepared}
            self.exercise("A20",family+" interrupted explicit kill at "+barrier,interrupted)

    def resume_competition(self, family):
        for contender in ("resume", "beat"):
            def concurrent(f, contender=contender):
                f.scenario(family,events_for(family,"clean")); f.run(f.command(family))
                original=f.command
                resume_extra=["--brief",str(f.brief)]+(["--home",str(f.root/"lane-home"),
                    "--projects-root",str(f.root/"projects")] if family=="claude" else [])
                f.command=lambda fam,operation="spawn",extra=(): original(fam,"resume",resume_extra+list(extra))
                proc,release,arrival=f.barrier(family,"published-start")
                f.command=original
                extra=resume_extra if contender=="resume" else (["--home",str(f.root/"lane-home"),
                    "--projects-root",str(f.root/"projects")] if family=="claude" else [])
                blocked=f.run(f.command(family,"resume",extra+(["--beat"] if contender=="beat" else [])))
                during=f.snapshot(); f.finish(proc,release); after=f.snapshot()
                reports=[j["report"] for j in after["journals"] if j.get("report")]
                return (blocked.returncode==2 and "gate busy" in blocked.stderr
                        and len(during["journals"])==2 and len(reports)==len(set(reports))==2
                        and after["successor_start_count"]==0 and self.controls[family]),arrival
            self.exercise("A25",family+" resume versus "+contender,concurrent)

    def notice_boundaries(self, family):
        def boundaries(f):
            f.scenario(family,events_for(family,"continued")); f.run(f.command(family))
            j=f.snapshot()["journals"][0]; notice=j["notices"][-1]
            head=[sys.executable,"-B",str(f.wrappers/"handsoff.py")]
            common=["--run","fixture","--record",str(f.record)]
            commands={"run-open":["--handoff",str(f.root/"absent.md"),"--session","fixture-head",
                                  "--head","fixture","--regime","single","--regime-src","head",
                                  "--detail","fixture entry"],
                      "run-resume":["--head","fixture","--detail","fixture restart"],
                      "gate":["--to","two"],
                      "boundary":["--from","one","--to","two","--disposition","fixture",
                                  "--waste","none","--next","fixture"],
                      "handoff":[],"close":[]}
            observed=[]
            for operation,extra in commands.items():
                result=f.run(head+[operation]+common+extra)
                observed.append({"operation":operation,"returncode":result.returncode,
                                 "notice_present":notice["notice_id"] in result.stdout})
            good=all(row["notice_present"] for row in observed)
            module=f.module(); path=Path(module.a3_journal_path(str(f.record),j["pass_id"]))
            path.write_text('{"invalid":')
            broken=f.run(head+["notices"]+common+["--pending","--format","json"])
            return (good and broken.returncode==2 and "PROBE FAILED" in broken.stderr
                    and self.controls[family]),observed
        self.exercise("A23",family+" f lifecycle early-return discovery and unreadable census",boundaries)

    def refusal_causes(self, family):
        def mixed(f):
            events=events_for(family,"terminal")
            if family=="codex":
                events += [{"type":"turn.failed","error":{"message":"Usage limit reached"}}]
                result=None
            else:
                result={"type":"result","subtype":"error_during_execution","is_error":True,
                        "result":"Usage limit reached"}
            f.scenario(family,events,result=result)
            r=f.run(f.command(family)); j=f.snapshot()["journals"][0]
            return (r.returncode==3 and j["close"]["exit_class"]=="refusal"
                    and j["evidence"]["refusal_count"]==1 and f.snapshot()["successor_start_count"]==1
                    and "Usage limit reached" in json.dumps(j["evidence"])
                    and bool(j["notices"])),None
        self.exercise("A29",family+" refusal retains separate usage-limit evidence",mixed)

    def stream_settlement(self, family):
        for release_tail in (True, False):
            def stream(f, release_tail=release_tail):
                data=f.scenario(family,events_for(family,"clean"))
                data["late_events"]=[events_for(family,"terminal")[-1]]
                (f.root/"scenario.json").write_text(json.dumps(data))
                command=f.command(family)
                proc=subprocess.Popen(command,env=f.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                f.processes.append(proc)
                ready=f.root/"late-ready"; ceiling=time.monotonic()+10
                while not ready.exists() and time.monotonic()<ceiling:
                    time.sleep(0.01)
                if not ready.exists():
                    raise RuntimeError("PROBE FAILED: inherited-stream fixture did not acknowledge")
                tail_identity=f.module().a3_process_identity(int(ready.read_text()))
                j=f.snapshot()["journals"][0]
                while f.module().a3_liveness(j["child"])!="dead" and time.monotonic()<ceiling:
                    time.sleep(0.01)
                child_exited=f.module().a3_liveness(j["child"])=="dead"
                observed=f.run(f.command(family,"watch",["--appear-s","0","--poll-s","0.01","--max-wait-s","0.05"]))
                if release_tail:
                    (f.root/"late-release").touch()
                out,err=proc.communicate(timeout=30)
                f.history.append({"command":command,"returncode":proc.returncode,"stdout":out,"stderr":err})
                snap=f.snapshot(); j=snap["journals"][0]
                if not release_tail:
                    tail_alive=f.module().a3_liveness(tail_identity)=="alive"
                    recovery=shlex.split(f.module().a3_recovery_command(j))+["--decision","hold","--reason","fixture incomplete stream"]
                    recovered=f.run(recovery)
                    snap=f.snapshot();j=snap["journals"][0]
                    recovery_held=(tail_alive and recovered.returncode==3 and j["execution"]!="closed"
                                   and j["evidence"].get("refusal_count") is None)
                if tail_identity and f.module().a3_liveness(tail_identity)=="alive":
                    os.kill(tail_identity["pid"],signal.SIGKILL)
                if release_tail:
                    valid=(j["close"]["refusal_count"]==1 and j["close"]["exit_class"]=="refusal"
                           and snap["successor_start_count"]==1)
                else:
                    valid=(recovery_held and j["execution"]!="closed" and j["disposition"]["phase"]=="awaiting-head"
                           and not j["evidence"]["settled"] and snap["successor_start_count"]==0
                           and not any(r.get("event")=="lane-closed" for r in snap["record"]))
                return (valid and child_exited and observed.returncode==8 and proc.returncode==3
                        and self.controls[family]),{"released_late_evidence":release_tail,
                                                    "child_death_observed":child_exited}
            self.exercise("A16",family+" inherited stream tail released="+str(release_tail),stream)

    def fallback_matrix(self, family):
        for verdict in ("fallback", "unconfirmed", "stale-map", "error-probe", "mixed-probe"):
            if family=="codex" and verdict in ("error-probe","mixed-probe"):
                continue
            for refused in (False, True):
                def fallback(f,verdict=verdict,refused=refused):
                    data=f.scenario(family,events_for(family,"terminal" if refused else "clean"))
                    expected_verdict=verdict if verdict not in ("error-probe","mixed-probe") else "unconfirmed"
                    if family=="claude":
                        facts,_=f.module().load_model_facts()
                        expected=facts["aliases"]["sonnet"]
                        observed=next(value for value in facts["aliases"].values()
                                      if value!=expected and not any(h in value.lower() for h in facts["helpers"]))
                        data["result"]={"type":"result","subtype":"success","is_error":False,
                                        "result":"fixture final report","modelUsage":{observed:{"outputTokens":1}}}
                        data["probe_result"]={"type":"result","result":"ok","modelUsage":{
                            observed if verdict=="stale-map" else expected:{"outputTokens":1}}}
                        if verdict=="error-probe":data["probe_result"]["is_error"]=True
                        elif verdict=="unconfirmed":data["probe_exit"]=1
                        elif verdict=="mixed-probe":data["probe_result"]["modelUsage"][observed]={"outputTokens":1}
                        (f.root/"scenario.json").write_text(json.dumps(data))
                        result=f.run(f.command(family))
                    else:
                        f.env["A3_FALLBACK_VERDICT"]=verdict
                        cmd=f.command(family)
                        result=f.run([sys.executable,"-B",str(f.bootstrap),cmd[2]]+cmd[3:])
                    snap=f.snapshot();j=snap["journals"][0]
                    starts=int(refused or verdict=="fallback")
                    valid=(snap["successor_start_count"]==starts and j["close"].get("fallback",{}).get("verdict")==expected_verdict
                           and result.returncode==(3 if refused else 0)
                           and j["close"].get("refusal_count")==int(refused)
                           and self.controls[family])
                    if family=="claude":
                        valid=valid and (f.root/"probe-input").read_text()=="Reply with the single word ok."
                        if verdict=="fallback":
                            valid=valid and "disposition moved" in result.stdout and "not attempted" not in result.stdout
                    return valid,{"verdict":verdict,"refused":refused}
                self.exercise("A26",family+" fallback "+verdict+" refused="+str(refused),fallback)
        def write_scope(f):
            f.scenario(family,events_for(family,"terminal"))
            f.run(f.command(family,extra=["--write",str(f.root/"work")]))
            snap=f.snapshot();j=snap["journals"][0]
            argv=snap["successor_starts"][0]["argv"]
            def values(flag):return [argv[i+1] for i,a in enumerate(argv[:-1]) if a==flag]
            return (snap["successor_start_count"]==1 and values("--write")==j["start"]["writes"]
                    and values("--grant")==j["start"]["grants"]
                    and values("--write")==[str((f.root/"work").resolve())]
                    and "--read-only" not in argv),j["disposition"]
        self.exercise("A02",family+" exact writable successor scope",write_scope)

    def launch_outcomes(self, family):
        for mode in ("missing-executable","no-ack","open-only","spawn-failed","started-error","started-unconfirmed"):
            def launch(f,mode=mode):
                f.scenario(family,events_for(family,"terminal"))
                if mode=="missing-executable":
                    f.env["AIMYTH_SWAP_CMD"]=str(f.root/"absent-launcher")
                elif mode.startswith("started-"):
                    f.successor.write_text(SUCCESSOR+'\nraise SystemExit(%d)\n'%(3 if mode=="started-error" else 4))
                else:
                    prefix=SUCCESSOR.split('record=Path(value("--record"))')[0]
                    if mode in ("open-only","spawn-failed"):
                        prefix+=r'''
with Path(value("--record")).open("a") as handle:
    handle.write(json.dumps({"event":"lane-open","run":value("--run"),"lane":value("--lane")})+"\n")
'''
                        if mode=="spawn-failed":
                            prefix+=r'''    handle.write(json.dumps({"event":"lane-closed","run":value("--run"),"lane":value("--lane"),"exit_class":"spawn-failed"})+"\n")
'''
                    f.successor.write_text(prefix+'\nraise SystemExit(0)\n')
                compile(f.successor.read_text(),str(f.successor),"exec")
                r=f.run(f.command(family));snap=f.snapshot();j=snap["journals"][0]
                command=shlex.split(f.module().a3_recovery_command(j))+["--decision","move","--reason","fixture reconciliation"]
                f.run(command);f.run(command);after=f.snapshot()
                starts=int(mode!="missing-executable")
                moved=mode.startswith("started-")
                return (r.returncode==3 and snap["successor_start_count"]==after["successor_start_count"]==starts
                        and j["disposition"].get("attempted") is True
                        and j["disposition"]["decision"]==("moved" if moved else "held")
                        and j["disposition"]["reason"]==("successor start recorded" if moved else "launch outcome unconfirmed")
                        and len([row for row in after["record"] if row.get("event")=="lane-closed" and row.get("lane")=="case"])==1
                        and self.controls[family]),{"mode":mode,"before":snap}
            self.exercise("A22",family+" successor outcome "+mode,launch)

    def notice_versions_and_crashes(self, family):
        def versions(f):
            f.scenario(family,events_for(family,"terminal"))
            proc,release,arrival=f.barrier(family,"child-started")
            proc.kill();proc.communicate(timeout=10)
            module=f.module()
            head=[sys.executable,"-B",str(f.wrappers/"handsoff.py")]
            common=["--run","fixture","--record",str(f.record)]
            drain=head+["notices"]+common+["--pending","--format","json"]
            f.run(f.command(family,"watch",["--appear-s","0","--poll-s","0.01"]))
            first=json.loads(f.run(drain).stdout)["pending"]
            def receive(notice):
                triple=["--notice-id",notice["notice_id"],"--notice-version",str(notice["version"]),
                        "--notice-sha256",notice["payload_sha256"]]
                receipt=f.run(head+["ledger"]+common+["--observation","fixture head received version"]+triple)
                locator="record:"+receipt.stdout.split("record:",1)[1].split()[0]
                ack=head+["notices"]+common+["--ack"]+triple+["--route","hands-off","--receipt",locator]
                return f.run(ack),ack
            ack,old_ack=receive(first[0])
            f.run(f.command(family,"watch",["--appear-s","0","--poll-s","0.01"]))
            clean=json.loads(f.run(drain).stdout)
            j=f.snapshot()["journals"][0]
            # Receiver fixture: two material updates, no fabricated execution close.
            # Native production of facts/closure is exercised by A16/A20/A21/A23b.
            with module.a3_record_lock(str(f.record)):
                j["evidence"].update(refusal_count=1,refusal_evidence=[{"event":1,"message_id":"fixture-late-evidence"}],
                                     source="fixture retained evidence")
                module.a3_notice(j,"orphan");module.a3_save_journal(j)
            second=json.loads(f.run(drain).stdout)["pending"][0]
            triple=["--notice-id",second["notice_id"],"--notice-version",str(second["version"]),
                    "--notice-sha256",second["payload_sha256"]]
            receipt=f.run(head+["ledger"]+common+["--observation","fixture version delivered before update"]+triple)
            with module.a3_record_lock(str(f.record)):
                j=module.a3_read_journal(str(f.record),j["pass_id"])
                j["disposition"].update(phase="resolved",decision="held",reason="fixture head resolution")
                module.a3_notice(j,"orphan");module.a3_save_journal(j)
                count=len(j["notices"]);module.a3_notice(j,"orphan");module.a3_save_journal(j)
                identical=len(j["notices"])==count
            f.run(old_ack)
            during=json.loads(f.run(drain).stdout)["pending"]
            for notice in during:receive(notice)
            final=json.loads(f.run(drain).stdout)
            current=f.snapshot()["journals"][0]
            receipts=[r for r in f.snapshot()["record"] if r.get("notice_receipt")]
            return (len(first)==1 and first[0]["version"]==1 and ack.returncode==0 and clean["count"]==0
                    and [n["version"] for n in during]==[2,3] and len({n["payload_sha256"] for n in current["notices"]})==3
                    and identical and final["count"]==0 and len(receipts)==3 and self.controls[family]), {"arrival":arrival,"pending_during_update":during}
        self.exercise("A23",family+" a/d open orphan and three version-specific receipts",versions)
        for barrier in ("receipt-before","receipt-after"):
            def crash(f,barrier=barrier):
                f.scenario(family,events_for(family,"continued"));f.run(f.command(family))
                j=f.snapshot()["journals"][0];notice=j["notices"][-1]
                triple=["--notice-id",notice["notice_id"],"--notice-version",str(notice["version"]),
                        "--notice-sha256",notice["payload_sha256"]]
                head=[sys.executable,"-B",str(f.wrappers/"handsoff.py")]
                common=["--run","fixture","--record",str(f.record)]
                ledger=head+["ledger"]+common+["--observation","fixture head receipt"]+triple
                original=f.command;f.command=lambda *args,**kwargs:ledger
                consumer,release,arrival=f.barrier(family,barrier)
                f.command=original;consumer.kill();consumer.communicate(timeout=10)
                before=[r for r in f.snapshot()["record"] if r.get("notice_receipt")]
                result=f.run(ledger)
                locator="record:"+result.stdout.split("record:",1)[1].split()[0]
                acknowledged=f.run(head+["notices"]+common+["--ack"]+triple+[
                    "--route","hands-off","--receipt",locator])
                after=[r for r in f.snapshot()["record"] if r.get("notice_receipt")]
                return (len(before)==int(barrier=="receipt-after") and len(after)==1
                        and result.returncode==acknowledged.returncode==0 and self.controls[family]),arrival
            self.exercise("A23",family+" c consumer crash at "+barrier,crash)

    def boundary_report_controls(self, family):
        for known in (True, False):
            def controls(f,known=known):
                f.scenario(family,events_for(family,"clean"));f.run(f.command(family))
                f.brief=f.root/"controlled-resume.md"
                f.brief.write_text("CURRENT-RESUME-INPUT\nCONTROL+: WHOLE-REPORT-CONTROL in <<REPORT>>\n")
                f.scenario(family,events_for(family,"clean"),result={
                    "type":"result","subtype":"success","is_error":False,"result":"WHOLE-REPORT-CONTROL"})
                original=f.command
                extras=["--brief",str(f.brief)]+(["--home",str(f.root/"lane-home"),
                    "--projects-root",str(f.root/"projects")] if family=="claude" else [])
                f.command=lambda fam,operation="spawn",extra=():original(fam,"resume",extras+list(extra))
                proc,release,arrival=f.barrier(family,"published-start")
                j=max(f.snapshot()["journals"],key=lambda j:j["ordinal"])
                if not known:
                    j["boundary"]["known"]=False;f.module().a3_save_journal(j)
                result=f.finish(proc,release);snap=f.snapshot()
                current=max(snap["journals"],key=lambda j:j["ordinal"])
                verdicts=current.get("close",{}).get("controls_deferred",[])
                return (result["returncode"]==(0 if known else 3) and len(verdicts)==1
                        and verdicts[0]["result"]==("checked" if known else "unverified")
                        and snap["successor_start_count"]==0 and self.controls[family]),arrival
            self.exercise("A10",family+" report control boundary known="+str(known),controls)

    def supervisor_beats(self, family):
        for mode in ("missing-wrapper", "failed-wrapper", "timeout-then-native-recovery"):
            def supervisor(f,mode=mode):
                if not f.supported:
                    raise RuntimeError("unsupported-interface: A3 invocation-linked beat observations")
                f.scenario(family,events_for(family,"clean"));f.run(f.command(family))
                before=f.snapshot()
                f.scenario(family,events_for(family,"terminal"),wait=True)
                stubs=f.root/"beat-wrappers";stubs.mkdir()
                if mode=="failed-wrapper":
                    (stubs/("lane.py" if family=="claude" else "codex-lane.py")).write_text("raise SystemExit(3)\n")
                driver=f.root/"beat-supervisor.py"
                driver.write_text(r'''
import argparse,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
path,record,family,mode,stubs=sys.argv[1:]
spec=importlib.util.spec_from_file_location("fixture_head_supervisor",path)
head=importlib.util.module_from_spec(spec);spec.loader.exec_module(head)
shared=head.a3_shared()
if mode!="timeout-then-native-recovery":
    os.environ[head.BEAT_WRAPPER_DIR_ENV]=stubs
else:
    original_run=head.subprocess.run
    def stop_after_native_detection(command,*args,**kwargs):
        if not isinstance(command,list) or "--beat" not in command:
            return original_run(command,*args,**kwargs)
        process=subprocess.Popen(command,cwd=kwargs.get("cwd"),env=kwargs.get("env"),
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,text=True)
        until=time.monotonic()+15  # Harness ceiling, set by judgement, unmeasured.
        handed_back=False
        try:
            while time.monotonic()<until:
                journals=shared.a3_journals(record,"fixture")
                if (Path(os.environ["A3_FIXTURE"])/"provider-ready").exists() and any(
                        j.get("kind")=="beat" and j["owner"]["pid"]==process.pid for j in journals):
                    # The supervisor has no result, while the native owner remains alive. Its
                    # eventual refusal must coexist with the fallback accounting observation.
                    handed_back=True
                    raise subprocess.TimeoutExpired(command,1)
                if process.poll() is not None:
                    raise RuntimeError("PROBE FAILED: native beat ended before readiness")
                time.sleep(0.01)
            raise RuntimeError("PROBE FAILED: native beat readiness did not arrive")
        finally:
            if not handed_back and process.poll() is None:process.kill();process.wait(timeout=10)
    head.subprocess.run=stop_after_native_detection
args=argparse.Namespace(run="fixture",beat_timeout_s=1)
print("fixture supervisor result",head.issue_beat(args,record,"case",family,{"beats":[],"cap":1},0,"fixture"))
''')
                result=f.run([sys.executable,"-B",str(driver),str(f.wrappers/"handsoff.py"),str(f.record),
                              family,mode,str(stubs)],timeout=40)
                snap=f.snapshot();fallback=[r for r in snap["record"] if r.get("event")=="hold-beat" and r.get("observation_only")]
                valid=(result.returncode==0 and len(fallback)==1 and fallback[0].get("ok") is False
                       and bool(fallback[0].get("invocation_id")) and snap["successor_start_count"]==0)
                if mode=="missing-wrapper":
                    valid=valid and not fallback[0].get("harness_may_survive")
                else:
                    extra=["--brief",str(f.brief)]+(["--home",str(f.root/"lane-home"),
                         "--projects-root",str(f.root/"projects")] if family=="claude" else [])
                    blocked=f.run(f.command(family,"resume",extra))
                    valid=valid and blocked.returncode==2 and any(
                        message in blocked.stderr for message in ("may survive","gate busy"))
                if mode=="timeout-then-native-recovery":
                    beat=next(j for j in snap["journals"] if j.get("kind")=="beat")
                    (f.root/"provider-release").touch()
                    until=time.monotonic()+15  # Harness ceiling, set by judgement, unmeasured.
                    native=[]
                    while time.monotonic()<until:
                        final=f.snapshot()
                        native=[r for r in final["record"] if r.get("event")=="hold-beat" and not r.get("observation_only")]
                        if native:break
                        time.sleep(0.01)
                    valid=(valid and len(native)==1
                           and native[0]["invocation_id"]==fallback[0]["invocation_id"]
                           and native[0]["refusal_count"]==1 and bool(native[0].get("notice")))
                final=f.snapshot()
                valid=(valid and [r for r in final["record"] if r.get("event")=="lane-closed"]==
                       [r for r in before["record"] if r.get("event")=="lane-closed"] and self.controls[family])
                return valid,{"mode":mode,"after_fallback":snap}
            self.exercise("A25",family+" supervisor beat "+mode,supervisor)

    def orphan_decisions(self, family):
        for origin in ("orphan", "explicit-kill"):
            for decision in ("move", "hold", "recovered"):
                def resolve(f,origin=origin,decision=decision):
                    f.brief.write_text("TASK-INPUT-CONTROL\nCONTROL+: WHOLE-REPORT-CONTROL in <<REPORT>>\n")
                    f.scenario(family,events_for(family,"continued" if origin=="orphan" else "terminal"),wait=origin=="orphan")
                    proc,release,arrival=f.barrier(family,"native-evidence" if origin=="orphan" else "before-seal")
                    if origin=="orphan":
                        proc.kill();proc.communicate(timeout=10)
                        f.run(f.command(family,"watch",["--appear-s","0","--poll-s","0.01"]))
                    else:
                        f.run(f.command(family,"kill",["--reason","fixture explicit stop"]))
                        f.finish(proc,release)
                    before=f.snapshot();j=before["journals"][0]
                    command=shlex.split(f.module().a3_recovery_command(j))
                    inspect=f.run(command)
                    chosen=command+["--decision",decision,"--reason","fixture head judgement","--stop-child"]
                    first=f.run(chosen);second=f.run(chosen)
                    after=f.snapshot();current=after["journals"][0]
                    closes=[r for r in after["record"] if r.get("event")=="lane-closed" and r.get("lane")=="case"]
                    valid=(inspect.returncode==first.returncode==second.returncode==3 and len(closes)==1
                           and after["successor_start_count"]==int(decision=="move")
                           and current["disposition"]["decision"]=={"move":"moved","hold":"held","recovered":"recovered"}[decision]
                           and self.controls[family])
                    if origin=="orphan":
                        valid=(valid and closes[0]["exit_class"]=="refusal" and closes[0].get("process_exit") is None
                               and "refusal detected; launcher gone; process outcome unknown" in first.stdout
                               and len(closes[0].get("controls_deferred",[]))==1
                               and closes[0]["controls_deferred"][0]["result"]=="unverified")
                    else:
                        valid=valid and [r for r in before["record"] if r.get("event")=="lane-closed"]==closes
                    return valid,{"arrival":arrival,"before":before}
                self.exercise("A15",family+" "+origin+" head decision "+decision,resolve)

    def recovery_crashes(self, family):
        for barrier in ("native-evidence","outcome-saved","before-seal","decision-sealed",
                        "prepared-outcome","close-projection","committed-journal","notice-rendering",
                        "launch-intent","successor-returned"):
            def crash(f,barrier=barrier):
                f.scenario(family,events_for(family,"terminal"),wait=True)
                original,release,first=f.barrier(family,"native-evidence")
                original.kill();original.communicate(timeout=10)
                j=f.snapshot()["journals"][0]
                command=shlex.split(f.module().a3_recovery_command(j))
                command.insert(1,"-B")
                command += ["--decision","move","--reason","fixture explicit recovery","--stop-child","--repair-projection"]
                command_factory=f.command
                f.command=lambda *args,**kwargs:command
                recoverer,release,arrival=f.barrier(family,barrier)
                f.command=command_factory
                recoverer.kill();recoverer.communicate(timeout=10)
                before=f.snapshot();j=before["journals"][0]
                expected=before["successor_start_count"] if j["disposition"].get("attempted") else 1
                first_retry=f.run(command);again=f.run(command)
                after=f.snapshot();closes=[r for r in after["record"] if r.get("event")=="lane-closed" and r.get("lane")=="case"]
                return (first_retry.returncode==again.returncode==3 and len(closes)==1
                        and closes[0].get("refusal_count")==1 and after["successor_start_count"]==expected
                        and self.controls[family]),{"original_crash":first,"recovery_crash":arrival,"before":before}
            self.exercise("A21",family+" recovery process crash at "+barrier,crash)

    def retired_writers(self, family):
        for name in ("close_from_transcript","fallback_swap"):
            def retired(f,name=name):
                from unittest import mock
                events=([claude_message("first","end_turn","FIRST-PART"),claude_message("second","end_turn","SECOND-PART")]
                        if family=="claude" else [codex_message("first","FIRST-PART"),codex_message("second","SECOND-PART"),{"type":"turn.completed"}])
                f.scenario(family,events);f.run(f.command(family))
                if name=="close_from_transcript":
                    # Unsupported legacy publication must not authorise a new report destination.
                    with f.record.open("a") as stream:
                        stream.write(json.dumps({"event":"lane-resumed","run":"fixture","lane":"case"})+"\n")
                before=f.snapshot();module=f.module();paths=module.store_paths
                opened=next(r for r in before["record"] if r.get("event")=="lane-open")
                spawned=next(r for r in before["record"] if r.get("event")=="lane-spawned")
                rejected=False
                with mock.patch.object(module,"store_paths",side_effect=lambda run,lane,record_override=None:
                                       paths(run,lane,record_override or str(f.record))), \
                     mock.patch.object(module.subprocess,"run",side_effect=RuntimeError("PROBE FAILED: unowned process attempt")), \
                     mock.patch.object(module.subprocess,"Popen",side_effect=RuntimeError("PROBE FAILED: unowned process attempt")):
                    try:
                        if name=="close_from_transcript":
                            module.close_from_transcript(str(f.record),"fixture","case",opened,spawned,
                                str(f.root/"lane-home"),str(f.root/"projects"),"fixture",None)
                        else:
                            module.fallback_swap({"run":"fixture","lane":"case","cls":"fixture","no_swap":True},
                                                 {},str(f.record))
                    except Exception as exc:
                        rejected=type(exc).__name__=="A3Premise"
                after=f.snapshot()
                return (rejected and before["record"]==after["record"]
                        and before["report_bytes_base64"]==after["report_bytes_base64"]
                        and after["successor_start_count"]==0 and self.controls[family]),{"before":before}
            self.exercise("A01",family+" retired unowned writer "+name,retired)

    def unusable_lock(self, family):
        def lock(f):
            f.scenario(family,events_for(family,"terminal"))
            f.env["A3_FAIL_LOCK"]="1";command=f.command(family)
            result=f.run([sys.executable,"-B",str(f.bootstrap),command[2]]+command[3:])
            before=f.snapshot()
            zero=(result.returncode==2 and "PROBE FAILED" in result.stderr and "unusable" in result.stderr
                  and before["successor_start_count"]==0 and not before["record"]
                  and not (f.root/(family+"-input")).exists())
            f.env.pop("A3_FAIL_LOCK")
            control=f.run(f.command(family));after=f.snapshot()
            return (zero and control.returncode==3 and after["successor_start_count"]==1),{"failed_premise":before}
        self.exercise("A24",family+" unusable lifetime lock with a subsequent allowed-move control",lock)

    def pending_fallback_status(self, family):
        def pending(f):
            f.scenario(family,events_for(family,"clean"))
            f.env["A3_CONFIRMED_FALLBACK"]="1"
            proc,release,arrival=f.barrier(family,"outcome-saved")
            j=f.snapshot()["journals"][0];j["input"]["estimate"]=None
            f.module().a3_save_journal(j)
            result=f.finish(proc,release);snap=f.snapshot();j=snap["journals"][0]
            return (result["returncode"]==3 and j["close"]["process_exit"]==0
                    and j["disposition"]["phase"]=="awaiting-input"
                    and snap["successor_start_count"]==0 and self.controls[family]),arrival
        self.exercise("A26",family+" pending fallback returns recovery-needed with natural process result retained",pending)

    def repeated_tail_repair(self, family):
        def repair(f):
            f.scenario(family,events_for(family,"terminal"))
            proc,release,arrival=f.barrier(family,"prepared-outcome")
            proc.kill();proc.communicate(timeout=10)
            j=f.snapshot()["journals"][0]
            recovery=shlex.split(f.module().a3_recovery_command(j))+["--repair-projection"]
            with f.record.open("a") as stream:stream.write('{"event":')
            first=f.run(recovery)
            notices=f.snapshot()["journals"][0]["notices"]
            def receipt(notice):
                return [sys.executable,"-B",str(f.wrappers/"handsoff.py"),"ledger","--run","fixture",
                        "--record",str(f.record),"--observation","fixture repair receipt",
                        "--notice-id",notice["notice_id"],"--notice-version",str(notice["version"]),
                        "--notice-sha256",notice["payload_sha256"]]
            control=f.run(receipt(notices[0]))
            with f.record.open("a") as stream:stream.write('{"event":')
            before=f.record.read_bytes()
            rejected=f.run(receipt(notices[1]))
            unchanged=f.record.read_bytes()==before
            repaired=f.run(recovery);received=f.run(receipt(notices[1]))
            final=f.snapshot()
            closes=[row for row in final["record"] if row.get("event")=="lane-closed" and row.get("lane")=="case"]
            markers=[row for row in final["record"] if row.get("event")=="record-tail-repaired"]
            return (first.returncode==3 and control.returncode==0 and rejected.returncode==2
                    and "PROBE FAILED" in rejected.stderr and unchanged
                    and repaired.returncode==3 and received.returncode==0
                    and len(closes)==1 and len(markers)==2 and final["successor_start_count"]==1),arrival
        self.exercise("A24",family+" identical later torn append requires its own repair witness",repair)

    def held_task_beat(self, family):
        def held(f):
            f.scenario(family,events_for(family,"clean"));f.env["A3_CONFIRMED_FALLBACK"]="1"
            command=f.command(family,extra=["--no-swap"])
            first=f.run([sys.executable,"-B",str(f.bootstrap),command[2]]+command[3:])
            f.env.pop("A3_CONFIRMED_FALLBACK")
            before=f.snapshot();task=before["journals"][0]
            spec=importlib.util.spec_from_file_location("fixture_hold_head",f.wrappers/"handsoff.py")
            head=importlib.util.module_from_spec(spec);spec.loader.exec_module(head)
            eligible=head.a3_can_beat(str(f.record),"fixture","case")
            extra=["--beat"]+(["--home",str(f.root/"lane-home"),"--projects-root",str(f.root/"projects")]
                               if family=="claude" else [])
            result=f.run(f.command(family,"resume",extra));after=f.snapshot()
            return (first.returncode==0 and task["disposition"]["phase"]=="resolved"
                    and task["disposition"]["decision"]=="held" and eligible is False
                    and result.returncode==2 and before["record"]==after["record"]
                    and before["journals"]==after["journals"] and before["model_inputs"]==after["model_inputs"]
                    and after["successor_start_count"]==0 and self.controls[family]),{"before":before}
        self.exercise("A25",family+" final task hold cannot authorise a cache beat",held)

    def uncertain_beat(self, family):
        def beat(f):
            f.scenario(family,events_for(family,"clean"));f.run(f.command(family))
            before=f.snapshot()
            f.scenario(family,["malformed fixture record"]+events_for(family,"clean"))
            extra=["--beat"]+(["--home",str(f.root/"lane-home"),"--projects-root",str(f.root/"projects")]
                               if family=="claude" else [])
            result=f.run(f.command(family,"resume",extra));after=f.snapshot()
            j=next(j for j in after["journals"] if j.get("kind")=="beat")
            return (result.returncode==3 and j["outcome"]["ok"] is False and bool(j["notices"])
                    and j["evidence"]["refusal_count"] is None
                    and [r for r in before["record"] if r.get("event")=="lane-closed"]==
                        [r for r in after["record"] if r.get("event")=="lane-closed"]
                    and after["successor_start_count"]==0 and self.controls[family]),None
        self.exercise("A25",family+" uncertain beat evidence cannot report success",beat)

    def remaining_variants(self, family):
        def stopped_work(f):
            f.scenario(family,events_for(family,"further"),wait=True)
            result=f.run(f.command(family,extra=["--silence-s","0.05"]))
            snap=f.snapshot();j=snap["journals"][0]
            return (result.returncode==3 and j["close"]["exit_class"]=="refusal"
                    and j["stop_cause"]=="stall" and snap["successor_start_count"]==1),None
        self.exercise("A08",family+" completion then further work then watchdog",stopped_work)
        def old_prefix(f):
            f.scenario(family,events_for(family,"continued"));f.run(f.command(family))
            old=f.snapshot()["journals"][0]
            command=shlex.split(f.module().a3_recovery_command(old))+["--decision","recovered","--reason","fixture head checked prior work"]
            f.run(command)
            # Beats retain the base eligibility rule, so establish a later completed pass
            # while retaining the older refusal in the same session's transcript prefix.
            common=(["--home",str(f.root/"lane-home"),"--projects-root",str(f.root/"projects")]
                    if family=="claude" else [])
            f.scenario(family,events_for(family,"clean"))
            intermediate=f.run(f.command(family,"resume",["--brief",str(f.brief)]+common))
            if intermediate.returncode!=0:
                raise RuntimeError("PROBE FAILED: completed prefix control did not run")
            beat=([claude_message("beat-prefix","end_turn","BEAT-PREFIX")] if family=="claude" else
                  [codex_message("beat-prefix","BEAT-PREFIX"),{"type":"turn.completed"}])
            f.scenario(family,beat)
            common=(["--home",str(f.root/"lane-home"),"--projects-root",str(f.root/"projects")]
                    if family=="claude" else [])
            beaten=f.run(f.command(family,"resume",["--beat"]+common))
            f.brief=f.root/"fresh-report-brief.md";f.brief.write_text("CURRENT-RESUME-INPUT\n")
            events=([claude_message("new-pass","end_turn","CURRENT-REPORT-ONLY")] if family=="claude" else
                    [codex_message("new-pass","CURRENT-REPORT-ONLY"),{"type":"turn.completed"}])
            f.scenario(family,events)
            result=f.run(f.command(family,"resume",["--brief",str(f.brief)]+common))
            snap=f.snapshot();j=max((j for j in snap["journals"] if j.get("kind")!="beat"),key=lambda j:j["ordinal"])
            return (beaten.returncode==0 and result.returncode==0 and j["close"]["refusal_count"]==0
                    and not j["notices"] and Path(j["report"]).read_text()=="CURRENT-REPORT-ONLY\n"
                    and snap["successor_start_count"]==0 and self.controls[family]),None
        self.exercise("A10",family+" old refusal, report and beat prefix excluded",old_prefix)
        def reader_failure(f):
            f.scenario(family,events_for(family,"terminal"),wait=True)
            proc,release,arrival=f.barrier(family,"native-evidence")
            os.write(release,b"E")
            # The provider is allowed to end; the planted capture/reader exception decides the failure.
            (f.root/"provider-release").touch()
            out,err=proc.communicate(timeout=30)
            f.history.append({"command":proc.args,"returncode":proc.returncode,"stdout":out,"stderr":err})
            snap=f.snapshot();j=snap["journals"][0]
            return (proc.returncode==3 and j["evidence"]["refusal_count"]==1 and bool(j["notices"])
                    and snap["successor_start_count"]==0 and self.controls[family]),arrival
        self.exercise("A16",family+" capture or reader failure preserves detected refusal",reader_failure)
        if family=="codex":
            def staged(f):
                source=f.root/"stage-source";source.mkdir();(source/"control.txt").write_text("STAGED-INPUT-CONTROL\n")
                f.brief.write_text("TASK-INPUT-CONTROL\nRead <<STAGED_COPY>>/control.txt.\nCONTROL+: STAGED-INPUT-CONTROL in <<STAGED_COPY>>/control.txt\n")
                f.scenario(family,events_for(family,"terminal"))
                command=f.command(family);index=command.index("--cwd");del command[index:index+2]
                command += ["--stage-from",str(source),"--stage-writable"]
                result=f.run(command);snap=f.snapshot();j=snap["journals"][0]
                original=Path(j["input"]["source_copy"]).read_bytes();delivered=Path(j["input"]["snapshot"]).read_bytes()
                target=snap["successor_starts"][0] if snap["successor_starts"] else {}
                return (result.returncode==3 and snap["successor_start_count"]==1
                        and b"<<STAGED_COPY>>" in original and b"<<STAGED_COPY>>" not in delivered
                        and original!=delivered and delivered.decode() in snap["model_inputs"][family]
                        and target.get("brief","").endswith(delivered.decode())
                        and j["input"]["source_sha256"]==sha(original)
                        and j["input"]["snapshot_sha256"]==sha(delivered)),j["input"]
            self.exercise("A02",family+" authorised staging substitution reaches successor with both hashes",staged)

    def family_limit(self, family):
        if not self.selected("A33"):
            return
        other = "codex" if family == "claude" else "claude"
        rule = ("both families refused: hold; the head may rewrite the brief once "
                "(harmless purpose stated, exact files and change, nothing from the refused replies) "
                "or park the task for the owner; a second double refusal parks it.")
        for trigger in ("refusal", "fallback", "completion"):
            fixture = Fixture(self.args.wrappers, self.args.fixture_root)
            try:
                fixture.successor.write_text(CHAIN_RECEIVER)
                fixture.env.update(A3_WRAPPERS=str(fixture.wrappers), A3_SECOND_TRIGGER=trigger)
                second_events = events_for(other, "terminal" if trigger == "refusal" else "clean")
                second_scenario = {"events": second_events, "exit": 0}
                if trigger == "fallback" and other == "claude":
                    # CR-A3-1 L3 (depth): the actual detector and harmless alias probe decide.
                    facts, _ = fixture.module().load_model_facts()
                    expected = facts["aliases"]["sonnet"]
                    observed = next(value for value in facts["aliases"].values()
                                    if value != expected and not any(h in value.lower() for h in facts["helpers"]))
                    second_scenario["result"] = {"type": "result", "subtype": "success", "is_error": False,
                        "result": "fixture final report", "modelUsage": {observed: {"outputTokens": 1}}}
                    second_scenario["probe_result"] = {"type": "result", "result": "ok",
                        "modelUsage": {expected: {"outputTokens": 1}}}
                (fixture.root / "second-scenario.json").write_text(json.dumps(second_scenario))
                fixture.scenario(family, events_for(family, "terminal"))
                result = fixture.run(fixture.command(family), timeout=60)
                captured = fixture.snapshot()
                second_file = fixture.root / "second-public-result.json"
                captured["second_public_result"] = (json.loads(second_file.read_text())
                                                     if second_file.exists() else None)
                journals = captured["journals"]
                source = next((j for j in journals if j.get("lane") == "case"), {})
                target = next((j for j in journals if j.get("lane") != "case"), {})
                valid = (result.returncode == 3 and captured["successor_start_count"] == 1
                         and len(journals) == 2 and target.get("execution") == "closed"
                         and source.get("disposition", {}).get("decision") == "moved")
                source_rules = [n for n in source.get("notices", []) if n["payload"].get("rule")]
                task_rules = [n for j in journals if j.get("task_id") == source.get("task_id")
                              for n in j.get("notices", []) if n["payload"].get("rule")]
                self.check("A33", family + " chain " + trigger + " source has no rule",
                           not source_rules and self.controls[family], {"source_rules": source_rules})
                expected_rules = 0 if trigger == "completion" else 1
                self.check("A33", family + " chain " + trigger + " task rule count",
                           len(task_rules) == expected_rules and self.controls[family],
                           {"expected": expected_rules, "rules": task_rules})
                if trigger == "completion":
                    valid = (valid and target.get("close", {}).get("exit_class") == "completed"
                             and target.get("disposition", {}).get("decision") == "none"
                             and not target.get("notices") and self.controls.get(family))
                else:
                    disposition = target.get("disposition", {})
                    notices = [n for n in target.get("notices", [])
                               if n["payload"].get("rule") == rule]
                    valid = (valid and disposition.get("phase") == "resolved"
                             and disposition.get("decision") == "held"
                             and disposition.get("reason") == "no untried model family remains"
                             and len(notices) == 1)
                    if notices:
                        payload = notices[0]["payload"]
                        history = payload.get("movement_history", [])
                        valid = (valid and payload.get("families_tried") == [family, other]
                                 and payload.get("task_id") == source["pass_id"]
                                 and len(history) == 2
                                 and all(Path(h["refusal_locator"].split("#")[0]).is_file()
                                         for h in history))
                valid = (valid and all("PROHIBITED-OUTPUT-CONTROL" not in start["brief"]
                                       and "TASK-INPUT-CONTROL" in start["brief"]
                                       for start in captured["successor_starts"]))
                if trigger == "fallback" and other == "claude":
                    probe = fixture.root / "probe-input"
                    captured["actual_probe_input"] = probe.read_text() if probe.exists() else None
                    valid = (valid and captured["actual_probe_input"] == "Reply with the single word ok."
                             and target.get("close", {}).get("fallback", {}).get("verdict") == "fallback")
                self.check("A33", family + " chain " + trigger, valid, captured)
                if trigger != "completion" and target:
                    before = sha(json.dumps(target["close"], sort_keys=True).encode())
                    command = shlex.split(fixture.module().a3_recovery_command(target))
                    moved = fixture.run(command + ["--decision", "move", "--reason", "fixture decision"])
                    replay = fixture.run(command)
                    after = fixture.snapshot()
                    final_target = next(j for j in after["journals"] if j["pass_id"] == target["pass_id"])
                    self.check("A33", family + " exhausted explicit move " + trigger,
                        moved.returncode == 2 and "no untried model family remains" in moved.stderr
                        and replay.returncode == 3 and after["successor_start_count"] == 1
                        and before == sha(json.dumps(final_target["close"], sort_keys=True).encode())
                        and final_target["notices"] == target["notices"], after)
                elif trigger != "completion":
                    self.check("A33", family + " exhausted explicit move " + trigger,
                               False, {"unsupported-interface": "no successor A3 journal"})
            except Exception as exc:
                self.check("A33", family + " chain " + trigger, False,
                           {"exception": repr(exc), **fixture.snapshot()})
            finally:
                fixture.cleanup()

    def fold_policy(self, family):
        if family != "codex" or not self.selected("A02"):
            return
        for shape in ("terminal", "continued", "quoted", "unknown", "error-only",
                      "structured-refusal", "structured-safety", "structured-stop"):
            def policy(f, shape=shape):
                events = json.loads(json.dumps(POLICY_EVENTS))
                if shape == "continued":
                    events += events_for(family, "clean")
                elif shape == "quoted":
                    events = [codex_message("quote", json.dumps(events)),
                              {"type": "item.completed", "item": {"type": "command_execution",
                               "aggregated_output": events[0]["message"] + " permission denied"}}]
                    events += events_for(family, "clean")
                elif shape == "unknown":
                    events = [{"type": "turn.failed", "error": {"message": "An unrecorded policy restriction"}}]
                elif shape == "error-only":
                    events = events[:1]
                elif shape.startswith("structured-"):
                    events = [{"type": "turn.failed", "error": {"code":
                        "safety_refusal" if shape == "structured-safety" else "refusal"}}]
                    if shape == "structured-stop":
                        events = [{"type": "turn.failed", "stop_reason": "refusal"}]
                f.scenario(family, events, exit_code=0 if shape in ("continued", "quoted") else 1)
                result = f.run(f.command(family)); snap = f.snapshot(); j = snap["journals"][0]
                expected = "failed" if shape.startswith("structured-") else {
                    "terminal": "refusal", "continued": "refusal-continued",
                    "quoted": "completed", "unknown": "failed", "error-only": "failed"}[shape]
                count = int(shape in ("terminal", "continued"))
                return (j["close"]["exit_class"] == expected and j["evidence"]["refusal_count"] == count
                        and snap["successor_start_count"] == int(expected == "refusal")
                        and result.returncode == (0 if shape == "quoted" else 3)
                        and self.controls[family]), {"recorded_events": POLICY_EVENTS, "shape": shape}
            synthetic = shape.startswith("structured-") or shape == "unknown"
            label = "synthetic Codex policy negative control " if synthetic else "recorded Codex policy "
            self.exercise("A02", "CR-A3-1 M3 spec " + label + shape, policy)

    def fold_family(self, family):
        if not self.selected("A33"):
            return
        other = "codex" if family == "claude" else "claude"
        def rule_notice(f, journal):
            expected = ("both families refused: hold; the head may rewrite the brief once "
                        "(harmless purpose stated, exact files and change, nothing from the refused replies) "
                        "or park the task for the owner; a second double refusal parks it.")
            notices = [n for n in journal["notices"] if n["payload"].get("rule")]
            if len(notices) != 1:
                return False
            payload = notices[0]["payload"]
            history = f.module().a3_task_history(journal)
            rendered = f.module().a3_notice_text(notices[0])
            before = json.loads(json.dumps(journal["notices"]))
            f.module().a3_notice(journal, journal["notices"][-1]["payload"]["kind"])
            return (payload["rule"] == expected and expected in rendered
                    and payload["families_tried"] == [other, family]
                    and payload["movement_history"] == history
                    and payload["task_id"] == journal["task_id"]
                    and payload["disposition"]["phase"] in ("awaiting-head", "resolved")
                    and all(row["refusal_locator"] in rendered
                            and Path(row["refusal_locator"].split("#", 1)[0]).is_file() for row in history)
                    and journal["notices"] == before)
        for decision in ("hold", "recovered"):
            def orphan(f, decision=decision):
                # Two native fixture passes supply real local locators; the fixture links their task.
                f.scenario(other, events_for(other, "clean"))
                f.run(f.command(other, extra=["--lane", "ancestor"]))
                ancestor = f.snapshot()["journals"][0]
                f.scenario(family, events_for(family, "terminal"))
                proc, release, arrived = f.barrier(family, "settled-evidence")
                j = next(j for j in f.snapshot()["journals"] if j["lane"] == "case")
                j.update(task_id=ancestor["task_id"], movement_history=ancestor["movement_history"]+j["movement_history"])
                f.module().a3_save_journal(j)
                proc.kill(); proc.communicate(timeout=10)
                command = shlex.split(f.module().a3_recovery_command(j))
                before = f.snapshot()
                expected_rule = f.module().A3_FAMILY_RULE
                for form in ("text", "json"):
                    inspected = f.run(command+["--format", form])
                    text = inspected.stdout
                    if form == "json":
                        block = json.loads(text).get("family_rule") or {}
                        visible = (block.get("rule") == expected_rule
                                   and block.get("families_tried") == [other, family]
                                   and block.get("task_id") == j["task_id"])
                    else:
                        visible = expected_rule in text and " → ".join([other, family]) in text
                    visible = (visible and all(row["refusal_locator"] in text for row in j["movement_history"]))
                    self.check("A33", family + " exhausted orphan " + decision + " inspection " + form,
                               inspected.returncode == 3 and visible
                               and before["journals"] == f.snapshot()["journals"] and self.controls[family],
                               {"inspection": text, "before": before})
                rejected = f.run(command+["--decision", "move", "--reason", "fixture move"])
                unchanged = before["journals"] == f.snapshot()["journals"]
                chosen = f.run(command+["--decision", decision, "--reason", "fixture head judgement"])
                snap = f.snapshot(); final = next(x for x in snap["journals"] if x["lane"] == "case")
                d = final["disposition"]
                return (rejected.returncode == 2 and "no untried model family remains" in rejected.stderr
                        and unchanged and chosen.returncode == 3 and d.get("phase") == "resolved"
                        and d.get("decision") == ("held" if decision == "hold" else decision)
                        and d.get("reason") == d.get("head_reason") == "fixture head judgement"
                        and snap["successor_start_count"] == 0 and self.controls[family]
                        and rule_notice(f, final)), arrived
            self.exercise("A33", "CR-A3-1 M1/L3 depth " + family + " exhausted orphan " + decision, orphan)
        for uncertainty in ("report not durably saved", "unsettled"):
            def pending(f, uncertainty=uncertainty):
                f.scenario(other, events_for(other, "clean")); f.run(f.command(other, extra=["--lane", "ancestor"]))
                ancestor = f.snapshot()["journals"][0]
                f.scenario(family, events_for(family, "terminal"))
                proc, release, arrived = f.barrier(family, "outcome-saved")
                j = next(j for j in f.snapshot()["journals"] if j["lane"] == "case")
                j.update(task_id=ancestor["task_id"], movement_history=ancestor["movement_history"]+j["movement_history"])
                if uncertainty == "unsettled": j["evidence"]["settled"] = False
                else: j["evidence"]["uncertainty"] = uncertainty
                f.module().a3_save_journal(j); result = f.finish(proc, release)
                before = f.snapshot(); final = next(x for x in before["journals"] if x["lane"] == "case")
                rejected = f.run(shlex.split(f.module().a3_recovery_command(final))+[
                    "--decision", "move", "--reason", "fixture move"])
                return (result["returncode"] == 3 and final["disposition"]["phase"] == "awaiting-head"
                        and rejected.returncode == 2 and "no untried model family remains" in rejected.stderr
                        and before["journals"] == f.snapshot()["journals"]
                        and before["successor_start_count"] == 0 and self.controls[family]
                        and rule_notice(f, final)), arrived
            self.exercise("A33", "CR-A3-1 M1/L3 depth " + family + " exhausted pending " + uncertainty, pending)
        for path in ("orphan", "pending"):
            for decision in ("hold", "recovered"):
                def no_swap(f, path=path, decision=decision):
                    f.scenario(family, events_for(family, "terminal"))
                    barrier = "settled-evidence" if path == "orphan" else "outcome-saved"
                    proc, release, arrived = f.barrier(family, barrier, extra=["--no-swap"])
                    j = next(x for x in f.snapshot()["journals"] if x["lane"] == "case")
                    if path == "orphan":
                        proc.kill(); proc.communicate(timeout=10)
                    else:
                        j["evidence"]["uncertainty"] = "report not durably saved"
                        f.module().a3_save_journal(j)
                        result = f.finish(proc, release)
                        if result["returncode"] != 3:
                            return False, {"result": result}
                    before = f.snapshot()
                    current = next(x for x in before["journals"] if x["pass_id"] == j["pass_id"])
                    command = shlex.split(f.module().a3_recovery_command(current))
                    shown = f.run(command)
                    allowed = [line for line in shown.stdout.splitlines() if line.startswith("allowed decisions:")]
                    rejected = f.run(command+["--decision", "move", "--reason", "fixture move"])
                    unchanged = before["journals"] == f.snapshot()["journals"]
                    chosen = f.run(command+["--decision", decision, "--reason", "fixture head judgement"])
                    snap = f.snapshot()
                    final = next(x for x in snap["journals"] if x["pass_id"] == j["pass_id"])
                    d = final["disposition"]
                    return (shown.returncode == 3 and allowed == ["allowed decisions: hold, recovered"]
                            and rejected.returncode == 2 and "movement disabled (--no-swap)" in rejected.stderr
                            and "allowed decisions: hold, recovered" in rejected.stderr and unchanged
                            and (path == "orphan" or current["disposition"]["phase"] == "awaiting-head")
                            and chosen.returncode == 3 and d["phase"] == "resolved"
                            and d.get("decision") == ("held" if decision == "hold" else decision)
                            and d.get("reason") == d.get("head_reason") == "fixture head judgement"
                            and (path == "orphan" or final["close"] == current["close"])
                            and snap["successor_start_count"] == 0 and self.controls[family]), {
                                "barrier": arrived, "path": path, "decision": decision, "before": before,
                                "allowed": allowed, "move_rejected_without_mutation": unchanged}
                self.exercise("A33", "CR-A3-1b F1 " + family + " no-swap " + path + " " + decision, no_swap)
        def exhausted_disabled(f):
            f.scenario(other, events_for(other, "clean")); f.run(f.command(other, extra=["--lane", "ancestor"]))
            ancestor = f.snapshot()["journals"][0]
            f.scenario(family, events_for(family, "terminal"))
            proc, release, arrived = f.barrier(family, "outcome-saved", extra=["--no-swap"])
            j = next(x for x in f.snapshot()["journals"] if x["lane"] == "case")
            j.update(task_id=ancestor["task_id"], movement_history=ancestor["movement_history"]+j["movement_history"])
            f.module().a3_save_journal(j); result = f.finish(proc, release)
            before = f.snapshot(); final = next(x for x in before["journals"] if x["lane"] == "case")
            rejected = f.run(shlex.split(f.module().a3_recovery_command(final))+[
                "--decision", "move", "--reason", "fixture move"])
            return (result["returncode"] == 3 and final["disposition"].get("reason") == "no untried model family remains"
                    and rejected.returncode == 2 and "no untried model family remains" in rejected.stderr
                    and before["journals"] == f.snapshot()["journals"] and rule_notice(f, final)
                    and before["successor_start_count"] == 0 and self.controls[family]), arrived
        self.exercise("A33", family + " exhausted no-swap uses N5 reason", exhausted_disabled)
        def resumed(f):
            f.successor.write_text(CHAIN_RECEIVER)
            f.env.update(A3_WRAPPERS=str(f.wrappers), A3_SECOND_TRIGGER="completion")
            (f.root/"second-scenario.json").write_text(json.dumps({"events": events_for(other, "clean"), "exit": 0}))
            f.scenario(family, events_for(family, "terminal")); f.run(f.command(family))
            before = f.snapshot(); source = next(j for j in before["journals"] if j["lane"] == "case")
            source_rules = [n for n in source["notices"] if n["payload"].get("rule")]
            before_rules = [n for j in before["journals"] if j.get("task_id") == source["task_id"]
                            for n in j["notices"] if n["payload"].get("rule")]
            self.check("A33", family + " resumed source original notices have no rule",
                       not source_rules and self.controls[family], {"rules": source_rules})
            self.check("A33", family + " resumed source completed task has zero rules",
                       not before_rules and self.controls[family], {"rules": before_rules})
            extra = ["--brief", str(f.brief)]
            if family == "claude": extra += ["--home", str(f.root/"lane-home"), "--projects-root", str(f.root/"projects")]
            result = f.run(f.command(family, "resume", extra)); snap = f.snapshot()
            current = max((j for j in snap["journals"] if j["lane"] == "case"), key=lambda j:j["ordinal"])
            after_rules = [n for j in snap["journals"] if j.get("task_id") == source["task_id"]
                           for n in j["notices"] if n["payload"].get("rule")]
            self.check("A33", family + " resumed source refused task has one rule",
                       len(after_rules) == 1 and self.controls[family], {"rules": after_rules})
            repeated = f.run(f.command(family, "resume", extra)); repeated_snap = f.snapshot()
            repeated_rules = [n for j in repeated_snap["journals"] if j.get("task_id") == source["task_id"]
                              for n in j["notices"] if n["payload"].get("rule")]
            self.check("A33", family + " repeated resumed refusal keeps one task rule",
                       repeated.returncode == 3 and len(repeated_rules) == 1
                       and repeated_snap["successor_start_count"] == 1 and self.controls[family],
                       {"rules": repeated_rules})
            return (result.returncode == 3 and current["ordinal"] > source["ordinal"]
                    and current["task_id"] == source["task_id"]
                    and current["disposition"].get("reason") == "no untried model family remains"
                    and snap["successor_start_count"] == before["successor_start_count"] == 1
                    and {r["family"] for r in f.module().a3_task_history(current)} == {"claude", "codex"}
                    and self.controls[family]), {"before": before}
        self.exercise("A33", "CR-A3-1 L1 spec/depth " + family + " resumed source uses task history", resumed)

    def fold_contracts(self):
        if not self.selected("A31"):
            return
        def roots(f):
            results = {}
            env = dict(f.env, TMPDIR=str(f.root/"platform-temp"), LLM_WIKI_STORE=str(f.store))
            env.pop("AIMYTH_TEST_ROOT", None); env.pop("AIMYTH_TEST_SCRATCH_ROOT", None)
            stub = 'mktemp() { shift; printf "%s\\n" "${1:-$TMPDIR/default-control}"; }; die() { echo "PROBE FAILED: $1"; exit 2; };\n'
            for name, variable in (("test_lane.sh", "F"), ("test_codex_lane.sh", "T"), ("test_handsoff.sh", "WORK")):
                source = (f.wrappers/name).read_text()
                if variable == "F" and 'if [ -n "${AIMYTH_TEST_ROOT:-}" ]; then' in source:
                    start = source.index('if [ -n "${AIMYTH_TEST_ROOT:-}" ]; then')
                    snippet = source[start:source.index('\nfi', start)+3]
                else:
                    snippet = next(line for line in source.splitlines() if line.startswith(variable+'='))
                run = subprocess.run(["/bin/sh", "-c", stub+snippet+'\nprintf "%s\\n" "$'+variable+'"'],
                                     env=env, capture_output=True, text=True)
                parent = Path(run.stdout.strip()).parent
                wanted = Path("/tmp") if variable == "WORK" else Path(env["TMPDIR"])
                results[name] = {"returncode": run.returncode, "root": run.stdout.strip(), "expected_parent": str(wanted)}
                if run.returncode or parent.resolve() != wanted.resolve(): return False, results
            source = (f.wrappers/"test_lane.sh").read_text()
            snippet = next(line for line in source.splitlines() if line.startswith('LFTMP=$(mktemp'))
            run = subprocess.run(["/bin/sh", "-c", stub+snippet+'\nprintf "%s\\n" "$LFTMP"'],
                                 env=env, capture_output=True, text=True)
            results["B4LF-04"] = run.stdout.strip()
            return (run.returncode == 0 and Path(run.stdout.strip()).parent.resolve() == Path("/tmp").resolve()
                    and all(str(f.store.resolve()) not in str(Path(value["root"]).resolve()) for value in results.values() if isinstance(value, dict))), results
        self.exercise("A31", "CR-A3-1 M2 depth/spec default roots ignore caller store and preserve /tmp cases", roots)
        def premise(f):
            source = (f.wrappers/"test_lane.sh").read_text()
            marker = "<<'FIXTURE_PREMISE_END'"
            if marker not in source: return False, {"missing": "out-of-grant premise guard"}
            body = source.split(marker, 1)[1].split("\n", 1)[1].split("\nFIXTURE_PREMISE_END", 1)[0]
            paths = [f.root/"outside", Path("/tmp")/"planted", f.root/"vault/planted", f.wrappers/"planted"]
            outputs = []
            for root in paths:
                result = f.run([sys.executable, "-B", "-c", body, str(root), str(f.root/"vault"), str(f.wrappers)])
                outputs.append({"root": str(root), "rc": result.returncode, "stderr": result.stderr})
            return (outputs[0]["rc"] == 0 and all(r["rc"] == 2 and "PROBE FAILED" in r["stderr"]
                    for r in outputs[1:])), outputs
        self.exercise("A31", "CR-A3-1 M2 depth/spec outside-root control and granted-root rejection", premise)
        def codex_premise(f):
            source = (f.wrappers/"test_codex_lane.sh").read_text()
            marker = "<<'FIXTURE_PREMISE_END'"
            if marker not in source:
                return False, {"missing": "Codex fixture premise guard"}
            body = source.split(marker, 1)[1].split("\n", 1)[1].split("\nFIXTURE_PREMISE_END", 1)[0]
            paths = [(Path("/tmp")/f.root.name, 0), (Path("/dev")/f.root.name, 0),
                     (f.root/"vault/planted", 2), (f.wrappers/"planted", 2)]
            outputs = []
            for root, expected in paths:
                result = f.run([sys.executable, "-B", "-c", body, str(root), str(f.root/"vault"), str(f.wrappers)])
                outputs.append({"root": str(root), "expected": expected, "rc": result.returncode, "stderr": result.stderr})
            return (all(row["rc"] == row["expected"] for row in outputs)
                    and all("PROBE FAILED" in row["stderr"] for row in outputs if row["expected"])), outputs
        self.exercise("A31", "CR-A3-1b F4 Codex scratch acceptance and vault/HERE rejection controls", codex_premise)
        def detections(f):
            source = (f.wrappers/"test_lane.sh").read_text()
            found = {name: any('--lane '+lane+' ' in line and '--no-swap' in line
                              for line in source.splitlines())
                     for name, lane in (("FB4", "FB4"), ("FB4b", "FB4B"), ("FB7", "FB7"))}
            return all(found.values()) and 'ok "FB1 ' in source, found
        self.exercise("A31", "CR-A3-1 L2 depth restored detection cases and clean control", detections)
        def wording(f):
            source = (f.wrappers/"test_codex_lane.sh").read_text()
            line = next(line for line in source.splitlines() if line.startswith('f7leg "F7-C19 '))
            return ('evidence-incomplete' in line and 'returning 3' in line and 'awaiting the head' in line
                    and 'must never cost the close' not in line and 'F7-C20' in source), line
        self.exercise("A31", "CR-A3-1 L4 depth explicit malformed-stream semantic migration", wording)

    def base_and_census(self):
        if not self.selected("A01"):
            return
        import ast
        base=Path(self.args.base or Path(self.args.wrappers).parent/"H")
        manifest=Path(self.args.base_manifest or Path(self.args.wrappers).parent.parent/"installed-base.sha256")
        try:
            expected={Path(line.split(maxsplit=1)[1]).name:line.split(maxsplit=1)[0]
                      for line in manifest.read_text().splitlines() if line.strip()}
            before={name:sha((base/name).read_bytes()) for name in expected}
            self.check("A01","supplied base hashes and altered-byte control",bool(before) and before==expected
                       and sha(b"original")!=sha(b"altered"),{"base":before,"expected":expected})
            sites=[]
            for name in ("lane.py","codex-lane.py","handsoff.py"):
                tree=ast.parse((Path(self.args.wrappers)/name).read_text())
                for node in ast.walk(tree):
                    if isinstance(node,ast.Call):
                        called=getattr(node.func,"id",None) or getattr(node.func,"attr",None)
                        if called in ("append_record","_append_record_unlocked","finish","finish_beat",
                                      "a3_launch","a3_project","a3_prepare_move","a3_prepare_disposition",
                                      "a3_recover","a3_kill","fallback_swap","close_if_orphan"):
                            sites.append({"file":name,"line":node.lineno,"call":called})
            controls=ast.parse('append_record(path, {"event":"lane-closed"})')
            positive=sum(isinstance(n,ast.Call) for n in ast.walk(controls))
            self.check("A01","complete append/finaliser caller census",bool(sites) and positive==1,
                       {"calls":sites,"count":len(sites),"positive_control":positive})
        except (OSError,ValueError,SyntaxError) as exc:
            self.check("A01","base/census premise",False,{"premise":str(exc)})

    def package_roundtrip(self):
        if not self.selected("A32"):
            return
        if not self.args.package:
            self.check("A32","package gate",False,{"premise":"--package is required for install/undo verification"})
            return
        f=Fixture(self.args.wrappers,self.args.fixture_root)
        try:
            package=Path(self.args.package).resolve()
            base=Path(self.args.base or Path(self.args.wrappers).parent/"H")
            diffs = sorted(package.glob("*.diff"))
            shaped = bool(diffs) and all(
                patch.read_text().splitlines()[1].startswith("+++ b/.claude/skills/delegate/")
                for patch in diffs)
            self.check("A32", "CR-A3-1 L5 spec vault-shaped diffs at real strip depth",
                       shaped and '"-p4"' in (package/"install.sh").read_text(),
                       {"headers": {patch.name: patch.read_text().splitlines()[:2] for patch in diffs}})
            target=f.root/"target"; backup=f.root/"backup"
            shutil.copytree(base,target,ignore=shutil.ignore_patterns("__pycache__"))
            def manifest():
                return {str(p.relative_to(target)):sha(p.read_bytes()) for p in target.rglob("*") if p.is_file()}
            before=manifest()
            command=["/bin/sh",str(package/"install.sh"),"--target",str(target),"--backup",str(backup)]
            dry=f.run(command+["--dry-run"],timeout=120)
            dry_same=before==manifest() and not backup.exists()
            installed=f.run(command,timeout=120); stage=manifest()
            expected={line.split(maxsplit=1)[1]:line.split(maxsplit=1)[0]
                      for line in (package/"staged.sha256").read_text().splitlines() if line.strip()}
            staged_matches=all(stage.get(name)==digest for name,digest in expected.items())
            again=f.run(command,timeout=120)
            undo=["/bin/sh",str(package/"undo.sh"),"--target",str(target),"--backup",str(backup)]
            undo_dry=f.run(undo+["--dry-run"],timeout=120)
            stage_same=stage==manifest()
            undone=f.run(undo,timeout=120); after=manifest()
            self.check("A32","flat package dry-run/install/idempotence/undo round trip",
                       all(r.returncode==0 for r in (dry,installed,again,undo_dry,undone))
                       and dry_same and staged_matches and stage_same and before==after,
                       {"before":before,"installed":stage,"after":after,"commands":f.history})
            # A32: changed payload and backup controls must fail before any target mutation.
            bad_package = f.root/"bad-package"
            shutil.copytree(package, bad_package)
            (bad_package/"lane.py").write_bytes((bad_package/"lane.py").read_bytes()+b"\n# altered payload\n")
            bad_command = ["/bin/sh", str(bad_package/"install.sh"), "--target", str(target), "--backup", str(backup)]
            denied = f.run(bad_command, timeout=120)
            self.check("A32", "altered staged payload rejected before mutation",
                       denied.returncode == 2 and "PROBE FAILED" in denied.stderr and before == manifest(),
                       {"result": f.history[-1]})
            installed_again = f.run(command, timeout=120)
            backup_bytes = (backup/"lane.py").read_bytes()
            (backup/"lane.py").write_bytes(backup_bytes+b"\n# altered backup\n")
            staged_before = manifest(); denied = f.run(undo, timeout=120)
            self.check("A32", "altered backup rejected before undo mutation",
                       installed_again.returncode == 0 and denied.returncode == 2
                       and "PROBE FAILED" in denied.stderr and staged_before == manifest(),
                       {"result": f.history[-1]})
            (backup/"lane.py").write_bytes(backup_bytes)
            restored = f.run(undo, timeout=120)
            self.check("A32", "verified backup restores complete original manifest",
                       restored.returncode == 0 and before == manifest(), {"after": manifest()})
            (target/"lane.py").write_bytes((target/"lane.py").read_bytes()+b"\n# planted altered base\n")
            planted=manifest(); denied=f.run(command,timeout=120)
            self.check("A32","altered base rejected before mutation",
                       denied.returncode==2 and "PROBE FAILED" in denied.stderr and planted==manifest(),
                       {"result":f.history[-1]})
        except Exception as exc:
            self.check("A32","package premise",False,{"exception":repr(exc),"commands":f.history})
        finally:
            f.cleanup()

    def mutations(self):
        if not self.selected("A31") or self.args.no_mutations:
            return
        source=(Path(self.args.wrappers)/"lane.py").read_text()
        function_start=source.find("def a3_final_success(")
        function_end=source.find("\n\n# ",function_start)
        if function_start<0 or function_end<0:
            self.check("A31","mutation seam",False,{"unsupported-interface":"a3_final_success"})
            return
        replacements = {
            "any-completion": ("A06", source[:function_start] + '''def a3_final_success(harness, evidence, process_exit, successful_result=True, stopped=False):
    return process_exit == 0 and successful_result and not stopped and bool(evidence.get("last_completion"))
''' + source[function_end:]),
            "result-only": ("A07", source[:function_start] + '''def a3_final_success(harness, evidence, process_exit, successful_result=True, stopped=False):
    return process_exit == 0 and successful_result and not stopped
''' + source[function_end:]),
            "no-final-guard": ("A08", source[:function_start] + '''def a3_final_success(harness, evidence, process_exit, successful_result=True, stopped=False):
    return (process_exit == 0 and successful_result and not stopped
            and evidence.get("last_completion", 0) > evidence.get("last_refusal", 0))
''' + source[function_end:]),
        }
        anchor='    for journal in a3_journals(record, run):\n        acknowledgements = '
        if source.count(anchor)!=1:
            self.check("A31","open-only mutation anchor",False)
        else:
            replacements["open-only-drain"]=("A23",source.replace(anchor,
                '    for journal in a3_journals(record, run):\n        if journal["execution"] == "closed":\n            continue\n        acknowledgements = '))
        anchor='            if key not in acknowledgements:\n'
        if source.count(anchor)!=1:
            self.check("A31","identifier-only mutation anchor",False)
        else:
            replacements["identifier-only-ack"]=("A23",source.replace(anchor,
                '            if not any(key[0] == old[0] for old in acknowledgements):\n'))
        anchor='    identity = journal["owner"]\n    live = a3_liveness(identity)\n'
        if source.count(anchor)!=1:
            self.check("A31","observer-ownership mutation anchor",False)
        else:
            replacements["observer-projects-close"]=("A16",source.replace(anchor,'''    if journal["execution"] == "prepared":
        gate = type("MutatedGate", (), {"record": record})()
        owner = A3Owner(gate, journal["harness"], None, None)
        owner.journal, owner.recovering = journal, True
        a3_project(owner)
        journal = owner.journal
'''+anchor))
        for name,(group,mutated) in replacements.items():
            fixture=Fixture(self.args.wrappers,self.args.fixture_root)
            try:
                wrappers=fixture.root/"mutant"
                shutil.copytree(self.args.wrappers,wrappers,ignore=shutil.ignore_patterns("__pycache__"))
                (wrappers/"lane.py").write_text(mutated)
                compile(mutated,str(wrappers/"lane.py"),"exec")
                command=[sys.executable,"-B",str(Path(__file__).resolve()),"--wrappers",str(wrappers),
                         "--fixture-root",str(fixture.root),"--only",group,"--only","A03","--no-mutations"]
                result=fixture.run(command,timeout=180)
                clean=[line for line in result.stdout.splitlines() if line.startswith("OK A03") and line.endswith(" clean")]
                bad=[line for line in result.stdout.splitlines() if line.startswith("BAD "+group)]
                self.check("A31",name+" mutant fails designated leg and preserves clean controls",
                           result.returncode==1 and bool(bad) and len(clean)==2,
                           {"designated_group":group,"failures":bad,"clean_controls":clean,
                            "returncode":result.returncode,"stdout":result.stdout,"stderr":result.stderr})
            except Exception as exc:
                self.check("A31",name,False,{"exception":repr(exc)})
            finally:
                fixture.cleanup()

    def native_suites(self):
        if not self.args.native and not self.args.native_suite:
            return
        for name in ("test_lane.sh","test_codex_lane.sh","test_handsoff.sh"):
            if self.args.native_suite and name not in self.args.native_suite:
                continue
            command=["/bin/sh",str(Path(self.args.wrappers)/name)]
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1")
            env["AIMYTH_TEST_ROOT"] = str(Path(self.args.native_fixture_root or self.args.fixture_root).resolve())
            if self.args.native_scratch_root:
                env["AIMYTH_TEST_SCRATCH_ROOT"] = str(Path(self.args.native_scratch_root).resolve())
            env["PATH"]=os.pathsep.join([str(Path(sys.executable).parent),"/usr/local/bin",
                                        "/usr/bin","/bin","/usr/sbin","/sbin"])
            if name=="test_lane.sh":
                if not self.args.vault:
                    self.check("A31",name,False,{"premise":"--vault is required"}); continue
                command += ["--vault",self.args.vault]
            if name=="test_handsoff.sh":
                if not self.args.hooks_dir:
                    self.check("A31",name,False,{"premise":"--hooks-dir read grant is required"}); continue
                env["HOOKS_DIR"]=self.args.hooks_dir
            fixture=Fixture(self.args.wrappers,self.args.fixture_root)
            try:
                if name=="test_codex_lane.sh":
                    for definition in ("critic", "builder", "verifier"):
                        (fixture.root/"vault/.claude/agents"/(definition+".md")).write_text(
                            "---\nname: "+definition+"\ndescription: fixture role\ntools: Read, Grep, Glob, Bash, Write, Edit\n---\nFixture role.\n")
                    env["CLAUDE_PROJECT_DIR"]=str(fixture.root/"vault")
                result=subprocess.run(command,env=env,cwd=Path(self.args.wrappers).resolve(),
                                      capture_output=True,text=True,timeout=1100)
                final=result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
                self.check("A31",name+" native gate",result.returncode==0 and final.startswith("PASS "),
                           {"command":command,"returncode":result.returncode,"final":final,
                            "stdout":result.stdout,"stderr":result.stderr})
            finally:
                fixture.cleanup()

    def run(self):
        families = ("claude", "codex") if self.args.part == "all" else (self.args.part,)
        for family in families:
            if family in ("claude", "codex"):
                self.positive(family)
                if getattr(self.args, "fold_only", False):
                    self.fold_family(family)
                    self.fold_policy(family)
                    continue
                self.basic(family)
                self.ordinary_paths(family)
                self.guarded(family)
                self.input_holds(family)
                self.native_observers(family)
                self.orphan(family)
                self.decisions(family)
                self.notices(family)
                self.beats(family)
                self.extra_public(family)
                self.provenance(family)
                self.boundary_faults(family)
                self.lifecycle_faults(family)
                self.crash_matrix(family)
                self.kill_arbitration(family)
                self.corruption(family)
                self.observer_requests(family)
                self.orphan_liveness(family)
                self.competing_observers(family)
                self.competing_recoverers(family)
                self.notice_matrix(family)
                self.capability_matrix(family)
                self.kill_crashes(family)
                self.resume_competition(family)
                self.notice_boundaries(family)
                self.refusal_causes(family)
                self.stream_settlement(family)
                self.fallback_matrix(family)
                self.launch_outcomes(family)
                self.notice_versions_and_crashes(family)
                self.boundary_report_controls(family)
                self.supervisor_beats(family)
                self.orphan_decisions(family)
                self.recovery_crashes(family)
                self.retired_writers(family)
                self.unusable_lock(family)
                self.pending_fallback_status(family)
                self.repeated_tail_repair(family)
                self.held_task_beat(family)
                self.uncertain_beat(family)
                self.remaining_variants(family)
                self.family_limit(family)
                self.fold_family(family)
                self.fold_policy(family)
        if self.args.part == "handsoff":
            self.positive("claude")
            self.notices("claude")
            self.notice_matrix("claude")
            self.notice_boundaries("claude")
            self.notice_versions_and_crashes("claude")
        self.fold_contracts()
        self.base_and_census()
        self.package_roundtrip()
        self.mutations()
        self.native_suites()
        total = self.passed + self.failed
        print("FAIL %d/%d" % (self.failed, total) if self.failed else "PASS %d/%d" % (self.passed, total))
        return bool(self.failed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wrappers", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--fixture-root", default=os.environ.get("TMPDIR") or "/tmp")
    parser.add_argument("--part", choices=("all", "claude", "codex", "handsoff"), default="all")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--base", help="read-only flat original base")
    parser.add_argument("--base-manifest", help="supplied original checksums")
    parser.add_argument("--package", help="staged install/undo package")
    parser.add_argument("--no-mutations", action="store_true")
    parser.add_argument("--fold-only", action="store_true", help="run CR-A3-1 behavioural regressions only")
    parser.add_argument("--native", action="store_true", help="include all three paired native suites")
    parser.add_argument("--native-suite", action="append", choices=("test_lane.sh","test_codex_lane.sh","test_handsoff.sh"),
                        help="run a named native suite separately within the harness time ceiling")
    parser.add_argument("--vault", help="read-only vault for the native lane suite")
    parser.add_argument("--hooks-dir", help="granted read-only hooks for the native supervisor suite")
    parser.add_argument("--native-fixture-root", help="explicit native fixture root outside /tmp, the vault and wrappers")
    parser.add_argument("--native-scratch-root", help="explicit native scratch subdirectory under /tmp")
    args = parser.parse_args()
    for name, source in (("provider", PROVIDER), ("successor", SUCCESSOR), ("bootstrap", BOOTSTRAP)):
        compile(source, "<fixture-" + name + ">", "exec")
    if not Path(args.fixture_root).is_dir() or not (Path(args.wrappers) / "lane.py").is_file():
        print("PROBE FAILED: fixture root or wrapper source is unavailable")
        return 2
    return Suite(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
