#!/usr/bin/env python3
"""The adopt suites' result protocol: four outcomes, one record, one closing line.

A required check that did not run stays visible without counting as a failed test. A suite ends
with one `ADOPT_SUITE_RESULT` JSON record and one closing line:

  exit 0  PASS          all selected required coverage executed, no failure or probe error
  exit 1  FAIL          an executed test failed; unrun obligations and probes are still listed
  exit 2  PROBE FAILED  no executed failure established, but a premise or the evidence is broken
  exit 3  INCOMPLETE    no failure or probe error, but required coverage is unrun

Importing this module runs no test and touches nothing. Its two commands read files and print:

  suite_results.py validate --suite S --scope C --producer FILE --stdout FILE --status N
      --hook present|absent [--require-exit N] [--require-executed N] [--require-failed N]
      [--require-unrun N] [--require-probes N]
  suite_results.py inventory --suite S --scope C --producer FILE

`validate` exits 0 for a valid report meeting any requested expectations, 1 for a valid report
contradicting them, and 2 for invalid input, a missing or unknown argument or a broken premise. Exit
0 alone is not suite success: a valid incomplete report also validates. `inventory` exits 0 or 2.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

SCHEMA = 1
MARKER = "ADOPT_SUITE_RESULT "
UNITS = {"register": "families", "generated-dates": "cases", "o5": "cases", "fingerprint": "cases"}
STATES = ("PASS", "FAIL", "INCOMPLETE", "UNRUN", "NOT_APPLICABLE", "PROBE_FAILED")
VERDICTS = {0: "PASS", 1: "FAIL", 2: "PROBE FAILED", 3: "INCOMPLETE"}
FIELDS = ("schema", "suite", "scope", "unit", "inventory", "records", "unrun", "not_applicable",
          "probe_errors", "coverage_known", "executed", "failed", "exit")
RECORD_FIELDS = ("id", "executed", "assertions", "failed", "state")
ROLES = ("helper", "entry")
# GD's hook-scoped cases, by their stable IDs, in GD's own inventory and inside the dispatcher's.
HOOK_CASES = ("I1", "D5-stop", "I3", "N1-rename")
GD_NAMESPACE = "GD/"
GD_FAMILY = "GD generated register dates, digest and navigation"
LIVE_CONSUMERS = "T-consumers: live update/install, launcher, setup/export/deep-lint sources and integration grants"


class ProtocolError(Exception):
    """A report, inventory or validator input that cannot be trusted."""


class Unrun(Exception):
    """A required input is known to be absent: one obligation, not a failed test."""

    def __init__(self, requirement, missing):
        super().__init__(requirement)
        self.requirement = requirement
        self.missing = list(missing)


class Premise(Exception):
    """A named harness stage failed: a probe, with no claim about the code under test."""

    def __init__(self, stage, message):
        super().__init__(message)
        self.stage = stage
        self.message = message


def default_state(path):
    """`present` or `absent` for a default input; anything else raises OSError.

    Absence is only known by walking to the nearest existing ancestor and finding it a searchable
    directory, so a missing fixtures folder is not mistaken for an inspection error, and a path that
    cannot be inspected is not mistaken for absence."""
    path = Path(path)
    try:
        os.stat(path)
        return "present"
    except FileNotFoundError:
        pass
    ancestor = path.parent
    while True:
        try:
            info = os.stat(ancestor)
            break
        except FileNotFoundError:
            if ancestor.parent == ancestor:
                raise
            ancestor = ancestor.parent
    if not stat_is_directory(info) or not os.access(ancestor, os.X_OK):
        raise NotADirectoryError("cannot inspect below " + str(ancestor))
    return "absent"


def stat_is_directory(info):
    return (info.st_mode & 0o170000) == 0o040000


def decide(executed, failed, unrun, probes):
    """The exit, in the contract's order. An empty selection must arrive here as a probe."""
    if failed > 0:
        return 1
    if probes > 0:
        return 2
    if unrun > 0:
        return 3
    return 0 if executed > 0 else 2


def closing_line(code, unit, executed, failed, unrun, probes):
    return "%s: %d executed %s; %d executed failures; %d required unrun; %d probe errors" % (
        VERDICTS[code], executed, unit, failed, unrun, probes)


