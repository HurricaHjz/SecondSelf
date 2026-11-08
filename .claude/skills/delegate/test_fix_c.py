#!/usr/bin/env python3
"""A27–A30 public fixtures: no network or real model starts.

All fixture writes live under a removed mktemp directory. Wrapper copies are read-only;
their byte manifests are compared at the end. Time ceilings are set by judgement, unmeasured.
"""
import argparse
import ast
import contextlib
import hashlib
import importlib.util
import io
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
from test_a3 import Fixture, Suite as A3Suite, POLICY_EVENTS, events_for, rows

STOPS = (
    "API Error: Can't reach the API server — check your internet or DNS (ENOTFOUND)",
    "API Error: connection refused (ECONNREFUSED)",
    "API Error: connection reset (ECONNRESET)",
    "API Error: request timed out (ETIMEDOUT)",
)
LIMIT = "Usage limit reached; resets at 5pm (UTC)"
MODEL_LIMIT = ("You've reached your Fable limit. Switch to another model, or manage usage "
               "credits at claude.ai/settings/usage, to continue.")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assistant(text="", model="fixture-model", identity="fresh", tool=False):
    blocks = ([{"type": "text", "text": text}] if text else [])
    if tool:
        blocks.append({"type": "tool_use", "id": identity, "name": "Read", "input": {}})
    return {"type": "assistant", "uuid": identity, "message": {
        "id": identity, "model": model, "stop_reason": "tool_use" if tool else "end_turn",
        "content": blocks, "usage": {"input_tokens": 0 if model.startswith("<synthetic") else 1,
                                      "output_tokens": 0 if model.startswith("<synthetic") else 1}}}


def result(text="Work completed.", error=False):
    return {"type": "result", "subtype": "error_during_execution" if error else "success",
            "is_error": error, "result": text}


def encoded(records):
    return "".join(json.dumps(row) + "\n" for row in records)


