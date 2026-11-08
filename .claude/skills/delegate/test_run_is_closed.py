#!/usr/bin/env python3
"""Public run-is-closed regressions on removed mktemp fixtures, never a real run store.

The command runs on a read-only copy with a before/after checksum manifest. The last leg
also greps its source for write operations, with a planted positive control. Fixture times
and the process timeout are set by judgement, unmeasured; time ordering is deliberately
different from event ordering. Exit codes follow the command contract: 0 closed, 1 open,
2 unresolved. All test-created files live under the required --fixture-root.
"""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys


TIMEOUT = 10  # Seconds; set by judgement, unmeasured, to bound a broken fixture command.
WRITE_PATTERN = (r"\.(write|write_text|write_bytes|touch|mkdir|unlink|rename|replace|chmod)\("
                 r"|open\([^\n]*['\"][wax][+bt]*['\"]"
                 r"|\b(append_record|write_pointer|record_lock|makedirs|remove|rmdir)\("
                 r"|\b(subprocess|shutil)\.")


def manifest(root):
    """Names, modes and file hashes; an unexpected new file also changes this manifest."""
    result = {}
    for path in [root] + sorted(root.rglob("*")):
        mode = stat.S_IMODE(path.stat().st_mode)
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "directory"
        result[str(path.relative_to(root))] = (mode, digest)
    return result


def grep_hits(text):
    result = subprocess.run(["/usr/bin/grep", "-En", WRITE_PATTERN], input=text,
                            text=True, capture_output=True, timeout=TIMEOUT)
    if result.returncode not in (0, 1):
        raise RuntimeError("source grep failed: " + result.stderr.strip())
    return result.stdout.splitlines()


def command_source(path):
    source = path.read_text(encoding="utf-8")
    names = {"cmd_run_is_closed", "run_is_closed"}
    nodes = [node for node in ast.parse(source).body
             if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in nodes} != names or len(nodes) != len(names):
        raise RuntimeError("command or event-order helper missing or repeated")
    lines = source.splitlines(keepends=True)
    return "".join("".join(lines[node.lineno - 1:node.end_lineno]) for node in nodes)