def probe_key(stage, entries, tag=None):
    return stage + "/" + (tag if tag else ",".join(entries) if entries else "suite")


class Collector:
    """Accounts one suite run. It holds plain data only and prints nothing until `finish`."""

    def __init__(self, suite, scope, inventory):
        self.suite, self.scope = suite, scope
        self.unit = UNITS[suite]
        self.inventory = inventory
        self.ids = [entry["id"] for entry in inventory]
        self.items = {i: {"executed": False, "assertions": 0, "failed": False} for i in self.ids}
        self.unrun_list, self.probes, self.absent = [], [], []
        self.reported = set()

    def _known(self, entry):
        if entry not in self.items:
            raise KeyError("unknown inventory entry: " + str(entry))

    def execute(self, entry, assertions=0):
        self._known(entry)
        self.items[entry]["executed"] = True
        self.items[entry]["assertions"] += assertions

    def fail(self, entry, assertions=0):
        self.execute(entry, assertions)
        self.items[entry]["failed"] = True

    def unrun(self, identifier, entry, requirement, missing):
        self._known(entry)
        if not any(item["id"] == identifier for item in self.unrun_list):
            self.unrun_list.append({"id": identifier, "entry": entry, "requirement": requirement,
                                    "missing": sorted(missing)})

    def not_applicable(self, identifier, entry, reason):
        self._known(entry)
        if not any(item["id"] == identifier for item in self.absent):
            self.absent.append({"id": identifier, "entry": entry, "reason": reason})

    def probe(self, stage, entries, message, tag=None):
        for entry in entries:
            self._known(entry)
        key = probe_key(stage, entries, tag)
        if not any(item["key"] == key for item in self.probes):
            self.probes.append({"key": key, "stage": stage, "entries": list(entries), "message": str(message)})

    def unaccounted(self):
        """Entries with no outcome yet: neither run nor named by an omission, probe or absence."""
        marked = ({item["entry"] for item in self.unrun_list} | {item["entry"] for item in self.absent} |
                  {entry for item in self.probes for entry in item["entries"]})
        return [i for i in self.ids if i not in marked and not self.items[i]["executed"]]

    def state(self, entry):
        item = self.items[entry]
        if item["failed"]:
            return "FAIL"
        if any(entry in probe["entries"] for probe in self.probes):
            return "PROBE_FAILED"
        if any(entry == absent["id"] for absent in self.absent):
            return "NOT_APPLICABLE"
        if any(entry == gap["entry"] for gap in self.unrun_list):
            return "INCOMPLETE" if item["executed"] else "UNRUN"
        return "PASS" if item["executed"] else "PROBE_FAILED"

    def report(self):
        applicable = [i for i in self.ids if not any(i == absent["id"] for absent in self.absent)]
        if not applicable and not self.probes:
            self.probe("selection", [], "no applicable selection", tag="empty")
        missing = self.unaccounted()
        if missing:
            self.probe("accounting", missing, "unaccounted coverage")
        records = [dict(id=i, executed=self.items[i]["executed"], assertions=self.items[i]["assertions"],
                        failed=self.items[i]["failed"], state=self.state(i)) for i in self.ids]
        executed = sum(1 for record in records if record["executed"])
        failed = sum(1 for record in records if record["failed"])
        code = decide(executed, failed, len(self.unrun_list), len(self.probes))
        return {"schema": SCHEMA, "suite": self.suite, "scope": self.scope, "unit": self.unit,
                "inventory": self.inventory, "records": records, "unrun": self.unrun_list,
                "not_applicable": self.absent, "probe_errors": self.probes,
                "coverage_known": not self.probes, "executed": executed, "failed": failed, "exit": code}

    def family_line(self, entry):
        self.reported.add(entry)
        return "FAMILY %s %s (assertions %d)" % (self.state(entry), entry, self.items[entry]["assertions"])

    def finish(self):
        """Print the remaining display lines, the record and the closing line; return the exit."""
        report = self.report()
        for entry in self.ids:
            if entry not in self.reported:
                print(self.family_line(entry), flush=True)
        for item in report["probe_errors"]:
            print("PROBE " + item["key"] + ": " + item["message"], flush=True)
        for item in report["unrun"]:
            print("UNRUN REQUIRED " + item["id"] + ": " + item["requirement"] + "; missing: " +
                  ", ".join(item["missing"]), flush=True)
        print(MARKER + json.dumps(report, sort_keys=True), flush=True)
        print(line_of(report), flush=True)
        return report["exit"]