def manifest(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def manifest_sees_a_changed_byte(source, control, read=manifest):
    """The control behind a read-only proof: one byte changed in a scratch copy must change what
    `read` returns, so a manifest that cannot see a change cannot pass the proof beside it."""
    control.mkdir()
    target = control / source.name
    shutil.copyfile(source, target)
    target.chmod(0o644)
    unchanged = read(control)
    data = bytearray(target.read_bytes())
    data[0] ^= 1
    target.write_bytes(bytes(data))
    return bool(unchanged) and read(control) != unchanged


class Suite(A3Suite):
    def case(self, group, name, callback):
        if not self.selected(group) or self.args.case_match and self.args.case_match not in name:
            return
        fixture = Fixture(self.args.wrappers, self.args.fixture_root)
        try:
            condition, detail = callback(fixture)
            self.check(group, name, condition, {"detail": detail, **fixture.snapshot()})
        except (Exception, SystemExit) as exc:
            self.check(group, name, False, {"error": repr(exc), **fixture.snapshot()})
        finally:
            fixture.cleanup()

    def native(self, f, family, records, expected, cli=None, code=1, recovery=None,
               refusal=False, guard=None):
        f.scenario(family, records, exit_code=code, result=cli or result("", error=True),
                   wait=bool(guard))
        extra = ["--deadline-s", "1" if family == "claude" else "0.15"] if guard == "deadline" else []
        if recovery:
            proc, release, arrived = f.barrier(family, "outcome-saved", extra)
            proc.kill()
            out, err = proc.communicate(timeout=30)
            f.history.append({"command": proc.args, "returncode": proc.returncode,
                              "stdout": out, "stderr": err})
            journal = f.snapshot()["journals"][0]
            module = f.module()
            if recovery == "suffix":
                journal["evidence"] = {"settled": False}
                journal.pop("outcome", None)
                module.a3_save_journal(journal)
            elif recovery == "saved":
                Path(journal["boundary"]["path"]).unlink()
            command = f.command(family, "recover", ["--pass", arrived["pass_id"],
                                "--decision", "hold", "--reason", "fixture evidence reviewed"])
            public = f.run(command)
        else:
            public = f.run(f.command(family, extra=extra))
        snapshot = f.snapshot()
        journal = snapshot["journals"][0]
        close = journal.get("close") or {}
        expected_code = 0 if expected == "completed" else 6 if expected == "limit" else 3
        if recovery:
            expected_code = 3  # Orphan process result stays unknown or its saved public failure.
        positive = self.controls.get(family)
        count = 1 if refusal and not recovery else 0
        good = (public.returncode == expected_code and close.get("exit_class") == expected
                and snapshot["successor_start_count"] == count and positive)
        if expected == "network" or refusal:
            good = good and bool(close.get("network_signal")) and close.get("limit_signal") is None
        if expected == "limit":
            good = good and bool(close.get("limit_signal")) and close.get("network_signal") is None
        if guard:
            good = good and close.get("stop_cause") == guard
        if refusal:
            good = good and close.get("refusal_count") == 1 and bool(journal.get("notices"))
        if expected == "network" and not recovery:
            advice = f.run(f.command("claude", "advise"))
            good = (good and advice.returncode == 0 and "advise: resume" in advice.stdout
                    and "API answers" in advice.stdout)
        return bool(good), {"expected_class": expected, "expected_code": expected_code,
                            "actual_code": public.returncode, "positive_start_control": positive}

    def wrappers(self, family):
        for i, text in enumerate(STOPS):
            endings = (False, True) if family == "claude" else (False,)
            for trailing in endings:
                records = ([assistant(text, "<synthetic>")] if family == "claude" else
                           [{"type": "turn.failed", "error": {"message": text}}])
                if trailing:
                    records += [{"type": "system"}]
                for recovery in (None, "suffix"):
                    self.case("A27", f"{family} network {i} trailing={trailing} recovery={recovery}",
                              lambda f, r=records, mode=recovery:
                              self.native(f, family, r, "network", recovery=mode))
        if family == "claude":
            scenarios = [
                ("genuine limit", [assistant(LIMIT, "<synthetic>")], None, 1, "limit"),
                ("limit suffix", [assistant(LIMIT, "<synthetic>"), {"type": "system"}], None, 1, "limit"),
                ("later success", [assistant(STOPS[0], "<synthetic>"), assistant("done", identity="later")], result(), 0, "completed"),
                ("successful network prose", [assistant(STOPS[0])], result(STOPS[0]), 0, "completed"),
                ("successful limit prose", [assistant(LIMIT)], result(LIMIT), 0, "completed"),
                ("bare successful envelope", [assistant(STOPS[0], "<synthetic>")], result(), 0, "network"),
                ("CLI source beats synthetic", [assistant(LIMIT, "<synthetic>")], result(STOPS[0], True), 1, "network"),
                ("CLI limit beats network", [assistant(STOPS[0], "<synthetic>")], result(LIMIT, True), 1, "limit"),
                ("mixed selected source", [assistant(LIMIT + " " + STOPS[0], "<synthetic>")], None, 1, "limit"),
                ("non-outcomes", [assistant(STOPS[0], "<synthetic>"), {"type": "user"}, {"type": "attachment"}, {"type": "progress"}], None, 1, "network"),
                ("synthetic prefix", [assistant(STOPS[0], "<synthetic:error>")], None, 1, "network"),
                ("unnamed synthetic", [assistant("unknown", "<synthetic>")], None, 1, "limit"),
                ("empty synthetic", [assistant("", "<synthetic>")], None, 1, "limit"),
            ]
        else:
            failed = lambda text: {"type": "turn.failed", "error": {"message": text}}
            scenarios = [
                ("genuine limit", [failed(LIMIT)], None, 1, "limit"),
                ("later success", [failed(LIMIT)] + events_for("codex", "clean"), None, 0, "completed"),
                ("successful prose", [{"type": "item.completed", "item": {"type": "agent_message", "text": LIMIT + STOPS[0]}}, {"type": "turn.completed"}], None, 0, "completed"),
                ("old retry limit", [{"type": "error", "message": LIMIT}, failed(STOPS[0])], None, 1, "network"),
                ("blank final failure", [failed(LIMIT), failed("")], None, 1, "failed"),
                ("long terminal error", [failed("x" * 400 + STOPS[0])], None, 1, "network"),
                ("long structured error", [{"type": "turn.failed", "error": {"a": "x" * 400, "z": STOPS[0]}}], None, 1, "network"),
                ("mixed terminal source", [failed(STOPS[0] + " " + LIMIT)], None, 1, "limit"),
            ]
        for name, records, cli, code, expected in scenarios:
            self.case("A28", family + " " + name, lambda f, r=records, c=cli, rc=code, e=expected:
                      self.native(f, family, r, e, c, rc))
        # Model names are fixture vocabulary; the predicate must also span newlines and
        # recognise usage before limit. Each selected source has a drop-only control.
        for text_name, text in (("model", MODEL_LIMIT),
                                ("multiline", MODEL_LIMIT.replace(". Switch", ".\nSwitch")),
                                ("usage-first", "Usage credits exhausted. You've reached your Fable limit."),
                                ("mixed", MODEL_LIMIT + " " + STOPS[0]),
                                ("other model", MODEL_LIMIT.replace("Fable", "Opus")),
                                ("drop control", STOPS[0])):
            expected = "network" if text_name == "drop control" else "limit"
            sources = ("synthetic", "cli", "stderr", "recovery") if family == "claude" else ("terminal", "recovery")
            for source in sources:
                def model_case(f, text=text, source=source, expected=expected):
                    if family == "claude":
                        records = [assistant(text, "<synthetic:error>")]
                        cli = None
                        if source in ("cli", "stderr"):
                            records = [assistant("partial work")]
                        if source == "cli":
                            cli = result(text, True)
                        if source == "stderr":
                            # One terminal stderr record; preserve the newline case in the CLI
                            # and synthetic sources, where the complete source is available.
                            provider = f.root / "bin/claude"
                            original = provider.read_text()
                            anchor = 'raise SystemExit(scenario.get("exit",0))'
                            assert original.count(anchor) == 1
                            provider.write_text(original.replace(anchor,
                                "print(" + repr(text.replace("\n", " ")) + ",file=sys.stderr)\n" + anchor))
                    else:
                        records = [{"type": "turn.failed", "error": {"message": text}}]
                        cli = None
                    good, detail = self.native(f, family, records, expected, cli,
                                               recovery="suffix" if source == "recovery" else None)
                    close = f.snapshot()["journals"][0].get("close", {})
                    signal = close.get("limit_signal" if expected == "limit" else "network_signal")
                    selected = text.replace("\n", " ") if source == "stderr" else text
                    # A generic zero-usage fallback loses the model scope; retain the selected text.
                    return good and signal == selected, {**detail, "signal": signal, "selected": selected}
                self.case("A28", family + " model-scope " + text_name + " " + source, model_case)
        # E8: successful prose never becomes a stop, even with model-scope words.
        records = ([assistant(MODEL_LIMIT)] if family == "claude" else
                   [{"type": "item.completed", "item": {"type": "agent_message", "text": MODEL_LIMIT}},
                    {"type": "turn.completed"}])
        self.case("A28", family + " model-scope successful prose control", lambda f:
                  self.native(f, family, records, "completed", result(MODEL_LIMIT), 0))
        if family == "claude":
            self.case("A28", "Claude stderr priority and complete text", self.stderr_priority)
            self.case("A28", "cold network resume gate with limit and ordinary controls", self.resume_gate)
            for damaged in ({"type": "assistant"}, {"type": "assistant", "message": {"content": []}}):
                self.case("A28", "malformed assistant preserves candidate " + json.dumps(damaged),
                          lambda f, d=damaged: self.malformed(f, [assistant(STOPS[0], "<synthetic>"), d], "network"))
            self.case("A28", "malformed assistant alone is uncertain", lambda f:
                      self.malformed(f, [{"type": "assistant"}], "evidence-incomplete"))
        self.case("A28", family + " beat uses terminal network evidence", lambda f: self.beat(f, family))
        self.case("A29", family + " orphan network cannot authorise move", lambda f: self.no_network_move(f, family))
        for refusal in (False, True):
            records = (events_for(family, "terminal") if refusal else []) + (
                [assistant(STOPS[0], "<synthetic>", identity="diagnostic")] if family == "claude" else
                [{"type": "turn.failed", "error": {"message": STOPS[0]}}])
            for guard in (None, "deadline"):
                expected = "refusal" if refusal else ("deadline" if guard else "network")
                self.case("A29", f"{family} network refusal={refusal} guard={guard}",
                          lambda f, r=records, e=expected, ref=refusal, g=guard:
                          self.native(f, family, r, e, refusal=ref, guard=g))
            self.case("A29", f"{family} saved network refusal={refusal}",
                      lambda f, r=records, ref=refusal:
                      self.native(f, family, r, "refusal" if ref else "network",
                                  recovery="saved", refusal=ref))

    def refusal_composition(self):
        recorded = json.loads(json.dumps(POLICY_EVENTS))
        recorded[-1]["error"]["message"] += " " + STOPS[0]
        shapes = [("recorded failed-turn refusal", recorded, True)]
        for code in ("refusal", "safety_refusal"):
            shapes.append(("unrecognised error code " + code,
                [{"type": "turn.failed", "error": {"code": code, "message": STOPS[0]}}], False))
        shapes.append(("unrecognised top-level stop reason",
            [{"type": "turn.failed", "stop_reason": "refusal", "error": {"message": STOPS[0]}}], False))
        shapes.append(("quoted policy text",
            [{"type": "item.completed", "item": {"type": "agent_message", "id": "quote",
              "text": POLICY_EVENTS[0]["message"]}}, {"type": "turn.failed", "error": {"message": STOPS[0]}}], False))
        for name, records, refusal in shapes:
            # Fold 1f deliberately removed recognition of three unrecorded structured shapes.
            self.case("A29", "1f composition with network: " + name,
                      lambda f, r=records, ref=refusal:
                      self.native(f, "codex", r, "refusal" if ref else "network", refusal=ref))

    def stderr_priority(self, f):
        provider = f.root / "bin/claude"
        source = provider.read_text()
        anchor = 'raise SystemExit(scenario.get("exit",0))'
        assert source.count(anchor) == 1
        provider.write_text(source.replace(anchor, 'print("Usage limit reached\\nAPI Error: connection reset (ECONNRESET)",file=sys.stderr)\n' + anchor))
        good, detail = self.native(f, "claude", [assistant("ordinary report")], "network")
        return good, detail

    def malformed(self, f, records, expected):
        good, detail = self.native(f, "claude", records, expected, result(), 0)
        journal = f.snapshot()["journals"][0]
        return good and not journal["close"].get("evidence_complete") and bool(journal["evidence"].get("uncertainty")), detail

    def resume_gate(self, f):
        module = f.module()
        tree = ast.parse((Path(self.args.wrappers) / "lane.py").read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "cmd_resume")
        start = next(i for i, n in enumerate(function.body) if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "after_limit" for t in n.targets))
        end = next(i for i in range(start, len(function.body)) if isinstance(function.body[i], ast.If))
        code = compile(ast.Module(body=function.body[start:end + 1], type_ignores=[]), "<resume-gate>", "exec")
        observed = []
        def deny(*a):
            raise RuntimeError("held")
        for cls, factor, expected in (("network", 2, True), ("limit", 2, True), ("budget", 2, False), ("budget", 0.5, True)):
            scope = {"closed": {"exit_class": cls}, "age": module.RESUME_WINDOW_S * factor,
                     "RESUME_WINDOW_S": module.RESUME_WINDOW_S, "args": SimpleNamespace(run="fixture", lane="case"),
                     "age_src": "fixture", "beat": False, "die": deny}
            try:
                exec(code, scope)
                allowed = True
            except RuntimeError:
                allowed = False
            observed.append([cls, factor, allowed, expected])
        return all(r[-2] == r[-1] for r in observed), observed

    def beat(self, f, family):
        f.scenario(family, events_for(family, "clean"))
        clean = f.run(f.command(family))
        records = ([assistant(STOPS[0], "<synthetic>")] if family == "claude" else
                   [{"type": "turn.failed", "error": {"message": STOPS[0]}}])
        f.scenario(family, records, exit_code=1, result=result(STOPS[0], True))
        public = f.run(f.command(family, "resume", ["--beat"]))
        snap = f.snapshot()
        beats = [r for r in snap["record"] if r.get("event") == "hold-beat"]
        return (clean.returncode == 0 and public.returncode == 3 and len(beats) == 1
                and beats[0].get("exit_class") == "network" and bool(beats[0].get("network_signal"))
                and beats[0].get("limit_signal") is None and snap["successor_start_count"] == 0
                and self.controls.get(family)), beats

    def no_network_move(self, f, family):
        records = ([assistant(STOPS[0], "<synthetic>")] if family == "claude" else
                   [{"type": "turn.failed", "error": {"message": STOPS[0]}}])
        f.scenario(family, records, exit_code=1, result=result(STOPS[0], True))
        proc, release, arrived = f.barrier(family, "outcome-saved")
        proc.kill()
        out, err = proc.communicate(timeout=30)
        f.history.append({"command": proc.args, "returncode": proc.returncode, "stdout": out, "stderr": err})
        public = f.run(f.command(family, "recover", ["--pass", arrived["pass_id"], "--decision", "move",
                                                    "--reason", "fixture negative control"]))
        return (public.returncode == 2 and "no refusal or confirmed fallback" in public.stderr
                and f.snapshot()["successor_start_count"] == 0 and self.controls.get(family)), None

    def supervisor(self, f, text=STOPS[0], model="<synthetic>", envelope=None, activity=None,
                   previous=60, cancel=None, missing=False, limit=False, repeats=1, mutate=None):
        if limit:
            text = LIMIT
        h = load(Path(self.args.wrappers) / "handsoff.py", "fixture_supervisor")
        lane = f.module()
        transcript, output = f.root / "head.jsonl", f.root / "head.out"
        prefix = assistant("old work", identity="old")
        transcript.write_text(encoded([prefix]))
        output.write_text(encoded([result("old stdout")]))
        f.record.write_text(encoded([{"event": "run-open", "run": "fixture"}]))
        starts, prompts, probes, resets = [], [], [], []
        now = [1000.0]
        class Input(io.BytesIO):
            def close(self):
                prompts.append(self.getvalue().decode())
                super().close()
        class Process:
            def __init__(self, cmd, **kwargs):
                self.pid = 41000 + len(starts)  # Fixture identity sequence, not an OS process.
                self.stdin = Input()
                starts.append({"command": cmd, "cwd": kwargs.get("cwd"), "at": now[0],
                               "probes_before_start": len(probes)})
        args = SimpleNamespace(run="fixture", tick_s=30, wait_s=0, harness_bin="fixture-harness",
                               effort="max", config_dir=None, viewer_opened=True, model="fixture-model")
        h._LANE = (lane, str(Path(self.args.wrappers) / "lane.py"), None)
        if mutate:
            mutate(h)
        waited = [0]
        def wait_head(*_):
            waited[0] += 1
            if waited[0] > repeats:
                h.append_record(str(f.record), h.event("fixture", "run-close"))
                return 0
            content = []
            if activity in ("text", "tool", "empty"):
                content.append(assistant("new work" if activity == "text" else "", tool=activity == "tool"))
            if activity == "replay":
                content.append(prefix)
            content.append(assistant(text, model, identity="diagnostic-" + str(waited[0])))
            with transcript.open("a") as handle:
                handle.write(encoded(content))
            with output.open("a") as handle:
                handle.write(encoded([envelope or result(text, True)]))
            if activity in ("head-event", "foreign-event", "heartbeat"):
                pid = starts[-1]["pid"]
                h.append_record(str(f.record), h.event("fixture", "heartbeat" if activity == "heartbeat" else "observation",
                                caller_pid=pid if activity != "foreign-event" else pid + 1))
            if activity == "ledger":
                pid = starts[-1]["pid"]
                with patch.object(h, "head_event_caller", return_value=(pid, "head-command"), create=True):
                    h.cmd_ledger(SimpleNamespace(run="fixture", record=str(f.record), observation="head bookkeeping",
                                 phase=None, dry_run=False, notice_id=None, notice_version=None, notice_sha256=None))
            return 1 if envelope is None else 0
        def connectivity():
            probes.append(now[0])
            if cancel == "owner":
                Path(h.supervisor_stop_file("fixture")).parent.mkdir(parents=True, exist_ok=True)
                Path(h.supervisor_stop_file("fixture")).touch()
            elif cancel == "close":
                h.append_record(str(f.record), h.event("fixture", "run-close"))
            elif cancel == "manual":
                with transcript.open("a") as handle:
                    handle.write(encoded([assistant("manual work", identity="manual")]))
            return len(probes) > 2 if cancel == "outage" else True
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, f.env))
            for name, replacement in {
                    "transcript_for": lambda sid: str(transcript), "vault_root": lambda: str(f.root),
                    "launch_model": lambda *a: ("fixture-model", "fixture"),
                    "head_context": lambda *a: {"context": 1000}, "open_console_if_dark": lambda *a: None,
                    "remainder": lambda *a: (1, "fixture budget"),
                    "wait_head": wait_head, "run_on_limit": lambda *a: ("resume", "fixture", None),
                    "wait_for_reset": lambda *a: (resets.append("reset") or "ok", "fixture reset", 0),
                    "resume_in_place": lambda *a: True,
                    "successor_path": lambda *a, **k: None,
                    "connectivity_check": connectivity}.items():
                stack.enter_context(patch.object(h, name, replacement, create=True))
            stack.enter_context(patch.object(h.subprocess, "Popen", Process))
            stack.enter_context(patch.object(h.time, "time", lambda: now[0]))
            stack.enter_context(patch.object(h.time, "monotonic", lambda: now[0]))
            stack.enter_context(patch.object(h.time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay)))
            stack.enter_context(contextlib.redirect_stdout(stdout))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            # Exercise the real constructor to capture the boundary before any new transcript work.
            kwargs = {"network_delay_s": previous} if "network_delay_s" in __import__("inspect").signature(h.resume_head).parameters else {}
            constructed = h.resume_head(args, str(f.record), "fixture-session", 1, "fixture", str(output),
                                        {"context": 1000} if limit else {}, "budget" if previous is None else "network", 0, "fixture", now[0], **kwargs)
            if not constructed:
                raise RuntimeError("real constructor did not return a fixture process")
            proc, out, offset, start = constructed
            starts[-1]["pid"] = proc.pid
            # Record each later constructor's PID too, without replacing its implementation.
            native_resume = h.resume_head
            def recorded_resume(*a, **k):
                resumed = native_resume(*a, **k)
                if resumed:
                    starts[-1]["pid"] = resumed[0].pid
                return resumed
            stack.enter_context(patch.object(h, "resume_head", recorded_resume))
            public = h.supervise_loop(args, str(f.record), None if missing else "fixture-session",
                                      proc, proc.pid, out, offset, start, now[0])
        f.history.append({"command": ["supervise_loop", "fixture-session"], "returncode": public,
                          "stdout": stdout.getvalue(), "stderr": stderr.getvalue()})
        recorded = rows(f.record)
        delays = [r["delay_s"] for r in recorded if r.get("event") == "network-backoff"]
        events = [r for r in recorded if r.get("what") == "head exited"]
        expected = []
        if not missing:
            current = previous
            for _ in range(repeats):
                current = 0 if activity in ("text", "tool", "head-event", "ledger") or current is None else min(1800, max(60, current * 2))
                expected.append(current)
        count = 0 if cancel in ("owner", "close", "manual") or missing else min(repeats, 1)
        if repeats > 1:
            expected = expected[:2]  # Two completed no-work resumes reach the approved stop.
        good = (len(starts) - 1 == count and self.controls.get("claude")
                and all("--resume" in s["command"] and "fixture-session" in s["command"]
                        and "fixture-model" in s["command"] and "json" in s["command"] for s in starts))
        good = good and (public == 1 if missing or repeats > 1 else public == 0)
        if repeats > 1:
            good = good and any(r.get("reason") == "network-no-progress" for r in recorded)
        if limit:
            good = good and not probes and not delays and resets == ["reset"]
            good = good and all(r.get("exit_class") == "limit" for r in events[:-1])
        elif not cancel and not missing:
            good = good and delays == expected and all(r.get("exit_class") == "network" for r in events[:-1])
        if cancel:
            good = good and bool(probes)
        if cancel == "outage":
            good = good and probes[:3] == [1000.0, 1030.0, 1060.0]
            good = good and starts[-1]["at"] == 1060.0 + expected[0]
            good = good and starts[-1]["probes_before_start"] == 3
        elif not cancel and not missing and not limit:
            elapsed = 1000.0
            for started, delay in zip(starts[1:], expected):
                elapsed += delay
                good = good and started["at"] == elapsed
        return bool(good), {"delays": delays, "expected": expected, "starts": starts,
                            "prompts": prompts, "probes": probes, "public_returncode": public}

    def supervisor_cases(self):
        for model in ("<synthetic>", "<synthetic:error>"):
            for i, text in enumerate(STOPS):
                for envelope in (None, result(text), result()):
                    name = f"diagnostic {model} {i} envelope={None if envelope is None else envelope['result']}"
                    self.case("A30", name, lambda f, t=text, m=model, e=envelope:
                              self.supervisor(f, t, m, e))
        for activity in ("text", "tool", "empty", "head-event", "foreign-event", "heartbeat", "ledger", "replay"):
            texts = STOPS if activity in ("text", "tool") else STOPS[:1]
            for i, text in enumerate(texts):
                self.case("A30", f"transcript progress {activity} {i}",
                          lambda f, t=text, a=activity: self.supervisor(f, t, activity=a))
        for cancel in ("owner", "close", "manual", "outage"):
            self.case("A30", "wait " + cancel, lambda f, c=cancel: self.supervisor(f, cancel=c))
        self.case("A30", "unknown session holds", lambda f: self.supervisor(f, missing=True))
        self.case("A30", "repeated no-work sequence stops after two resumes", lambda f:
                  self.supervisor(f, repeats=8))
        self.case("A30", "usage reset preserved", lambda f: self.supervisor(f, limit=True))
        for previous in (0, 60, 120, 240, 480, 960, 1800):
            self.case("A30", "backoff step from " + str(previous), lambda f, d=previous:
                      self.supervisor(f, previous=d))
        self.case("A30", "connectivity bounded and closed", self.connectivity)
        self.case("A30", "event producer attribution", self.producer)

    def mutations(self):
        def mutate(h, kind):
            source = inspect.getsource(h.network_progress)
            if kind == "exact-string":
                before, after = 'model.startswith("<synthetic")', 'model == "<synthetic>"'
            elif kind == "replay":
                before, after = ' or identity in seen', ''
            elif kind == "stdout":
                before, after = 'boundary = resumed.get("transcript_boundary")', 'boundary = output_boundary(out, offset)'
                def output_boundary(out, offset):
                    boundary = h._LANE[0].a3_boundary(out)
                    boundary["size"] = offset
                    boundary["prefix_sha256"] = hashlib.sha256(Path(out).read_bytes()[:offset]).hexdigest()
                    return boundary
                h.output_boundary = output_boundary
            else:
                before = '    resumed = events[start] if 0 <= start < len(events) else {}\n'
                after = '''    with open(out, "rb") as handle:
        handle.seek(offset)
        for raw in handle:
            row = json.loads(raw)
            if row.get("type") == "result" and row.get("subtype") == "success" and row.get("result"):
                return True
''' + before
            if source.count(before) != 1:
                raise RuntimeError("PROBE FAILED: mutant anchor changed")
            exec(compile(source.replace(before, after), "<progress-mutant>", "exec"), h.__dict__)
        matrix = []
        for text in STOPS:
            matrix.append(("exact-string", {"text": text, "model": "<synthetic:error>"}))
            for model in ("<synthetic>", "<synthetic:error>"):
                for envelope in (result(text), result()):
                    matrix.append(("envelope", {"text": text, "model": model, "envelope": envelope}))
            for activity in ("text", "tool"):
                matrix.append(("stdout", {"text": text, "activity": activity}))
        matrix.append(("replay", {"activity": "replay"}))
        for i, (kind, options) in enumerate(matrix):
            def run_mutant(f, kind=kind, options=options):
                good, detail = self.supervisor(f, mutate=lambda h: mutate(h, kind), **options)
                return not good and bool(detail.get("starts")), {"mutant_caught": not good, **detail}
            self.case("M30", f"{kind} mutant {i}", run_mutant)

    def connectivity(self, f):
        h = load(Path(self.args.wrappers) / "handsoff.py", "connectivity_fixture")
        cases = []
        for status in (200, 401, 404, 499, 500, 503, ConnectionRefusedError(), TimeoutError(), h.http.client.HTTPException()):
            calls = []
            class Connection:
                def __init__(self, host, port, timeout): calls.append(["connect", host, port, timeout])
                def request(self, *a, **k): calls.append(["request", list(a), k])
                def getresponse(self):
                    if isinstance(status, Exception): raise status
                    return SimpleNamespace(status=status)
                def close(self): calls.append(["close"])
            with patch.object(h.http.client, "HTTPSConnection", Connection), patch.dict(os.environ, {"ANTHROPIC_BASE_URL": "https://provider.invalid/model?secret=unused"}):
                answer = h.connectivity_check()
            expected = isinstance(status, int) and 200 <= status < 500
            cases.append({"status": str(status), "answer": answer, "calls": calls,
                          "pass": answer == expected and calls == [["connect", "provider.invalid", None, 10], ["request", ["HEAD", "/"], {}], ["close"]]})
        return all(c["pass"] for c in cases), cases

    def producer(self, f):
        h = load(Path(self.args.wrappers) / "handsoff.py", "producer_fixture")
        h._LANE = (f.module(), str(Path(self.args.wrappers) / "lane.py"), None)
        # Abstract PIDs reproduce the critic's measured command -> session-leading shell -> harness.
        fixtures = [
            ("same session", {43: (42, "/bin/sh", 1, 1), 42: (1, h.HARNESS, 1, 1)}, 1, 1, 42),
            ("measured shell session", {43: (42, "/bin/zsh", 43, 43), 42: (1, h.HARNESS, 42, 42)}, 43, 43, 42),
            ("detached worker", {43: (42, "python", 43, 43), 42: (1, h.HARNESS, 42, 42)}, 43, 43, None),
            ("non-leading shell", {43: (42, "/bin/sh", 44, 44), 42: (1, h.HARNESS, 42, 42)}, 44, 44, None),
            ("two session changes", {44: (43, "/bin/sh", 44, 44), 43: (42, "/bin/sh", 43, 43),
                                     42: (1, h.HARNESS, 42, 42)}, 44, 44, None),
            ("foreign shell group", {43: (42, "/bin/sh", 43, 45), 42: (1, h.HARNESS, 42, 42)}, 43, 43, None),
            ("detached worker in same session", {43: (42, "python", 1, 1), 42: (1, h.HARNESS, 1, 1)}, 1, 1, None),
            ("foreign harness group", {43: (42, "/bin/sh", 1, 1), 42: (1, h.HARNESS, 1, 2)}, 1, 1, None),
        ]
        results = []
        for name, topology, session, group, expected in fixtures:
            parent = next(iter(topology))
            with patch.dict(os.environ, f.env), \
                 patch.object(h.os, "getppid", return_value=parent), \
                 patch.object(h, "ps_row", side_effect=lambda pid: (pid, *topology[pid][:2]) if pid in topology else None), \
                 patch.object(h.os, "getsid", side_effect=lambda pid: session if pid == 0 else topology[pid][2]), \
                 patch.object(h.os, "getpgid", side_effect=lambda pid: group if pid == 0 else topology[pid][3]):
                actual = h.head_event_caller()[0]
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    public = h.cmd_ledger(SimpleNamespace(run="fixture", record=str(f.record), observation=name,
                                         phase=None, dry_run=False, notice_id=None, notice_version=None, notice_sha256=None))
            stamped = rows(f.record)[-1].get("caller_pid")
            results.append({"shape": name, "actual": actual, "expected": expected, "stamped": stamped,
                            "returncode": public, "stdout": output.getvalue(),
                            "pass": actual == stamped == expected and public == 0})
        return all(r["pass"] for r in results), results

    def parser_checks(self):
        def probe(f, mutant=False):
            command = [sys.executable, "-B", str(Path(__file__).with_name("probe_fix_c.py")),
                       "--root", str(self.args.wrappers), "--fixtures",
                       str(Path(__file__).with_name("fixtures-fix-c.json"))]
            if mutant:
                command.append("--mutant-pair")
            public = f.run(command)
            expected = "FAIL 4/10" if mutant else "PASS 10/10"
            return public.returncode == (1 if mutant else 0) and public.stdout.strip().endswith(expected), expected
        self.case("A27", "eight parser-to-classifier cases", probe)
        self.case("M27", "paired-preservation mutant", lambda f: probe(f, True))

    def diagnostic_contract(self):
        def verify(f):
            script = Path(__file__).with_name("probe_fix_c.py")
            pattern = re.compile(r'\.(?:write_(?:text|bytes)|unlink|mkdir|rename|touch|chmod)\s*\(|\bopen\([^\n]*,[ \t]*[\x27\"][wax+]')
            hits = len(pattern.findall(script.read_text()))
            planted = len(pattern.findall('open("fixture", "w")'))
            command = [sys.executable, "-B", str(script), "--root", str(f.root / "absent"),
                       "--fixtures", str(Path(__file__).with_name("fixtures-fix-c.json"))]
            public = f.run(command)
            return (hits == 0 and planted == 1 and public.returncode == 2
                    and public.stdout.startswith("PROBE FAILED:")), {"write_pattern_hits": hits, "positive_hits": planted}
        self.case("READ-ONLY", "diagnostic source grep and broken premise", verify)

    def run(self):
        families = ("claude", "codex") if self.args.part == "all" else (self.args.part,)
        self.positive("claude")
        if "codex" in families:
            self.positive("codex")
        for family in families:
            if family in ("claude", "codex"):
                self.wrappers(family)
        if self.args.part in ("all", "codex"):
            self.refusal_composition()
        if self.args.part in ("all", "claude"):
            self.parser_checks()
        if self.args.part in ("all", "handsoff"):
            self.supervisor_cases()
            self.mutations()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wrappers", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--fixture-root", type=Path, default=os.environ.get("TMPDIR"))
    parser.add_argument("--part", choices=("all", "claude", "codex", "handsoff"), default="all")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--case-match", default="")
    args = parser.parse_args()
    if not args.fixture_root or not args.fixture_root.is_dir() or not (args.wrappers / "lane.py").is_file():
        print("PROBE FAILED: wrapper source or isolated fixture root missing")
        return 2
    scratch = Path(subprocess.check_output(["mktemp", "-d", str(args.fixture_root / "fixc.XXXXXX")], text=True).strip())
    original = args.wrappers.resolve()
    copy = scratch / "sources"
    try:
        shutil.copytree(original, copy)
        for p in copy.rglob("*"):
            p.chmod(0o555 if p.is_dir() else 0o444)
        copy.chmod(0o555)
        before = manifest(copy)
        args.wrappers, args.fixture_root = copy, scratch
        suite = Suite(args)
        suite.run()
        # The final proof runs independently of the selected behavioural group.
        selected, matched = args.only, args.case_match
        args.only, args.case_match = [], ""
        suite.diagnostic_contract()
        args.only, args.case_match = selected, matched
        suite.check("CONTROL+", "the checksum manifest sees one changed byte in a scratch copy",
                    manifest_sees_a_changed_byte(copy / "lane.py", scratch / "manifest-control"))
        suite.check("CONTROL+", "a stub manifest returning an empty dictionary fails that control",
                    not manifest_sees_a_changed_byte(copy / "lane.py", scratch / "manifest-control-stub", lambda root: {}))
        suite.check("READ-ONLY", "wrapper byte manifest unchanged", before == manifest(copy), {"files": len(before)})
        total = suite.passed + suite.failed
        print("FAIL %d/%d" % (suite.failed, total) if suite.failed else "PASS %d/%d" % (total, total))
        return 1 if suite.failed else 0
    finally:
        for p in copy.rglob("*"):
            p.chmod(0o755 if p.is_dir() else 0o644)
        if copy.exists(): copy.chmod(0o755)
        shutil.rmtree(scratch)


if __name__ == "__main__":
    raise SystemExit(main())
