#!/usr/bin/env python3
"""Public resume cases with fake model, provider and clock boundaries.

Fixture writes stay under a removed mktemp directory. Source copies are read-only.
The command reports to stdout only; it never uses a real provider or run store.
Fixture values and failure timeouts are set by judgement, unmeasured.
"""
import argparse
import contextlib
import io
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
from test_a3 import Fixture, events_for, rows
from test_fix_c import Suite as BaseSuite, STOPS, LIMIT, MODEL_LIMIT, assistant, result, encoded, load, manifest, manifest_sees_a_changed_byte


class Suite(BaseSuite):
    def loop(self, f, sequence, outage=0, limit=False, cancel=None, inherited=None,
             start_failure=False, context=1000, on_limit="resume", invalid_origin=None,
             model_text=None, model_probe=False, real_successor=False, hold=False,
             successor_guard=None):
        """Run the complete supervisor; replace only external process/meter/clock boundaries."""
        h = load(Path(self.args.wrappers) / "handsoff.py", "resume_fixture_supervisor")
        lane = f.module()
        if self.args.mutant_progress:
            source = inspect.getsource(h.network_resume_evidence)
            anchor = '"yes" if worked else "unknown" if uncertain else "no"'
            changed = ('"yes" if worked else "no"' if self.args.mutant_progress == "no" else
                       '"yes" if worked or uncertain else "no"')
            if source.count(anchor) != 1:
                raise RuntimeError("PROBE FAILED: progress mutant anchor")
            exec(compile(source.replace(anchor, changed), "<progress-mutant>", "exec"), h.__dict__)
        h._LANE = (lane, str(Path(self.args.wrappers) / "lane.py"), None)
        transcript, output = f.root / "head.jsonl", f.root / "head.out"
        transcript.write_text(encoded([assistant("work already on disk", identity="prefix")]))
        output.write_text("")
        (f.root / "handoff.md").write_text("Fixture hand-off with saved work.\n")
        initial = {"event": "run-resume" if real_successor else "head-successor",
                   "session_id": "fixture-session", "pid": 41000}
        f.record.write_text(encoded([{"event": "run-open", "run": "fixture"}, initial]))
        if hold:
            h.append_record(str(f.record), h.event("fixture", "hold", lane="held-helper", cap=1))
        held_at_start = list(h.open_holds(rows(f.record)))
        starts, probes, resets, successors, prompts, usage_probes = [], [], [], [], [], []
        clock, turn = [1000.0], [0]
        class Input(io.BytesIO):
            def close(self):
                prompts.append(self.getvalue().decode())
                super().close()
        class Process:
            def __init__(self, command, **kwargs):
                if start_failure and "--resume" in command:
                    raise OSError("fixture model executable could not start")
                self.pid = 41001 + len(starts)  # Fixture identities, never operating-system PIDs.
                self.stdin = Input()
                starts.append({"command": command, "pid": self.pid, "at": clock[0],
                               "probes_before_start": len(probes)})
        args = SimpleNamespace(run="fixture", tick_s=30, wait_s=0, harness_bin="fixture-harness",
                               effort="max", config_dir=None, viewer_opened=True, model="fixture-model",
                               handoff=str(f.root / "handoff.md"), meter_line="fixture",
                               reset_at=None, probe=model_probe, probe_interval_s=30, max_wait_s=300)
        def wait_head(*unused):
            index = turn[0]
            turn[0] += 1
            if index >= len(sequence):
                raise RuntimeError("PROBE FAILED: fixture schedule exhausted")
            activity = sequence[index]
            if activity == "close":
                h.append_record(str(f.record), h.event("fixture", "run-close"))
                return 0
            text = model_text or (LIMIT if activity == "limit" or limit else STOPS[0])
            records = []
            if activity in ("text", "tool", "empty", "unknown", "missing-boundary", "bad-record", "malformed", "thinking"):
                records.append(assistant("new work" if activity == "text" else "",
                                         identity="response-" + str(index), tool=activity == "tool"))
            if activity == "thinking":
                records[-1]["message"]["content"] = [{"type": "thinking", "thinking": "fixture reasoning"}]
            if activity == "replay":
                records.append(assistant("work already on disk", identity="prefix"))
            records.append(assistant(text, "<synthetic:error>", identity="diagnostic-" + str(index)))
            with transcript.open("a") as handle:
                handle.write(encoded(records))
            with output.open("a") as handle:
                handle.write(encoded([result(text, True)]))
            if activity in ("unknown", "missing-boundary"):
                record = rows(f.record)
                resumed = next(r for r in reversed(record) if r.get("event") == "head-resumed")
                if activity == "unknown":
                    resumed["transcript_boundary"]["prefix_sha256"] = "corrupt-fixture-digest"
                else:
                    resumed.pop("transcript_boundary", None)
                f.record.write_text(encoded(record))
            if activity == "malformed":
                with transcript.open("a") as handle:
                    handle.write("{unparseable fixture record\n")
            if activity == "bad-record":
                with f.record.open("a") as handle:
                    handle.write("{unparseable fixture event\n")
            if activity in ("gone", "unparseable", "torn"):
                if activity == "gone":
                    transcript.unlink()
                elif activity == "unparseable":
                    transcript.write_text("{unparseable fixture transcript\n")
                else:
                    with transcript.open("a") as handle:
                        handle.write("{torn fixture tail\n")
            if activity == "head-event":
                h.append_record(str(f.record), h.event("fixture", "observation",
                                caller_pid=starts[-1]["pid"] if starts else 41000))
            return 1
        def connectivity():
            probes.append({"at": clock[0], "turn": turn[0]})
            if cancel == "owner":
                Path(h.supervisor_stop_file("fixture")).touch()
            elif cancel == "close":
                h.append_record(str(f.record), h.event("fixture", "run-close"))
            elif cancel == "manual":
                with transcript.open("a") as handle:
                    handle.write(encoded([assistant("manual work", identity="manual")]))
            return sum(p["turn"] == turn[0] for p in probes) > outage
        def successor(a, path, budget, t0, watch=None):
            # The real successor_path records its exit; fake only the fresh head launch.
            record = rows(f.record)
            previous = next(r for r in reversed(record) if r.get("event") == "head-exit")
            sid = "fixture-successor-" + str(len(successors) + 1)
            proc = Process(["fixture-harness", "--session-id", sid, "--model", "fixture-model"])
            successors.append({"class": previous["exit_class"], "band": previous["band"], "session": sid})
            transcript.write_text(encoded([assistant("saved hand-off", identity=sid)]))
            h.append_record(path, h.event("fixture", "head-successor", session_id=sid, pid=proc.pid))
            return proc, sid, str(output), output.stat().st_size, len(rows(f.record)) - 1
        def start_head(a, path, budget, out, t0, watch=None):
            return successor(a, path, budget, t0, watch)
        native_succeed = h.succeed_exit
        def guarded_successor(a, path, budget, t0, watch=None):
            if successor_guard == "duplicate":
                h.append_record(path, h.event("fixture", "head-successor", session_id="other-supervisor"))
            return native_succeed(a, path, budget, t0, watch)
        def usage_probe(*unused):
            usage_probes.append("fake usage probe")
            return True, "fixture usage probe"
        def sleep(delay):
            clock[0] += delay
            # Fixture bound only: detect an old unbounded invalid-origin wait without hanging.
            if clock[0] > 1000 + 100000:
                raise RuntimeError("PROBE FAILED: invalid probe kept waiting past the fixture bound")
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, f.env))
            stack.enter_context(patch.dict(os.environ, {"AIMYTH_MAX_SUCCESSORS": str(h.MAX_SUCCESSORS_DEFAULT)}))
            if invalid_origin is not None:
                stack.enter_context(patch.dict(os.environ, {"ANTHROPIC_BASE_URL": invalid_origin}))
            for name, replacement in {
                "transcript_for": lambda sid: str(transcript), "vault_root": lambda: str(f.root),
                "launch_model": lambda *a: ("fixture-model", "fixture"),
                "head_context": lambda *a: {"context": context, "source": "fixture meter",
                    "percent": context * 100 // h.window() if context is not None else None,
                    "band": h.band_edge(context, h.window(), h.edges()) if context is not None else None},
                "meter_line": lambda *a: "fixture meter",
                "open_console_if_dark": lambda *a: None, "remainder": lambda *a: (1, "fixture budget"),
                "wait_head": wait_head, "run_on_limit": lambda *a: (on_limit, "fixture", None),
                **({"wait_for_reset": lambda *a: (resets.append("reset") or "ok", "fixture reset", 0)}
                   if model_text is None else {}),
                "probe": usage_probe,
                **({"start_head": start_head, "succeed_exit": guarded_successor} if real_successor
                   else {"succeed_exit": successor}),
                **({"connectivity_check": connectivity} if invalid_origin is None else {}),
            }.items():
                stack.enter_context(patch.object(h, name, replacement))
            stack.enter_context(patch.object(h.subprocess, "Popen", Process))
            stack.enter_context(patch.object(h.http.client, "HTTPSConnection",
                side_effect=RuntimeError("PROBE FAILED: real provider boundary reached")))
            stack.enter_context(patch.object(h.time, "time", lambda: clock[0]))
            stack.enter_context(patch.object(h.time, "monotonic", lambda: clock[0]))
            stack.enter_context(patch.object(h.time, "sleep", sleep))
            stack.enter_context(contextlib.redirect_stdout(stdout))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            # The no-probe assertion has an actual call to the same fake as its control.
            h.probe("fixture-harness", None)
            if inherited is not None:
                # Re-attach to a real constructor's durable state, as after a supervisor restart.
                resumed = h.resume_head(args, str(f.record), "fixture-session", 1, "fixture", str(output),
                                        {}, "network", 0, "fixture", clock[0])
                record = rows(f.record)
                event = next(r for r in reversed(record) if r.get("event") == "head-resumed")
                if inherited == "missing":
                    event.pop("network_no_work_n", None)
                else:
                    event["network_no_work_n"] = inherited
                f.record.write_text(encoded(record))
                proc, out, offset, start = resumed
                public = h.supervise_loop(args, str(f.record), "fixture-session", proc, proc.pid,
                                          out, offset, start, clock[0])
            else:
                public = h.supervise_loop(args, str(f.record), "fixture-session", None, 41000,
                                          str(output), 0, 1, clock[0])
        f.history.append({"command": ["handsoff.supervise_loop", "fixture-session"],
                          "returncode": public, "stdout": stdout.getvalue(), "stderr": stderr.getvalue()})
        record = rows(f.record)
        return {"public_returncode": public, "starts": starts, "probes": probes, "resets": resets,
                "successors": successors, "prompts": prompts,
                "delays": [r["delay_s"] for r in record if r.get("event") == "network-backoff"],
                "judgements": [r for r in record if r.get("event") == "network-resume-judged"],
                "abort": [r for r in record if r.get("event") == "successor-aborted"],
                "stood_down": [r for r in record if r.get("event") == "supervisor-stood-down"],
                "refused": [r for r in record if r.get("event") == "head-resume-refused"],
                "usage_probe_control": usage_probes[:1], "usage_probes": usage_probes[1:],
                "held_at_start": held_at_start, "held_at_end": list(h.open_holds(record)),
                "record": record, "turns": turn[0], "resume_cap": h.RESUME_CAP,
                "successor_cap": h.MAX_SUCCESSORS_DEFAULT}

    def sequence(self, f, sequence, starts, aborted=False, successors=0, **kwargs):
        data = self.loop(f, sequence, **kwargs)
        continued = data["starts"][1:] if kwargs.get("inherited") is not None else data["starts"]
        probe_counts = [row["probes_before_start"] for row in continued]
        good = (len(data["starts"]) == starts and bool(data["abort"]) == aborted
                and data["public_returncode"] == (1 if aborted else 0)
                and len(data["successors"]) == successors and not data["resets"] and self.controls.get("claude")
                and all(count > kwargs.get("outage", 0) for count in probe_counts)
                and all(before < after for before, after in zip(probe_counts, probe_counts[1:]))
                and all(("--resume" in row["command"] or "--session-id" in row["command"])
                        and "fixture-model" in row["command"] for row in data["starts"]))
        if aborted:
            good = good and data["abort"][-1].get("reason") == "network-no-progress"
        return bool(good), data

    def cold_lane(self, f, family, limit=False, damaged=None, costly=False, budget=False):
        executable = f.root / "bin" / family
        source = executable.read_text()
        anchor = 'root=Path(os.environ["A3_FIXTURE"])\n'
        if source.count(anchor) != 1:
            raise RuntimeError("PROBE FAILED: fake provider start counter anchor")
        executable.write_text(source.replace(anchor, anchor +
            'with (root/"provider-starts.jsonl").open("a") as counter:\n'
            '    counter.write(json.dumps({"argv":sys.argv[1:]})+"\\n")\n'))
        text = LIMIT if limit else STOPS[0]
        records = ([assistant(text, "<synthetic>")] if family == "claude" else
                   [{"type": "turn.failed", "error": {"message": text}}])
        if costly:
            # Above the measured first-call cost, with a report exceeding the advice threshold.
            first = assistant("partial work " * 50, identity="first")
            last = assistant("saved work " * 50, identity="last")
            first["message"]["usage"]["input_tokens"] = 1000
            last["message"]["usage"]["input_tokens"] = 100000
            if family == "claude":
                records = [first, last] + records
        cli = result(text, True)
        if budget:
            records = [assistant("partial budget work")]
            cli = result("Maximum budget reached", True)
            cli["subtype"] = "error_max_budget_usd"
        f.scenario(family, records, exit_code=1, result=cli)
        stopped = f.run(f.command(family))
        before = f.snapshot()
        expected = "budget" if budget else "limit" if limit else "network"
        if not before["journals"] or before["journals"][0].get("close", {}).get("exit_class") != expected:
            return False, {"premise": "public fixture did not close " + expected}
        clock_runner = f.root / "cold_clock.py"
        clock_runner.write_text('import runpy,sys,time\n'
            'clock=time.time\n'
            'time.time=lambda: clock()+7200  # Two hours, derived as 2 * 60 * 60 seconds.\n'
            'sys.argv=sys.argv[1:]\n'
            'runpy.run_path(sys.argv[0],run_name="__main__")\n')
        def cold(command):
            return command[:2] + [str(clock_runner)] + command[2:]
        advice = f.run(cold(f.command("claude", "advise")))
        if damaged:
            journal = before["journals"][0]
            path = Path(journal["boundary"]["path"])
            if damaged == "gone": path.unlink()
            elif damaged == "torn":
                with path.open("a") as handle: handle.write("{torn fixture tail\n")
            elif damaged == "non-record": path.write_text("[]\nnull\n42\n")
            else: path.write_text("{unparseable fixture transcript\n")
        count_before = len(rows(f.root / "provider-starts.jsonl"))
        f.scenario(family, events_for(family, "clean"))
        extra = ["--brief", str(f.brief)]
        if family == "claude":
            extra += ["--home", str(f.root / "lane-home"), "--projects-root", str(f.root / "projects")]
        else:
            extra += ["--codex", str(f.root / "bin/codex"), "--cwd", str(f.root / "work")]
        resumed = f.run(cold(f.command(family, "resume", extra)))
        snap = f.snapshot()
        resumed_rows = [r for r in snap["record"] if r.get("event") == "lane-resumed"]
        # The fake provider records every start independently of the wrapper record.
        provider_starts = rows(f.root / "provider-starts.jsonl")
        good = advice.returncode == 0 and self.controls.get(family) and count_before > 0
        if budget:
            good = (good and resumed.returncode == 2 and not resumed_rows
                    and len(provider_starts) == count_before and "resume window" in resumed.stderr)
        elif damaged and damaged != "torn":
            good = (good and resumed.returncode == 2 and not resumed_rows and len(provider_starts) == count_before
                    and ("no transcript" in resumed.stderr if damaged == "gone" else
                         "unparseable" in resumed.stderr))
        else:
            good = (good and stopped.returncode == (6 if limit else 3) and resumed.returncode == 0
                    and len(resumed_rows) == 1 and snap["successor_start_count"] == 0
                    and ("advise: restart" if costly else "advise: resume") in advice.stdout)
        return bool(good), {"advice": advice.stdout, "resume_returncode": resumed.returncode,
                            "damage": damaged, "provider_starts": provider_starts,
                            "positive_provider_start": count_before}

    def limit_loop(self, f):
        data = self.loop(f, ["limit", "limit", "limit", "close"], limit=True)
        good = (len(data["starts"]) == 3 and len(data["resets"]) == 3
                and len(data["successors"]) == 1 and data["successors"][0]["class"] == "limit"
                and not data["probes"] and not data["abort"] and not data["judgements"]
                and self.controls.get("claude"))
        return bool(good), data

    def run(self):
        self.positive("claude")
        self.positive("codex")
        def working(f):
            good, data = self.sequence(f, ["text", "tool", "text", "close"], 3, outage=2, successors=1)
            return (good and ["--resume" in r["command"] for r in data["starts"]] == [True, True, False]
                    and data["delays"] == [0, 0, 0]
                    and [r["probes_before_start"] for r in data["starts"]] == [3, 6, 9]), data
        self.case("i", "three working drops: two resumes then successor", working)
        for context in (None, 950000):
            self.case("i", "resume-fit fork context=" + str(context), lambda f, c=context:
                      self.sequence(f, ["transport", "close"], 1, successors=1, context=c))
        for activity in ("empty", "transport", "replay", "thinking"):
            self.case("ii", "two no-work resumes stop: " + activity, lambda f, a=activity:
                      self.sequence(f, ["transport", a, a, "close"], 2, aborted=True))
        # A single in-flight resume can reset a retained count before the cap chooses a successor.
        def resets(f):
            good, data = self.sequence(f, ["tool", "close"], 2, inherited=1)
            return good and [r["no_work_n"] for r in data["judgements"]] == [0], data
        self.case("ii", "new work resets the consecutive count", resets)
        self.case("ii", "restart retains the recorded count", lambda f: self.sequence(
            f, ["empty", "close"], 1, aborted=True, inherited=1))
        for inherited in ("unreadable", "missing"):
            def corrupt_count(f, value=inherited):
                data = self.loop(f, ["empty", "close"], inherited=value)
                return (len(data["starts"]) == 1 and data["public_returncode"] == 1
                        and data["abort"][-1].get("reason") == "network-state-unknown"
                        and not data["probes"] and self.controls.get("claude")), data
            self.case("ii", inherited + " stored count holds without inventing zero", corrupt_count)
        for activity in ("unknown", "missing-boundary", "bad-record", "malformed"):
            for retained in (0, 1):
                def neither(f, a=activity, n=retained):
                    good, data = self.sequence(f, [a, "close"], 2, inherited=n)
                    final = data["judgements"][-1] if data["judgements"] else {}
                    return (good and final.get("progress") == "unknown" and final.get("no_work_n") == n
                            and (a not in ("bad-record", "malformed") or final.get("model_answer") == "yes")), data
                self.case("iii", activity + " keeps " + str(retained), neither)
        def transport(f):
            good, data = self.sequence(f, ["transport"] * 3 + ["close"], 2, aborted=True)
            return (good and data["delays"] == [0, 60, 120]
                    and [r["no_work_n"] for r in data["judgements"]] == [0, 1, 2]), data
        self.case("iv", "provider-only answers count completed no-work resumes", transport)
        def waiting(f):
            good, data = self.sequence(f, ["transport", "close"], 1, outage=4)
            return (good and len(data["probes"]) == 5 and data["starts"][0]["at"] == 1120
                    and [r["no_work_n"] for r in data["judgements"]] == [0]), data
        self.case("iv", "outage probes wait without counting a resume", waiting)
        for cancel in ("owner", "close", "manual"):
            self.case("iv", "wait cancellation " + cancel, lambda f, c=cancel: self.sequence(
                f, ["transport", "close"], 0, cancel=c))
        for origin in ("http://provider.invalid", "https://user:secret@provider.invalid",
                       "https://provider.invalid:bad", "https://[broken"):
            def impossible(f, url=origin):
                data = self.loop(f, ["transport", "close"], invalid_origin=url)
                return (data["public_returncode"] == 1 and not data["starts"]
                        and data["abort"][-1].get("reason") == "network-probe-impossible"
                        and self.controls.get("claude")), data
            self.case("iv", "impossible provider probe " + origin, impossible)
        for family in ("claude", "codex"):
            self.case("v", family + " cold network public resume", lambda f, fam=family: self.cold_lane(f, fam))
            self.case("vi", family + " cold limit public resume", lambda f, fam=family: self.cold_lane(f, fam, True))
        for limit in (False, True):
            self.case("v", "cold costly advice " + str(limit), lambda f, l=limit:
                      self.cold_lane(f, "claude", limit=l, costly=True))
        self.case("v", "cold budget public refusal", lambda f: self.cold_lane(f, "claude", budget=True))
        def failed_start(f):
            data = self.loop(f, ["transport", "close"], start_failure=True)
            return (data["public_returncode"] == 0 and len(data["starts"]) == len(data["successors"]) == 1
                    and "--session-id" in data["starts"][0]["command"]
                    and not data["abort"] and data["refused"][-1].get("reason") == "resume-failed"
                    and self.controls.get("claude")), data
        self.case("v", "failed resume constructor takes the successor path", failed_start)
        self.case("vi", "limit cap and successor; no repeat-stop or network probe", self.limit_loop)
        def stopped(f):
            data = self.loop(f, ["limit", "close"], limit=True, on_limit="stop")
            return (data["public_returncode"] == 0 and not data["starts"] and not data["resets"]
                    and not data["probes"] and data["stood_down"][-1]["reason"] == "limit-stop"
                    and self.controls.get("claude")), data
        self.case("vi", "default on_limit stop stands down", stopped)
        self.case("i", "network ignores on_limit stop", lambda f: self.sequence(
            f, ["transport", "close"], 1, on_limit="stop"))
        # Two hours of outage = 240 failed probes at the specified 30-second polling interval.
        for context, successor in ((1000, 0), (200000, 1)):
            self.case("v", "cold head cost fork memory=" + str(context), lambda f, c=context, n=successor:
                      self.sequence(f, ["transport", "close"], 1, outage=240, context=c, successors=n))
        for limit in (False, True):
            for damaged in ("gone", "unparseable", "non-record", "torn"):
                self.case("vi", "D29 helper " + str(limit) + " " + damaged,
                          lambda f, l=limit, d=damaged: self.cold_lane(f, "claude", l, d))
            for damaged in ("gone", "unparseable", "torn"):
                def head_transcript(f, l=limit, d=damaged):
                    data = self.loop(f, [d, "close"], limit=l)
                    resumed = sum("--resume" in row["command"] for row in data["starts"])
                    return (data["public_returncode"] == 0 and resumed == (1 if d == "torn" else 0)
                            and len(data["successors"]) == (0 if d == "torn" else 1)
                            and self.controls.get("claude")), data
                self.case("vi", "D29 head " + str(limit) + " " + damaged, head_transcript)
        self.fold_cases()

    def fold_cases(self):
        for probe in (False, True):
            for mixed in (False, True):
                def model_limit(f, p=probe, mixed=mixed):
                    text = MODEL_LIMIT + (" " + STOPS[0] if mixed else "")
                    data = self.loop(f, ["limit", "close"], model_text=text, model_probe=p)
                    stops = [r for r in data["record"] if r.get("event") == "stop-condition"]
                    exits = [r for r in data["record"] if r.get("event") == "head-exit"]
                    relevant = [r["event"] for r in data["record"]
                                if r.get("event") in ("stop-condition", "head-exit", "successor-aborted")]
                    return (data["public_returncode"] == 1 and not data["starts"] and not data["probes"]
                            and not data["resets"] and not data["usage_probes"] and data["usage_probe_control"]
                            and len(stops) == len(exits) == len(data["abort"]) == 1
                            and stops[0].get("which") == "limit-model" and stops[0].get("model") == "Fable"
                            and exits[0].get("band") == "limit" and exits[0].get("which") == "limit-model"
                            and exits[0].get("pack") is False and exits[0].get("pid") == 41000
                            and data["abort"][0].get("reason") == "limit-model-fable"
                            and relevant == ["stop-condition", "head-exit", "successor-aborted"]
                            and self.controls.get("claude")), data
                self.case("FC2", "vi model-scope probe=" + str(probe) + " mixed=" + str(mixed), model_limit)
        def other_model(f):
            data = self.loop(f, ["limit", "close"], model_text=MODEL_LIMIT.replace("Fable", "Opus"), model_probe=False)
            stops = [r for r in data["record"] if r.get("event") == "stop-condition"]
            return (data["public_returncode"] == 1 and not data["starts"] and len(stops) == 1
                    and stops[0].get("which") == "limit-model" and stops[0].get("model") == "Opus"
                    and len(data["abort"]) == 1 and data["abort"][0].get("reason") == "limit-model-opus"), data
        self.case("FC2", "vi model-scope names a model other than Fable", other_model)
        self.case("FC2", "vi model-scope adjacent dropped-connection control", lambda f:
                  self.sequence(f, ["text", "close"], 1))
        for limit in (False, True):
            for damage in ("gone", "unparseable", "start-failed"):
                def holds(f, l=limit, d=damage):
                    data = self.loop(f, ["transport" if d == "start-failed" else d, "close"],
                                     limit=l, start_failure=d == "start-failed", hold=True,
                                     real_successor=True)
                    reason = "resume-failed" if d == "start-failed" else "resume-transcript"
                    return (data["public_returncode"] == 0 and data["held_at_start"] == ["held-helper"]
                            and data["held_at_end"] == data["held_at_start"] and not data["abort"]
                            and len(data["successors"]) == 1 and len(data["refused"]) == 1
                            and data["refused"][0].get("reason") == reason
                            and not any(r.get("event") == "hold-ended" for r in data["record"])
                            and self.controls.get("claude")), data
                self.case("FC2", "recoverable refusal preserves holds " + str(limit) + " " + damage, holds)
        def real_chain(f):
            h = load(Path(self.args.wrappers) / "handsoff.py", "cap_constants")
            # Every session gets RESUME_CAP resumes then a successor; the final successor is refused.
            stops = (h.MAX_SUCCESSORS_DEFAULT + 1) * (h.RESUME_CAP + 1)
            data = self.loop(f, ["text"] * stops + ["close"], real_successor=True, hold=True)
            return (data["public_returncode"] == 1 and len(data["successors"]) == h.MAX_SUCCESSORS_DEFAULT
                    and len(data["starts"]) == stops - 1 and len(data["probes"]) == stops
                    and data["abort"][-1].get("reason") == "successor-cap"
                    and data["held_at_start"] == ["held-helper"] and not data["held_at_end"]
                    and self.controls.get("claude")), data
        self.case("FC2", "real successor chain reaches successor-cap control", real_chain)
        for guard in ("duplicate", "unmetered-loop"):
            def guarded(f, guard=guard):
                data = self.loop(f, ["text", "text", "close"], real_successor=True,
                                 context=None, successor_guard=guard, hold=True)
                return (data["public_returncode"] == 1 and len(data["successors"]) == (guard == "unmetered-loop")
                        and data["abort"][-1].get("reason") == guard and not data["held_at_end"]
                        and data["held_at_start"] == ["held-helper"] and self.controls.get("claude")), data
            self.case("FC2", "real successor " + guard + " control", guarded)
        def prompt(f):
            data = self.loop(f, ["text", "close"])
            return (data["prompts"] and "check the saved work" in data["prompts"][0]
                    and "provider reachability" not in data["prompts"][0]
                    and "API answers again" in data["prompts"][0]), data
        self.case("FC2", "resume note gives no improvised provider check", prompt)
        for failure in ("transcript", "start"):
            def standalone(f, failure=failure):
                h = load(Path(self.args.wrappers) / "handsoff.py", "standalone_refusal")
                h._LANE = (f.module(), str(Path(self.args.wrappers) / "lane.py"), None)
                transcript = f.root / "standalone.jsonl"
                if failure == "start":
                    transcript.write_text(encoded([assistant("saved work")]))
                f.record.write_text(encoded([h.event("fixture", "hold", lane="held-helper", cap=1)]))
                before = list(h.open_holds(rows(f.record)))
                args = SimpleNamespace(run="fixture", harness_bin="fixture-harness", effort="max", config_dir=None)
                output = io.StringIO()
                with patch.dict(os.environ, f.env), \
                     patch.object(h, "transcript_for", return_value=str(transcript)), \
                     patch.object(h, "launch_model", return_value=("fixture-model", "fixture")), \
                     patch.object(h, "vault_root", return_value=str(f.root)), \
                     patch.object(h.subprocess, "Popen", side_effect=OSError("fixture start failure")), \
                     contextlib.redirect_stdout(output):
                    resumed = h.resume_head(args, str(f.record), "fixture-session", 1, "fixture",
                                            str(f.root / "standalone.out"), {}, "network", 0, "fixture", 1000)
                record = rows(f.record)
                aborts = [r for r in record if r.get("event") == "successor-aborted"]
                expected = "resume-transcript" if failure == "transcript" else "resume-failed"
                return (resumed is None and before == ["held-helper"] and not h.open_holds(record)
                        and len(aborts) == 1 and aborts[0].get("reason") == expected
                        and aborts[0].get("holds_ended") == 1 and self.controls.get("claude")), record
            self.case("FC2", "standalone resume refusal still aborts control " + failure, standalone)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wrappers", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--case-match", default="")
    parser.add_argument("--mutant-progress", choices=("yes", "no"))
    args = parser.parse_args()
    required = ("lane.py", "codex-lane.py", "handsoff.py", "probe_fix_c.py", "fixtures-fix-c.json")
    if not args.fixture_root.is_dir() or not all((args.wrappers / name).is_file() for name in required):
        print("PROBE FAILED: wrapper source or isolated fixture root missing")
        return 2
    scratch = Path(subprocess.check_output(["/usr/bin/mktemp", "-d", str(args.fixture_root / "resume.XXXXXX")], text=True).strip())
    source = args.wrappers.resolve()
    before_source = manifest(source)
    copy = scratch / "sources"
    try:
        shutil.copytree(source, copy)
        for p in copy.rglob("*"):
            p.chmod(0o555 if p.is_dir() else 0o444)
        copy.chmod(0o555)
        before = manifest(copy)
        args.wrappers, args.fixture_root = copy, scratch
        suite = Suite(args)
        suite.run()
        args.only, args.case_match = [], ""
        suite.diagnostic_contract()
        suite.check("CONTROL+", "the checksum manifest sees one changed byte in a scratch copy",
                    manifest_sees_a_changed_byte(copy / "lane.py", scratch / "manifest-control"))
        suite.check("CONTROL+", "a stub manifest returning an empty dictionary fails that control",
                    not manifest_sees_a_changed_byte(copy / "lane.py", scratch / "manifest-control-stub", lambda root: {}))
        suite.check("READ-ONLY", "source copy and supplied wrappers unchanged",
                    before == manifest(copy) and before_source == manifest(source), {"files": len(before)})
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