def line_of(report):
    return closing_line(report["exit"], report["unit"], report["executed"], report["failed"],
                        len(report["unrun"]), len(report["probe_errors"]))


def no_duplicates(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ProtocolError("duplicate JSON key: " + key)
        value[key] = item
    return value


def exact_int(value, label):
    if type(value) is not int:
        raise ProtocolError(label + " must be an exact integer")
    return value


def exact_bool(value, label):
    if type(value) is not bool:
        raise ProtocolError(label + " must be a boolean")
    return value


def plain_text(value, label):
    if type(value) is not str or not value:
        raise ProtocolError(label + " must be a non-empty string")
    return value


def check_inventory(value):
    """A plain-data inventory: stable unique IDs, each with its owned modules."""
    if type(value) is not list:
        raise ProtocolError("inventory must be a list")
    seen = set()
    for entry in value:
        if type(entry) is not dict or set(entry) != {"id", "modules"}:
            raise ProtocolError("inventory entry must hold id and modules")
        identifier = plain_text(entry["id"], "inventory id")
        if identifier in seen:
            raise ProtocolError("duplicate inventory id: " + identifier)
        seen.add(identifier)
        if type(entry["modules"]) is not list:
            raise ProtocolError("inventory modules must be a list")
        for module in entry["modules"]:
            if type(module) is not dict or set(module) != {"path", "role"}:
                raise ProtocolError("module must hold path and role")
            plain_text(module["path"], "module path")
            if module["role"] not in ROLES:
                raise ProtocolError("unknown module role: " + str(module["role"]))
    try:
        if json.loads(json.dumps(value)) != value:
            raise ProtocolError("inventory does not survive a JSON round trip")
    except (TypeError, ValueError) as exc:
        raise ProtocolError("inventory is not plain JSON: " + str(exc))
    return value


def load_provider(path):
    """Load a producer under a non-main name. Its module-level imports run, as any import's do."""
    path = Path(path).resolve(strict=True)
    sys.dont_write_bytecode = True
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("adopt_suite_provider_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def provider_inventory(path, scope):
    """The expected inventory, from the pinned producer rather than the report under test."""
    try:
        value = load_provider(path).selected_inventory(scope)
    except ProtocolError:
        raise
    except Exception as exc:
        raise ProtocolError("inventory provider: " + type(exc).__name__ + ": " + str(exc))
    return check_inventory(value)


def check_report(report, suite, scope, expected, hook):
    """Every rule of the contract except the process status and the closing text."""
    if type(report) is not dict or set(report) != set(FIELDS):
        raise ProtocolError("report fields differ from the contract")
    if exact_int(report["schema"], "schema") != SCHEMA:
        raise ProtocolError("unsupported schema")
    if report["suite"] != suite or report["scope"] != scope:
        raise ProtocolError("report suite or scope differs from the request")
    if report["unit"] != UNITS[suite]:
        raise ProtocolError("wrong unit")
    executed, failed = exact_int(report["executed"], "executed"), exact_int(report["failed"], "failed")
    code = exact_int(report["exit"], "exit")
    exact_bool(report["coverage_known"], "coverage_known")
    check_inventory(report["inventory"])
    if report["inventory"] != expected:
        raise ProtocolError("inventory differs from the producer's expected inventory")
    ids = [entry["id"] for entry in expected]
    for name in ("records", "unrun", "not_applicable", "probe_errors"):
        if type(report[name]) is not list:
            raise ProtocolError(name + " must be a list")
    unrun_by_entry, seen = {}, set()
    for item in report["unrun"]:
        if type(item) is not dict or set(item) != {"id", "entry", "requirement", "missing"}:
            raise ProtocolError("unrun entry fields differ from the contract")
        identifier = plain_text(item["id"], "unrun id")
        if identifier in seen:
            raise ProtocolError("duplicate unrun id: " + identifier)
        seen.add(identifier)
        if item["entry"] not in ids:
            raise ProtocolError("unrun entry names an unknown id: " + str(item["entry"]))
        plain_text(item["requirement"], "unrun requirement")
        if type(item["missing"]) is not list or not item["missing"]:
            raise ProtocolError("unrun entry names no missing prerequisite")
        for prerequisite in item["missing"]:
            plain_text(prerequisite, "missing prerequisite")
        unrun_by_entry.setdefault(item["entry"], []).append(identifier)
    probed, keys = set(), set()
    for item in report["probe_errors"]:
        if type(item) is not dict or set(item) != {"key", "stage", "entries", "message"}:
            raise ProtocolError("probe entry fields differ from the contract")
        key = plain_text(item["key"], "probe key")
        if key in keys:
            raise ProtocolError("duplicate probe key: " + key)
        keys.add(key)
        plain_text(item["stage"], "probe stage")
        if type(item["message"]) is not str or type(item["entries"]) is not list:
            raise ProtocolError("probe entry types differ from the contract")
        for entry in item["entries"]:
            if entry not in ids:
                raise ProtocolError("probe names an unknown id: " + str(entry))
            probed.add(entry)
    absent, absent_ids = set(), set()
    for item in report["not_applicable"]:
        if type(item) is not dict or set(item) != {"id", "entry", "reason"}:
            raise ProtocolError("not-applicable entry fields differ from the contract")
        identifier = plain_text(item["id"], "not-applicable id")
        if identifier in absent_ids:
            raise ProtocolError("duplicate not-applicable id: " + identifier)
        absent_ids.add(identifier)
        if item["entry"] not in ids:
            raise ProtocolError("not-applicable entry names an unknown id: " + str(item["entry"]))
        plain_text(item["reason"], "not-applicable reason")
        if identifier == item["entry"]:
            absent.add(identifier)
    records = {}
    for record in report["records"]:
        if type(record) is not dict or set(record) != set(RECORD_FIELDS):
            raise ProtocolError("record fields differ from the contract")
        identifier = plain_text(record["id"], "record id")
        if identifier not in ids:
            raise ProtocolError("record names an unknown id: " + identifier)
        if identifier in records:
            raise ProtocolError("duplicate record: " + identifier)
        exact_bool(record["executed"], "record executed")
        exact_bool(record["failed"], "record failed")
        if exact_int(record["assertions"], "record assertions") < 0:
            raise ProtocolError("negative assertion count")
        records[identifier] = record
    if set(records) != set(ids):
        raise ProtocolError("an inventory entry has no terminal record")
    for identifier, record in records.items():
        state, ran, broke = record["state"], record["executed"], record["failed"]
        gap, probe = identifier in unrun_by_entry, identifier in probed
        if state not in STATES:
            raise ProtocolError("unknown state: " + str(state))
        if broke and not ran:
            raise ProtocolError("a failed record did not execute: " + identifier)
        allowed = {"PASS": ran and not broke and not gap and not probe,
                   "FAIL": ran and broke,
                   "INCOMPLETE": ran and not broke and gap and not probe,
                   "UNRUN": not ran and not broke and gap and not probe,
                   "NOT_APPLICABLE": not ran and not broke and identifier in absent and not gap and not probe,
                   "PROBE_FAILED": not broke and probe}[state]
        if not allowed:
            raise ProtocolError("impossible state for " + identifier + ": " + state)
        if identifier in absent and state != "NOT_APPLICABLE":
            raise ProtocolError("a not-applicable entry holds another state: " + identifier)
    check_hook(report, suite, ids, records, absent_ids, hook)
    if suite == "register" and LIVE_CONSUMERS in ids and records[LIVE_CONSUMERS]["state"] != "UNRUN":
        raise ProtocolError("the live T-consumers obligation must stay unrun")
    count_executed = sum(1 for record in records.values() if record["executed"])
    count_failed = sum(1 for record in records.values() if record["failed"])
    if executed != count_executed or failed != count_failed or failed > executed:
        raise ProtocolError("counts differ from the records")
    probes, gaps = len(report["probe_errors"]), len(report["unrun"])
    if report["coverage_known"] is not (probes == 0):
        raise ProtocolError("coverage_known differs from the probe list")
    if code != decide(executed, failed, gaps, probes):
        raise ProtocolError("exit differs from the decision rule")
    if code == 0 and (not ids or gaps or probes or failed):
        raise ProtocolError("an exit 0 report with unaccounted coverage")
    return report


def check_hook(report, suite, ids, records, absent_ids, hook):
    """GD's hook cases are non-applicable exactly when the invocation has no hook."""
    if suite == "generated-dates":
        for case in (c for c in HOOK_CASES if c in ids):
            if (records[case]["state"] == "NOT_APPLICABLE") != (hook == "absent"):
                raise ProtocolError("hook case " + case + " disagrees with hook " + hook)
    elif suite == "register" and GD_FAMILY in ids and records[GD_FAMILY]["executed"]:
        named = {GD_NAMESPACE + case for case in HOOK_CASES}
        if (named <= absent_ids) != (hook == "absent") or (hook == "present" and named & absent_ids):
            raise ProtocolError("GD's hook cases disagree with hook " + hook)


def parse_stdout(text):
    """The record and closing line of a captured stdout: the last two lines, once each."""
    lines = text.split("\n")
    if not text.endswith("\n") or len(lines) < 3:
        raise ProtocolError("no complete record and closing line")
    lines = lines[:-1]
    if sum(1 for line in lines if line.startswith(MARKER)) != 1:
        raise ProtocolError("expected exactly one result record")
    if not lines[-2].startswith(MARKER):
        raise ProtocolError("output after the verdict, or no record before the closing line")
    try:
        report = json.loads(lines[-2][len(MARKER):], object_pairs_hook=no_duplicates)
    except ValueError as exc:
        raise ProtocolError("malformed record: " + str(exc))
    return report, lines[-1]


def validate_text(text, suite, scope, expected, status, hook):
    """The whole protocol check on captured stdout and the raw status; returns the report."""
    if hook not in ("present", "absent"):
        raise ProtocolError("hook must be present or absent")
    if suite not in UNITS:
        raise ProtocolError("unknown suite: " + str(suite))
    report, line = parse_stdout(text)
    check_report(report, suite, scope, expected, hook)
    if line != line_of(report):
        raise ProtocolError("closing line differs from the record")
    if type(status) is not int or status != report["exit"]:
        raise ProtocolError("raw status differs from the record's exit: " + str(status))
    return report


def summary(report, hook):
    states = {record["id"]: record["state"] for record in report["records"]}
    return {"suite": report["suite"], "scope": report["scope"], "hook": hook, "exit": report["exit"],
            "executed": report["executed"], "failed": report["failed"],
            "required_unrun": len(report["unrun"]), "probe_errors": len(report["probe_errors"]),
            "closing_line": line_of(report), "states": states,
            "failed_ids": sorted(i for i, state in states.items() if state == "FAIL"),
            "unrun_ids": sorted(item["id"] for item in report["unrun"]),
            "probe_keys": sorted(item["key"] for item in report["probe_errors"])}


def command_validate(args):
    expected = provider_inventory(args.producer, args.scope)
    try:
        text = Path(args.stdout).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ProtocolError("stdout file: " + str(exc))
    report = validate_text(text, args.suite, args.scope, expected, args.status, args.hook)
    value = summary(report, args.hook)
    wanted = {"exit": args.require_exit, "executed": args.require_executed, "failed": args.require_failed,
              "required_unrun": args.require_unrun, "probe_errors": args.require_probes}
    print(json.dumps(value, sort_keys=True), flush=True)
    wrong = [name for name, target in wanted.items() if target is not None and value[name] != target]
    if wrong:
        print("expectation not met: " + ", ".join(wrong), file=sys.stderr, flush=True)
        return 1
    return 0


def command_inventory(args):
    value = {"suite": args.suite, "scope": args.scope,
             "inventory": provider_inventory(args.producer, args.scope)}
    print(json.dumps(value, sort_keys=True), flush=True)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    inventory = commands.add_parser("inventory")
    for command in (validate, inventory):
        command.add_argument("--suite", required=True, choices=sorted(UNITS))
        command.add_argument("--scope", required=True)
        command.add_argument("--producer", required=True)
    validate.add_argument("--stdout", required=True)
    validate.add_argument("--status", required=True, type=int)
    validate.add_argument("--hook", required=True, choices=("present", "absent"))
    for name in ("exit", "executed", "failed", "unrun", "probes"):
        validate.add_argument("--require-" + name, type=int)
    args = parser.parse_args(argv)
    try:
        return command_validate(args) if args.command == "validate" else command_inventory(args)
    except ProtocolError as exc:
        print("PROBE FAILED: " + str(exc), file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
