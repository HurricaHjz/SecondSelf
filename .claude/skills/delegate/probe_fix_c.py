#!/usr/bin/env python3
"""Read-only parser/classifier audit; optional exact staged mechanism reproduction.

No wrapper is imported or started. Fixture transcripts remain in memory. The staged-diff
option lifts only the original parser/classifier hunks, never ownership or lifecycle code.
"""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace


class Premise(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Premise(message)


def require(condition, reason):
    if not condition:
        raise Premise(reason)


def replace(source, before, after):
    require(source.count(before) == 1, "source anchor does not match exactly once")
    return source.replace(before, after)


def staged(source, diff):
    added = [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    reset = next(line for line in added if "terminal_synthetic_text" in line and "only an error record" in line)
    candidate = next(line for line in added if 'text.strip() if out["last_model"]' in line)
    anchor = '            message = record.get("message") if isinstance(record.get("message"), dict) else {}\n'
    source = replace(source, anchor, anchor + reset + "\n")
    anchor = '                out["last_model"] = str(message.get("model") or "")\n'
    source = replace(source, anchor, anchor + candidate + "\n")
    hunk = next(h for h in re.split(r"(?m)^@@[^\n]*\n", diff)[1:] if "+NETWORK_RE = re.compile(" in h)
    mechanism = "\n".join(line[1:] for line in hunk.splitlines() if line.startswith((" ", "+"))) + "\n"
    mechanism = mechanism[mechanism.index("NETWORK_RE ="):]
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "limit_signal")
    source = replace(source, "".join(source.splitlines(True)[node.lineno - 1:node.end_lineno]), mechanism)
    start = next(i for i, line in enumerate(added) if line.startswith("    result_is_error ="))
    end = next(i for i in range(start, len(added)) if added[i].startswith("    signal_text = limit_signal("))
    return replace(source, '    signal_text = limit_signal(parsed, result.get("result") or "", stderr, subtype, failed)\n',
                   "\n".join(added[start:end + 1]) + "\n")


def scope(source, payload):
    names = {"block_text", "parse_transcript", "a3_native_evidence", "a3_final_success",
             "terminal_error_text", "terminal_stop_text", "network_signal", "limit_signal", "classify"}
    constants = {"USAGE_KEYS", "NETWORK_RE", "USAGE_STOP_RE", "LIMIT_TEXT_WORDS"}
    nodes = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets):
            nodes.append(node)
    require({"parse_transcript", "classify", "limit_signal"} <= {getattr(n, "name", None) for n in nodes},
            "parser/classifier definitions absent")
    namespace = {"json": json, "re": re, "io": io, "read_bytes": lambda path: payload.encode(),
                 "os": SimpleNamespace(path=SimpleNamespace(isfile=lambda path: True)),
                 "open": lambda *a, **k: io.StringIO(payload)}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "isolated-parser", "exec"), namespace)
    return namespace


def run(args):
    path = args.root / "lane.py"
    source = path.read_text()
    digest = hashlib.sha256(source.encode()).hexdigest()
    if args.staged_diff:
        source = staged(source, args.staged_diff.read_text())
    if args.mutant_pair:
        source = replace(source, '        kind = event.get("type")\n',
                         '        synthetic["terminal_synthetic_text"] = None\n        kind = event.get("type")\n')
    stops = json.loads(args.fixtures.read_text())["stops"]
    require(len(stops) == len(set(stops)) == 4 and all(isinstance(t, str) for t in stops),
            "four distinct supplied network strings required")
    failed = total = network = limits = 0
    for text in stops:
        for trailing in (False, True):
            records = [{"type": "assistant", "uuid": "fixture", "message": {
                "model": "<synthetic>", "content": [{"type": "text", "text": text}],
                "usage": {"input_tokens": 0, "output_tokens": 0}}}]
            if trailing:
                records.append({"type": "system"})
            ns = scope(source, "".join(json.dumps(row) + "\n" for row in records))
            parsed = ns["parse_transcript"]("memory")
            cls, signal = ns["classify"](False, None, parsed, {}, "", 1, None, "")
            expected = "limit" if args.staged_diff and trailing else "network"
            total += 1
            failed += cls != expected
            network += cls == "network"
            limits += cls == "limit"
            print("CASE " + json.dumps({"trailing": trailing, "text": text, "class": cls, "signal": signal,
                                        "expected": expected, "synthetic_stop": parsed.get("synthetic_stop"),
                                        "terminal_synthetic_text": parsed.get("terminal_synthetic_text")}))
    control = source.count('"synthetic_stop"')
    require(control > 0, "positive parser control absent")
    usage_payload = json.dumps({"type": "assistant", "message": {"model": "<synthetic>",
                               "content": [{"type": "text", "text": "Usage limit reached; resets tomorrow"}]}}) + "\n"
    ns = scope(source, usage_payload)
    usage_class = ns["classify"](False, None, ns["parse_transcript"]("memory"), {}, "", 1, None, "")[0]
    total += 1
    failed += usage_class != "limit"
    total += 1
    failed += hashlib.sha256(path.read_bytes()).hexdigest() != digest
    print("parser control hits: %d" % control)
    print("genuine-limit positive control: " + usage_class)
    print("network classifications: %d/8; limit classifications: %d/8" % (network, limits))
    print("source sha256: " + digest)
    print("FAIL %d/%d" % (failed, total) if failed else "PASS %d/%d" % (total, total))
    return 1 if failed else 0


def main():
    try:
        parser = Parser(description=__doc__)
        parser.add_argument("--root", type=Path, required=True)
        parser.add_argument("--fixtures", type=Path, required=True)
        parser.add_argument("--staged-diff", type=Path)
        parser.add_argument("--mutant-pair", action="store_true")
        args = parser.parse_args()
        return run(args)
    except (Premise, OSError, ValueError, KeyError, StopIteration, SyntaxError) as exc:
        print("PROBE FAILED: " + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