def encoded(*kinds):
    return "".join(json.dumps({"event": kind, "run": "fixture", "ts": "fixture-time"})
                   + "\n" for kind in kinds).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handsoff", type=Path, default=Path(__file__).with_name("handsoff.py"))
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--only", action="append", default=[], help="run a named case; proof always runs")
    args = parser.parse_args()
    if not args.handsoff.is_file() or not args.fixture_root.is_dir():
        print("PROBE FAILED: handsoff.py or isolated fixture root missing")
        return 2

    opened = encoded("run-open")
    closed = encoded("run-open", "run-close")
    resumed = encoded("run-open", "run-close", "run-resume")
    # Each tuple is an independent public-command assertion: name, bytes, exit, answer, detail.
    cases = [
        ("open", opened, 1, "open", "no run-close"),
        ("closed", closed, 0, "closed", "run-close at"),
        ("resumed", resumed, 1, "open", "run-resume at fixture-time after last run-close"),
        ("reclosed", resumed + encoded("run-close"), 0, "closed", "run-close at"),
        ("reopened", closed + opened, 1, "open", "run-open at fixture-time after last run-close"),
        ("observation-after-close", closed + encoded("observation"), 0, "closed", "run-close at"),
        ("timestamps-not-order", b'{"event":"run-open","ts":"later"}\n'
         b'{"event":"run-close","ts":"latest"}\n'
         b'{"event":"run-resume","ts":"earliest"}\n', 1, "open", "run-resume at earliest"),
        ("missing", None, 2, "unresolved", "cannot read run record"),
        ("torn-after-close", closed + b'{"event":"run-resume"', 2, "unresolved", "invalid record line"),
        ("torn-before-close", opened + b'{torn\n' + encoded("run-close"), 2, "unresolved", "invalid record line"),
        ("torn-after-open", opened + b'{torn', 2, "unresolved", "invalid record line"),
        ("nonobject", closed + b'[]\n', 2, "unresolved", "invalid record line"),
        ("missing-event-name", closed + b'{}\n', 2, "unresolved", "invalid record line"),
        ("invalid-event-name", closed + b'{"event":7}\n', 2, "unresolved", "invalid record line"),
        ("empty-event-name", closed + b'{"event":""}\n', 2, "unresolved", "invalid record line"),
        ("invalid-utf8", closed + b'\xff\n', 2, "unresolved", "cannot read run record"),
        ("empty", b'', 2, "unresolved", "empty run record"),
        ("whitespace-only", b' \n\t\n', 2, "unresolved", "empty run record"),
        ("blank-lines", b'\n' + opened + b' \n' + encoded("run-close"), 0, "closed", "run-close at"),
        ("complete-last-line", closed.rstrip(b'\n'), 0, "closed", "run-close at"),
        ("unreadable", "directory", 2, "unresolved", "cannot read run record"),
    ]
    unknown = set(args.only) - {case[0] for case in cases}
    if unknown:
        print("PROBE FAILED: unknown cases: " + ", ".join(sorted(unknown)))
        return 2

    scratch = None
    results = []

    def check(name, condition, detail):
        results.append(bool(condition))
        print(("OK " if condition else "BAD ") + name + ": " + detail, flush=True)

    try:
        scratch = Path(subprocess.check_output(
            ["/usr/bin/mktemp", "-d", str(args.fixture_root.resolve() / "closed.XXXXXX")],
            text=True, timeout=TIMEOUT).strip())
        copy = scratch / "read-only"
        records = copy / "store" / "spawn-records"
        records.mkdir(parents=True)
        tool = copy / "handsoff.py"
        shutil.copyfile(args.handsoff, tool)
        for directory in ("state", "projects", "vault", "lane-home"):
            (copy / directory).mkdir()
        for name, content, *_ in cases:
            path = records / (name + ".jsonl")
            if content == "directory":
                path.mkdir()
            elif content is not None:
                path.write_bytes(content)
        for path in [copy] + list(copy.rglob("*")):
            path.chmod(0o555 if path.is_dir() else 0o444)
        before = manifest(copy)
        selected_source = command_source(tool)

        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("AIMYTH_", "LLM_WIKI_", "CLAUDE_"))}
        env.update(LLM_WIKI_STORE=str(copy / "store"),
                   AIMYTH_STATE_DIR=str(copy / "state"),
                   AIMYTH_PROJECTS_DIR=str(copy / "projects"),
                   CLAUDE_PROJECT_DIR=str(copy / "vault"),
                   LLM_WIKI_LANE_HOME=str(copy / "lane-home"),
                   PYTHONDONTWRITEBYTECODE="1")
        for name, content, expected_rc, answer, detail in cases:
            if args.only and name not in args.only:
                continue
            result = subprocess.run([sys.executable, "-B", str(tool), "run-is-closed", "--run", name],
                                    env=env, cwd=copy, text=True, capture_output=True, timeout=TIMEOUT)
            output = result.stdout + result.stderr
            correct = result.returncode == expected_rc and (name + " " + answer + " (") in output and detail in output
            if expected_rc == 2:
                correct = (correct and "PROBE FAILED:" in output and "Traceback" not in output
                           and (name + " closed (") not in output and (name + " open (") not in output)
            else:
                correct = correct and not result.stderr and "PROBE FAILED:" not in output
            check(name, correct, "exit %d, expected %d; %s" % (result.returncode, expected_rc,
                  output.strip().replace("\n", " | ")))

        # The source scan never executes its planted writer. The checksum control changes
        # a separate writable copy, so the input records themselves remain read-only.
        control = scratch / "checksum-control"
        control.mkdir()
        (control / "value").write_bytes(b"before\n")
        control_before = manifest(control)
        (control / "value").write_bytes(b"after\n")
        control_after = manifest(control)
        changed_control = sum(control_before.get(key) != control_after.get(key)
                              for key in control_before.keys() | control_after.keys())
        hits = grep_hits(selected_source)
        planted_hits = grep_hits('open("fixture", "w").write("planted")\n')
        after = manifest(copy)
        changed = sum(before.get(key) != after.get(key) for key in before.keys() | after.keys())
        proof = not changed and changed_control == 1 and not hits and len(planted_hits) == 1
        check("read-only proof", proof,
              "manifest changes %d; checksum control %d; source write hits %d; grep control %d"
              % (changed, changed_control, len(hits), len(planted_hits)))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("PROBE FAILED: " + str(exc))
        return 2
    finally:
        if scratch is not None:
            for path in scratch.rglob("*"):
                if path.is_dir():
                    path.chmod(0o755)
            shutil.rmtree(scratch)
    failed = len(results) - sum(results)
    print("FAIL %d/%d" % (failed, len(results)) if failed else "PASS %d/%d" % (len(results), len(results)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
