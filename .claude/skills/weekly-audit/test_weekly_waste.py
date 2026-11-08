#!/usr/bin/env python3
"""test_weekly_waste.py: the suite for weekly-waste.py, the eight tests that define done in the
specification of the records-only weekly waste report (CR-WASTE-B, quoted in spec-D19.md).

    python3 -B test_weekly_waste.py [--mutants] [--mutation-logs DIRECTORY] [--script PATH]
                                    [--cr6-finding N | --cr6-family N | --cr5-finding N | --b17 N | --route N
                                     | --cr4-finding N | --cr3-finding N | --finding N | --cr1-finding N]
                                    [CASE ...]

A run that names no case leaves out the mutant acceptance leg, which runs the whole suite once per
mutant and takes hours; `--mutants`, `--mutation-logs` or the leg's own name runs it.

Builds its fixtures in a fresh folder under TMPDIR and removes it afterwards; every run names its
own tools folder and its own LLM_WIKI_STORE, so the suite never touches a real store. It prints one
line per case as the case ends and ends `PASS n/n` or `FAIL k/n`. `--mutation-logs` preserves each
complete mutant log in an existing directory; mutation completion prints progress before the
enclosing case ends. Case names given as arguments
select a subset; a misspelt name is refused. `--cr6-finding N` selects the cases added for finding N
of the closed review CR-WASTE6 (1: an episode string that could name two openings hides neither; 2:
the held design's abandoned line read as that format writes it; 3: the total row of a helper-time
view apart from every recorded name), and `--cr6-family N` those for the families of each finding the
fold closed (1: identities built from recorded values, each structural or shown unambiguous; 2: every
label against the recorded values that share its place, the list of labels taken from the reader's
own; 3: every format the specification names read as specified; 4: the generated records, extended).
`--cr5-finding N` selects the cases added for finding N
of the closed review CR-WASTE5 (1: recorded strings equal to the reader's labels; 2: the generated
records; 3: exact sums, rounded once where displayed; 4: fractions of a second rendered; 5: the
reference promise as the input contract states it). `--b17 N` selects the cases added for the owner's input
contract (decision B17: 1, an admitted record another record names as evidence; 2, an excluded file
a record names; 3, the detector's control on those excluded files). `--route N` selects the cases of
the fold that closed the class "record content stops the report" (0: the reader's range, field by
field; 1 to 9: each route by which a recorded value raised between acquisition and rendering; 10
and 11: the two routes shown not to arise, as guards). `--cr4-finding N` selects the cases added
for finding N of the closed review CR-WASTE4 (1: an event of another kind; the cases of its findings
2 and 3, on R1's breach rule, retired with that rule), `--cr3-finding N` those for finding N of
CR-WASTE3 (1: the input contract that answers it, now the owner's B17; 2 to 4: its MEDIUM findings),
`--finding N` those for finding N of CR-WASTE2 and `--cr1-finding N` those for finding N of
CR-WASTE1, so they can be run against an earlier reader with `--script`.

Admission follows the owner's input contract (decision B17; FIELDS.md, "Admission"): every `*.jsonl`
a fixture writes into its records folder is a run record, whatever its name, except the five event
logs pinned by exact name, which are there to be listed and never opened. Every file a fixture
record references outside the inputs (another extension, a pinned event log, a path outside the
records folder) is guarded in the runs under the audit hook and never opened; a reference to
another admitted record is no read of evidence: that record is read as a record like any other. The
promise (spec-D19.md, "Input contract", what a reference may and may not change): a reference, and an
excluded file named by one, change no figure, no coverage status and no other substantive report
content, the acquisition time, the measured byte counts and the folder inventory being reported as
they are; the cases check more strongly where they can (byte identity on a fixed clock).

Every expected value below was fixed by hand from the figure definitions and FIELDS.md, with its
arithmetic written beside it; the reader is never run to choose an expected result. The reader runs
as its own process (python3 -I -B) in every case but the in-process acquisition case, which needs to
remove a file between the listing and the read.
"""

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "weekly-waste.py")
PY = sys.executable
TZ = "Europe/London"
SINCE, UNTIL = "2026-10-05", "2026-10-12"
UUID_NAME = "0f8fad5b-d9cb-469f-a165-70867728950e.jsonl"
# The five historical GPT-6 Astra event logs the contract pins by exact name (spec-D19.md,
# "Input contract"), written out here from the specification, not from the reader.
PINNED = tuple("run-20260909-n14-accept-events-L%s.jsonl" % n for n in ("1", "2", "3", "5", "6"))


def reader_module(path, name):
    """The reader at PATH loaded as a module, never run (its commands run only under __main__)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return observe_module(mod)


def observe_module(mod):
    seen = []
    mod.containment_observer = seen.append
    mod.test_ledger = seen
    original = mod.main
    def observed(*args, **kw):
        seen.clear()
        result = original(*args, **kw)
        expected = getattr(mod, "test_expected_ledger", [])
        if expected is not None:
            expect(seen == expected, "unexpected containment ledger: %r" % (seen,))
        return result
    mod.main = observed
    return mod


# The reader's labels, from its own one definition (LABELS) in the reader beside this suite, whatever
# --script names, so a label added there is planted as a recorded value here too and a reader under
# test never sets its own expectations (CR-WASTE6 finding 3, brief item 4(b)). The labels known when
# this was written are also written out by hand (HAND_LABELS), so one taken out of LABELS is caught.
READER_LABELS = tuple(reader_module(SCRIPT, "weekly_waste_labels").LABELS)
HAND_LABELS = ("(class invalid)", "(class conflicting)", "(class unrecorded)", "(source unrecorded)",
               "(unusable)", "(all)", "None")

# In process, the opens under one folder, whatever call makes them (builtins.open or os.open): an
# audit hook installed once in this process, recording only while a case has set a log.
_AUDIT = {"log": None, "root": None, "installed": False}


def _audit_hook(event, args):
    if event != "open" or _AUDIT["log"] is None:
        return
    path = args[0]
    if isinstance(path, (str, bytes)):
        real = os.path.realpath(os.fsdecode(path))
        if real.startswith(_AUDIT["root"] + os.sep):
            _AUDIT["log"].append(("open", os.path.basename(real)))


def audit_opens(root, log):
    if not _AUDIT["installed"]:
        sys.addaudithook(_audit_hook)
        _AUDIT["installed"] = True
    _AUDIT["root"], _AUDIT["log"] = os.path.realpath(root), log


def audit_stop():
    _AUDIT["log"] = None

# ------------------------------------------------------------------------ harness ----------


class Raw(str):
    """A number a fixture line holds exactly as this JSON text, for a value no Python int or float
    carries as written (an exponent such as 1e999999999, or 0e-99999999999999)."""


def dumps_raw(obj):
    """A fixture line as JSON, each Raw value written as its own text, unquoted."""
    raws = []

    def swap(v):
        if isinstance(v, Raw):
            raws.append(str(v))
            return "@@RAW%d@@" % (len(raws) - 1)
        if isinstance(v, dict):
            return dict((k, swap(x)) for k, x in v.items())
        if isinstance(v, list):
            return [swap(x) for x in v]
        return v
    text = json.dumps(swap(obj))
    for i, r in enumerate(raws):
        text = text.replace('"@@RAW%d@@"' % i, r)
    return text


OBSERVED_BOOTSTRAP = 'import json, runpy, sys\nscript, argv = sys.argv[1], sys.argv[2:]\nnamespace = runpy.run_path(script, run_name="weekly_waste_test")\nseen = []\nnamespace["main"].__globals__["containment_observer"] = seen.append\nresult = namespace["main"](argv)\nsys.stderr.write("CONTAINMENT-TEST-CHANNEL " + json.dumps(seen) + "\\n")\nsys.exit(result)\n'


class Fx(object):
    """One fixture: records/, tools/ (initialised), projects/ (stand-in transcripts), store/."""
    count = 0

    def __init__(self, root, name, init=True, script=None):
        Fx.count += 1
        self.dir = os.path.join(root, "%03d-%s" % (Fx.count, name))
        self.records = os.path.join(self.dir, "store", "spawn-records")
        self.tools = os.path.join(self.dir, "tools")
        self.projects = os.path.join(self.dir, "projects")
        for d in (self.records, self.tools, self.projects):
            os.makedirs(d)
        self.script = script or SCRIPT
        if init:
            code, out, err = self.run("init")
            if code != 0:
                raise RuntimeError("init failed: %s %s" % (out, err))

    def env(self):
        return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.environ.get("HOME", "/"),
                "TZ": TZ, "LLM_WIKI_STORE": os.path.join(self.dir, "store"),
                "TMPDIR": os.environ.get("TMPDIR", "/tmp")}

    def run(self, *args, **kw):
        argv = list(args)
        if not argv or argv[0] not in ("init", "dispose", "abandon", "end-run"):
            argv = ["--records", kw.get("records", self.records)] + argv
        if argv[0] in ("abandon", "end-run"):
            argv = argv + ["--records", self.records]
        argv = argv + ["--tools-dir", kw.get("tools", self.tools)]
        cmd = kw.get("prefix", [PY, "-I", "-B", "-c", OBSERVED_BOOTSTRAP]) + [kw.get("script", self.script)] + argv
        p = subprocess.run(cmd, env=dict(self.env(), **kw.get("env", {})),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        err = p.stderr.decode("utf-8", "replace")
        channel = [l for l in err.splitlines() if l.startswith("CONTAINMENT-TEST-CHANNEL ")]
        if p.returncode in (0, 1):
            expect(len(channel) == 1, "reader aborted before containment observation: " + err[-500:])
            events = json.loads(channel[0].split(" ", 1)[1])
            expect(events == kw.get("expected_ledger", []), "unexpected containment ledger: %r" % events)
        err = "\n".join(l for l in err.splitlines() if not l.startswith("CONTAINMENT-TEST-CHANNEL "))
        return p.returncode, p.stdout.decode("utf-8", "replace"), err

    def report(self, since=SINCE, until=UNTIL, **kw):
        args = (["--since", since] if since else []) + ["--until", until]
        code, out, err = self.run(*args, **kw)
        tools = kw.get("tools", self.tools)
        main = detail = None
        mp = os.path.join(tools, "reports", "waste-report-%s.md" % until)
        dp = os.path.join(tools, "reports", "waste-detail-%s.md" % until)
        if os.path.exists(mp):
            main = open(mp, encoding="utf-8").read()
        if os.path.exists(dp):
            detail = open(dp, encoding="utf-8").read()
        return code, out, err, main, detail

    def write(self, name, events, folder=None):
        path = os.path.join(folder or self.records, name)
        with open(path, "w", encoding="utf-8") as h:
            for e in events:
                h.write((e if isinstance(e, str) else dumps_raw(e)) + "\n")
        return path

    def sub(self, text):
        return text.replace("<R>", os.path.realpath(self.records)).replace("<T>", os.path.realpath(self.projects))


def rows_of(main):
    """The figures table as (figure, part, value, status, coverage) tuples."""
    out, on = [], False
    for line in (main or "").split("\n"):
        if line.startswith("| Figure | Part |"):
            on = True
            continue
        if on and line.startswith("|---"):
            continue
        if on and line.startswith("| "):
            cells = [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
            out.append(tuple(cells))
        elif on and not line.strip():
            break
    return out


def section(text, heading):
    lines, on = [], False
    for line in (text or "").split("\n"):
        if line.startswith("## "):
            on = line == heading
            continue
        if on:
            lines.append(line)
    return [l for l in lines if l.strip()]


def mask(text):
    return "\n".join(l for l in (text or "").split("\n")
                     if not l.startswith("- Acquired:") and not l.startswith("- Runtime:"))


def compare_rows(got, want):
    want = [(r[0], expected_view_part(r[1])) + tuple(r[2:]) for r in want]
    if got == want:
        return None
    for i in range(max(len(got), len(want))):
        g = got[i] if i < len(got) else None
        w = want[i] if i < len(want) else None
        if g != w:
            return "row %d: got %r, want %r (%d rows got, %d want)" % (i + 1, g, w, len(got), len(want))
    return "rows differ"


def as_map(rows):
    return dict(((r[0], r[1]), r[2:]) for r in rows)


def expected_view_part(part):
    if not part.startswith("helper ") or "/" not in part:
        return part
    stem, lane = part.split("/", 1)
    return stem + "/" + (lane if lane.startswith('"') else json.dumps(lane, ensure_ascii=True))


def compare_map(got_rows, want_map):
    want_map = {(f, expected_view_part(p)): v for (f, p), v in want_map.items()}
    got = as_map(got_rows)
    if set(got) != set(want_map):
        return "row keys differ: extra %s, missing %s" % (sorted(set(got) - set(want_map))[:4],
                                                           sorted(set(want_map) - set(got))[:4])
    for k in want_map:
        if got[k] != want_map[k]:
            return "%s: got %r, want %r" % (" / ".join(k), got[k], want_map[k])
    return None


def tree_manifest(root):
    out = {}
    for base, dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(base, f)
            st = os.lstat(p)
            if os.path.islink(p):
                out[p] = ("link", os.readlink(p))
                continue
            try:
                with open(p, "rb") as h:
                    out[p] = ("file", hashlib.sha256(h.read()).hexdigest(), st.st_mode)
            except OSError:
                out[p] = ("unreadable", st.st_size, st.st_mode)
        for d in dirs:
            out[os.path.join(base, d)] = ("dir",)
    return out


def dispositions_lines(main):
    """The key lines of the Dispositions section, before the since-the-previous-report list."""
    out = []
    for line in section(main, "## Dispositions"):
        if line.startswith("Recorded since the previous report"):
            break
        if line.startswith("- "):
            out.append(line)
    return out


H, F, RV, B, RF, S = ("Helper time", "Failed closes", "Review activity and possible loops",
                      "Phase boundaries", "Refusals", "Priced spend")
ROUNDS = (RV, "rounds", "unresolved", "unresolved",
          "no record carries an item-and-round association; helper names and counts do not "
          "establish rounds or verdicts")
EVID = (RV, "evidenced item associations", "none recorded", "unresolved",
        "no opening or close records the item it serves (FIELDS.md); totals by item and loops by "
        "item are not computed")
GAPS0 = "0 named gaps (detail)"
G1 = "1 named gap (detail)"
RVC_COV = ("class critic, verifier, gate-judge (set by judgement); a class is not evidence that an "
           "episode reviewed anything; %s with no usable class; %s")
GROUPS_COV = ("reviewing-class episodes grouped by the item of the last gate before the opening; by "
              "position, not an evidenced association; %s")
NOGROUP_COV = ("no gate before the opening, the last gate refused, invalid or without an item, or a "
               "gate between the opening and the close; listed in the detail")
MULTI_COV = "a cue for the Sunday walk-through, not an evidenced loop; listed in the detail"
IDLE_COV = "%s; not independently verified head idleness"
IDLEU_COV = "boundaries without a usable idle_min or idle_src; sources are never summed together"
OVER_COV = "%s without a usable count"
REW_COV = "%s without a usable delta; cumulative totals never summed"
BS_COV = "rewrites_total on the boundaries: dated values listed in the detail, never summed; %d unknown or invalid"
SS_COV = "dated values listed in the detail; not episode charges, never summed or added; %d unknown or invalid"
# The priced total counts each session once (FIELDS.md, "Priced spend"): the closes and beats in the interval,
# then the counts of what reaches it: missing, undeclared and invalid values, and unclassified sessions.
PRICED_COV = ("%s and %s, counted by session: a session read as running totals counts its rise over the "
              "interval, a per-pass session its costs in it; %d missing, %d on an undeclared basis, %d invalid, "
              "%d unclassified; %s")
PLAN_COV = "complete %d, measured zero %d, incomplete %d, no usage reported %d, unknown %d, invalid %d"
HF_COV = "%s: %d without a usable head_denials; %s"
HS_COV = "never added to the helper closes; %s without a usable count; %s"
LATER = "a later opening of the same helper on its record; no verdict on lost work"
NONCOMP = "%d with a status outside the writers' vocabulary, %d unknown or invalid; %s"
EPISODE_PARTS = ("Helper time; Failed closes; Review activity and possible loops: reviewing-class "
                 "episodes; Review activity and possible loops: positional groups; Refusals: helper "
                 "tool; Refusals: helper fence; Refusals: helper sandbox; Priced spend: closes")
BOUNDARY_PARTS = ("Phase boundaries; Phase boundaries: rewrites snapshots; Refusals: head fence; "
                  "Refusals: boundary summary; Priced spend: snapshots")
SP_T = (S, "priced total (USD, Claude CLI result basis)")
SP_PC = (S, "plan usage closes (GPT-6 Astra, not priced)")
# Plan tokens: each direction on its own, for the closes the writer marked complete (or measured
# zero) and, apart, for those it marked incomplete (finding 2 of CR-WASTE2).
SP_TCI = (S, "plan usage input tokens, complete closes")
SP_TCO = (S, "plan usage output tokens, complete closes")
SP_TII = (S, "plan usage input tokens, incomplete closes (the writer's subtotal)")
SP_TIO = (S, "plan usage output tokens, incomplete closes (the writer's subtotal)")
TOK_COV = "%s: %d known, %d unknown or invalid; %s of unknown or invalid state or basis; %s"
# The inventory's status for a name the reader does not admit: under the input contract, a pinned
# event log only.
NOT_ADMITTED_CELL = ("not admitted: an event log pinned by its name (FIELDS.md, \"Admission\"); not opened, "
                     "its contents unread and unknown")
NOT_FOLLOWED_CELL = "unreadable: a symbolic link, never followed (FIELDS.md, \"Admission\"); not opened"
NOT_REGULAR_CELL = "unreadable: not a regular file (FIELDS.md, \"Admission\"); not opened"


def pinned_line(n):
    return ("- Not admitted by name: %d, event logs pinned by their names, never opened, their contents unread and "
            "unknown; no figure reads them (FIELDS.md, \"Admission\"):" % n)


def candidates_line(total, admitted, read, not_admitted, empty=0, unreadable=0, gone=0):
    return ("- Candidate records: %d `*.jsonl` names in the records folder, each admitted or not by its name alone "
            "before any file was opened: %d admitted as run records (%d read, %d empty, %d unreadable, %d gone during "
            "acquisition), %d not admitted." % (total, admitted, read, empty, unreadable, gone, not_admitted))


def others_line(n):
    return "- Other entries in the records folder: %d, not named `*.jsonl`, so not candidates; none opened or listed." % n


def pl(n, word):
    return "%d %s" % (n, word if n == 1 else word + "s")


def tc(n):
    return "%s complete or measured zero" % pl(n, "close")


def ti(n):
    return "%s marked incomplete by the writer" % pl(n, "close")


def gn(n):
    return "%d named gap%s (detail)" % (n, "" if n == 1 else "s")


def tok(value, k, u, members, could=0, gaps=0, status=None):
    """One plan-token row (value, status, coverage), fixed from the rule: the total is complete only
    when none of its own values is unknown or invalid, no close of unknown or invalid state or basis
    could belong to it and no named gap reaches the closes; the writer's incomplete subtotal reads
    `incomplete` when it is otherwise complete and holds a close."""
    unsure = u + could + gaps
    return ("unknown; known subtotal %d" % value if unsure else str(value),
            "unknown" if unsure else (status or "complete"),
            TOK_COV % (members, k, u, pl(could, "close"), gn(gaps)))
SP_UN = (S, "unpriced closes (transcript estimate)")
SP_NA = (S, "not applicable (no process started)")
SP_HB = (S, "hold beats not priced")
SP_SS = (S, "cumulative run or head spend snapshots")

# ------------------------------------------------------------------------ scene A ----------
def fixture_inventory(cost):
    """A complete one-model close inventory; all four counts are explicit measured zeros."""
    return {"modelUsage": {"opus": {"costUSD": cost, "inputTokens": 0, "outputTokens": 0,
                                     "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0}}}


def fixture_beat_usage():
    """Two model names and the sums of entry's two default token vectors."""
    return {"models": ["opus", "haiku"], "input_tokens": 20, "output_tokens": 40,
            "cache_read_input_tokens": 60, "cache_creation_input_tokens": 80}


# The metric fixture (test 1): both writer families, historical formats, a resume, a watch
# close, a spawn failure, a kill, a beat, two boundaries, decided gates, a head-exit snapshot, an
# old record whose run id lacks the `run-` prefix, and two pinned event logs the reader never
# opens: one a record names as its event log, one holding a record-like close that would change
# every episode figure if it were read.

def scene_a(fx):
    T = fx.sub
    fx.write("run-a.jsonl", [
        {"ts": "2026-10-05T09:00:00+0100", "run": "run-a", "event": "run-open", "session": "sA",
         "session_kind": "head", "handoff": T("<R>/handoff-a.md")},
        {"ts": "2026-10-05T09:05:00+0100", "run": "run-a", "event": "gate", "item": "item1", "metered": True,
         "decision": "allow", "run_spend_usd": 9.0, "run_spend_src": "heads $9.00"},
        {"ts": "2026-10-05T09:10:00+0100", "run": "run-a", "lane": "B1", "event": "lane-open",
         "class": "builder", "session_id": "s-b1", "brief": T("<R>/brief-B1.md")},
        {"ts": "2026-10-05T09:10:01+0100", "run": "run-a", "lane": "B1", "event": "lane-spawned",
         "class": "builder", "pid": 1},
        {"ts": "2026-10-05T09:40:00+0100", "run": "run-a", "lane": "B1", "event": "lane-closed",
         "class": "builder", "exit_class": "completed", "duration_s": 1800.0, "cost_src": "result",
         "total_cost_usd": 2.5, "session_id": "s-b1", "usage": fixture_inventory(2.5), "denials": {"tool": 1, "fence": 2, "fence_allows": 0},
         "transcript": T("<T>/s-b1.jsonl"), "report": T("<R>/run-a-report-B1.md")},
        {"ts": "2026-10-05T09:45:00+0100", "run": "run-a", "lane": "CR-1", "event": "lane-open",
         "harness": "codex", "class": "critic", "events": T("<R>/run-a-events-CR-1.log"),
         "prompt_file": T("<R>/run-a-prompt-CR-1.md")},
        {"ts": "2026-10-05T10:15:00+0100", "run": "run-a", "lane": "CR-1", "event": "lane-closed",
         "harness": "codex", "class": "critic", "exit_class": "completed", "duration_s": 1500.5,
         "cost_src": "codex-plan", "total_cost_usd": None,
         "usage": {"input_tokens": 1000, "cached_input_tokens": 0, "output_tokens": 200, "calls": 2},
         "usage_complete": True, "usage_state": "complete", "sandbox_denials": 3,
         "denials": {"tool": 0, "fence": 0, "sandbox": 3}, "events": T("<R>/run-a-events-CR-1.log")},
        {"ts": "2026-10-05T10:20:00+0100", "run": "run-a", "lane": "CR-2", "event": "lane-open",
         "harness": "codex", "class": "critic"},
        {"ts": "2026-10-05T10:50:00+0100", "run": "run-a", "lane": "CR-2", "event": "lane-closed",
         "harness": "codex", "class": "critic", "exit_class": "limit", "duration_s": 600,
         "cost_src": "codex-plan", "total_cost_usd": None,
         "usage": {"input_tokens": 500, "output_tokens": 50, "calls": 1}, "usage_complete": False,
         "usage_state": "incomplete", "usage_incomplete": ["the wrapper stopped the run (limit)"],
         "sandbox_denials": 0, "denials": {"tool": 0, "fence": 0, "sandbox": 0}},
        {"ts": "2026-10-05T11:00:00+0100", "run": "run-a", "lane": "CR-2", "event": "lane-resumed",
         "harness": "codex", "class": "critic"},
        {"ts": "2026-10-05T11:20:00+0100", "run": "run-a", "lane": "CR-2", "event": "lane-closed",
         "harness": "codex", "class": "critic", "exit_class": "completed", "duration_s": 900.0,
         "cost_src": "codex-plan", "total_cost_usd": None,
         "usage": {"input_tokens": 300, "output_tokens": 30, "calls": 1}, "usage_complete": True,
         "usage_state": "complete", "sandbox_denials": 1,
         "denials": {"tool": 0, "fence": 0, "sandbox": 1}, "resumed": True},
        {"ts": "2026-10-05T11:30:00+0100", "run": "run-a", "event": "phase-boundary", "from": "item1",
         "to": "item2", "idle_min": 12.5, "idle_src": "transcript", "denials": 0, "head_denials": 2,
         "head_denials_src": "2 head-fence deny lines", "over_cap_reports": 1, "rewrites": 3,
         "rewrites_total": 3, "run_spend_usd": 10.0},
        {"ts": "2026-10-05T11:35:00+0100", "run": "run-a", "event": "gate", "item": "item2",
         "metered": True, "decision": "allow", "run_spend_usd": 10.5},
        {"ts": "2026-10-05T11:40:00+0100", "run": "run-a", "lane": "V1", "event": "lane-open", "class": "verifier"},
        {"ts": "2026-10-05T12:00:00+0100", "run": "run-a", "lane": "V1", "event": "lane-closed",
         "class": "verifier", "exit_class": "watch-closed", "duration_s": None,
         "cost_src": "transcript-estimate", "total_cost_usd": None, "denials": "unknown",
         "fence_denials_transcript": 4, "soft_exceeded": None},
        {"ts": "2026-10-05T12:10:00+0100", "run": "run-a", "lane": "B2", "event": "lane-open", "class": "builder"},
        {"ts": "2026-10-05T12:10:30+0100", "run": "run-a", "lane": "B2", "event": "lane-closed",
         "class": "builder", "exit_class": "spawn-failed", "error": "no such file", "exit_code": 3,
         "soft_exceeded": None},
        {"ts": "2026-10-05T12:30:00+0100", "run": "run-a", "lane": "B1", "event": "hold-beat",
         "harness": "claude", "session_id": "s-b1-hold", "cost_src": "result", "total_cost_usd": 0.05, "duration_s": 3.0,
         "usage": fixture_beat_usage()},
        {"ts": "2026-10-05T13:00:00+0100", "run": "run-a", "event": "phase-boundary", "from": "item2",
         "to": "item3", "idle_min": 5.0, "idle_src": "record", "denials": 1, "head_denials": None,
         "over_cap_reports": 0, "rewrites": None, "rewrites_total": None, "run_spend_usd": 14.0},
        {"ts": "2026-10-05T13:30:00+0100", "run": "run-a", "event": "head-exit", "band": 40,
         "spent_usd": 13.75},
        {"ts": "2026-10-05T14:00:00+0100", "run": "run-a", "event": "run-close", "run_spend_usd": 15.0,
         "run_spend_src": "heads $15.00"},
    ])
    fx.write("run-plain-b.jsonl", [
        {"ts": "2026-10-06T10:00:00+0100", "run": "run-plain-b", "lane": "B1", "event": "lane-open", "class": "writer"},
        {"ts": "2026-10-06T10:20:00.250+0100", "run": "run-plain-b", "lane": "B1", "event": "lane-closed",
         "class": "writer", "exit_class": "completed", "duration_s": 1200.25, "cost_src": "result",
         "total_cost_usd": 1.25, "session_id": "s-pb1", "usage": fixture_inventory(1.25), "denials": {"tool": 0, "fence": 0, "fence_allows": 1}},
        {"ts": "2026-10-06T11:00:00+0100", "run": "run-plain-b", "lane": "CR-9", "event": "lane-open", "class": "critic"},
        {"ts": "2026-10-06T11:10:00+0100", "run": "run-plain-b", "lane": "CR-9", "event": "lane-closed",
         "class": "critic", "exit_class": "completed", "duration_s": 0, "cost_src": "result",
         "total_cost_usd": 0, "session_id": "s-cr9", "usage": fixture_inventory(0), "denials": {"tool": 0, "fence": 0, "fence_allows": 0}},
    ])
    fx.write("run-hist-c.jsonl", [
        {"ts": "2026-10-07T08:00+0100", "run": "run-hist-c", "lane": "H1", "event": "lane-open", "class": "critic"},
        {"ts": "2026-10-07T08:30+01:00", "run": "run-hist-c", "lane": "H1", "event": "lane-closed",
         "exit_class": "complete", "usage": {"duration_ms": 1000, "tool_uses": 3}},
        {"ts": "2026-10-07T08:40+0100", "run": "run-hist-c", "lane": "H2", "event": "lane-open",
         "harness": "claude-agent-tool", "class": "reflector"},
        {"ts": "2026-10-07T09:00+0100", "run": "run-hist-c", "lane": "H2", "event": "lane-closed",
         "harness": "claude-agent-tool", "class": "reflector", "exit_class": "completed",
         "duration_s": 600, "total_cost_usd": 0.5, "events": T("<R>/" + PINNED[1])},
    ])
    fx.write("run-kill-d.jsonl", [
        {"ts": "2026-10-08T10:00:00+0100", "run": "run-kill-d", "lane": "K1", "event": "lane-open",
         "harness": "codex", "class": "builder"},
        {"ts": "2026-10-08T10:30:00+0100", "run": "run-kill-d", "lane": "K1", "event": "lane-closed",
         "harness": "codex", "exit_class": "killed", "exit_code": 3, "reason": "stuck",
         "total_cost_usd": None, "cost_src": "codex-plan", "session_id": None, "killed_by": "kill"},
    ])
    fx.write("build-20260914-fit.jsonl", [
        {"ts": "2026-09-20T10:00:00+0100", "run": "build-20260914-fit", "lane": "X1", "event": "lane-open", "class": "builder"},
        {"ts": "2026-09-20T10:10:00+0100", "run": "build-20260914-fit", "lane": "X1", "event": "lane-closed",
         "class": "builder", "exit_class": "completed", "duration_s": 600, "cost_src": "result",
         "total_cost_usd": 9.0, "denials": {"tool": 0, "fence": 0, "fence_allows": 0}},
    ])
    # The referenced evidence, all outside the contract: a transcript (outside the records folder), a
    # report, a brief, a prompt, a hand-off, a current event log (`.log`), a pinned historical event
    # log among the candidates, and a per-run waste table. A second pinned event log holds a
    # record-like close of 99999 s that would change every episode figure if it were read.
    fx.write("s-b1.jsonl", ['{"type": "user", "message": "TRANSCRIPT-MARKER"}'], fx.projects)
    for name, text in (("run-a-report-B1.md", "REPORT-MARKER"), ("brief-B1.md", "BRIEF-MARKER"),
                       ("run-a-prompt-CR-1.md", "PROMPT-MARKER"), ("handoff-a.md", "HANDOFF"),
                       ("run-a-events-CR-1.log", '{"type": "thread.started"}'),
                       ("run-a-waste-table.md", "TABLE-MARKER")):
        fx.write(name, [text])
    fx.write(PINNED[1], ['{"type": "thread.started", "thread_id": "t1"}', '{"type": "turn.completed"}'])
    fx.write(PINNED[3], [
        {"ts": "2026-10-06T10:00:00+0100", "run": "run-a", "lane": "N1", "event": "lane-open", "class": "critic"},
        {"ts": "2026-10-06T10:30:00+0100", "run": "run-a", "lane": "N1", "event": "lane-closed", "class": "critic",
         "exit_class": "completed", "duration_s": 99999, "cost_src": "result", "total_cost_usd": 99.0,
         "denials": {"tool": 9, "fence": 9, "fence_allows": 0}}])
    return [os.path.join(fx.projects, "s-b1.jsonl")] + [
        os.path.join(fx.records, n) for n in (
            "run-a-report-B1.md", "brief-B1.md", "run-a-prompt-CR-1.md", "handoff-a.md",
            "run-a-events-CR-1.log", "run-a-waste-table.md", PINNED[1], PINNED[3])]


# Hand-derived (see FIELDS.md for each field's reading). Helper time: timed closes B1 1800.0,
# CR-1 1500.5, CR-2 600 and 900.0, plain B1 1200.25, CR-9 0, H2 600 = 6600.75 s over 7 closes;
# B2 spawn-failed is not applicable; V1 null, H1 and K1 absent are unknown (3). 6600.75/60 =
# 110.0125 -> 110.0. Runs: run-a 1800+1500.5+600+900 = 4800.5 (B2 n/a, V1 unknown); run-plain-b
# 1200.25; run-hist-c 600 (H1 unknown); run-kill-d 0 (K1 unknown). Classes: critic 1500.5+600+900+0 =
# 3000.5 (H1 unknown, its class from its opening); builder 1800 (B2 n/a, K1 unknown); writer
# 1200.25; reflector 600; verifier 0. Helpers: run-a/B1 1800, run-a/CR-1 1500.5, run-a/CR-2
# 600+900 = 1500. No record holds a bad line, so no named gap reaches any view.
SCENE_A_ROWS = [
    (H, "total", "unknown; known subtotal 6600.75 s (110.0 min)", "unknown",
     "11 closes: 7 timed, 1 not applicable, 3 unknown or invalid; " + GAPS0),
    (H, "run run-a", "unknown; known subtotal 4800.5 s (80.0 min)", "unknown",
     "6 closes: 1 not applicable, 1 unknown or invalid; " + GAPS0),
    (H, "run run-plain-b", "1200.25 s (20.0 min)", "complete", "2 closes: 0 not applicable, 0 unknown or invalid; " + GAPS0),
    (H, "run run-hist-c", "unknown; known subtotal 600 s (10.0 min)", "unknown",
     "2 closes: 0 not applicable, 1 unknown or invalid; " + GAPS0),
    (H, "class critic", "unknown; known subtotal 3000.5 s (50.0 min)", "unknown",
     "5 closes: 0 not applicable, 1 unknown or invalid; " + GAPS0),
    (H, "class builder", "unknown; known subtotal 1800 s (30.0 min)", "unknown",
     "3 closes: 1 not applicable, 1 unknown or invalid; " + GAPS0),
    (H, "class writer", "1200.25 s (20.0 min)", "complete", "1 close: 0 not applicable, 0 unknown or invalid; " + GAPS0),
    (H, 'helper run-a/"B1"', "1800 s (30.0 min)", "complete", "1 close: 0 not applicable, 0 unknown or invalid; " + GAPS0),
    (H, 'helper run-a/"CR-1"', "1500.5 s (25.0 min)", "complete", "1 close: 0 not applicable, 0 unknown or invalid; " + GAPS0),
    (H, 'helper run-a/"CR-2"', "1500 s (25.0 min)", "complete", "2 closes: 0 not applicable, 0 unknown or invalid; " + GAPS0),
    # Failed closes: completed B1, CR-1, CR-2 (second), plain B1, CR-9, H2 = 6; limit, watch-closed,
    # spawn-failed, killed one each = 4; H1's "complete" is outside the writers' vocabulary, so the
    # completed and non-completed totals are unknown while each recorded value's count is exact.
    (F, "closes", "11", "complete", GAPS0),
    (F, "completed", "unknown; known subtotal 6", "unknown", "exit_class completed"),
    (F, "non-completed", "unknown; known subtotal 4", "unknown", NONCOMP % (1, 0, GAPS0)),
    (F, "status killed", "1", "complete", "recorded exit_class"),
    (F, "status limit", "1", "complete", "recorded exit_class"),
    (F, "status spawn-failed", "1", "complete", "recorded exit_class"),
    (F, "status watch-closed", "1", "complete", "recorded exit_class"),
    (F, "status outside the writers' vocabulary: complete", "1", "complete",
     "shown as recorded; neither completed nor non-completed"),
    (F, "status unknown or invalid", "0", "complete", "no usable exit_class"),
    (F, "non-completed, later resumed", "1", "complete", LATER),
    # Review: critics CR-1, CR-2 twice, CR-9, H1 and verifier V1 = 6 reviewing-class episodes. By
    # the allowed, dated gate before each opening: item1 holds CR-1 and both CR-2 episodes (3),
    # item2 holds V1 (1): 2 groups, 1 with two or more; CR-9 and H1 have no gate before them (2
    # with no group), which leaves the group counts known subtotals.
    (RV, "reviewing-class episodes", "6", "complete", RVC_COV % ("0 closes", GAPS0)),
    EVID,
    (RV, "positional candidate groups", "unknown; known subtotal 2", "unknown", GROUPS_COV % GAPS0),
    (RV, "reviewing-class episodes with no positional group", "2", "complete", NOGROUP_COV),
    (RV, "candidate groups with two or more reviewing-class episodes", "unknown; known subtotal 1", "unknown", MULTI_COV),
    ROUNDS,
    # Boundaries 11:30 and 13:00: idle 12.5 (transcript) and 5.0 (record), kept apart; over-cap
    # 1 + 0; rewrites 3 and null; rewrites_total 3 and null (one unknown snapshot).
    (B, "boundary events", "2", "complete", "counted at their own timestamps; " + GAPS0),
    (B, "recorded idle, idle_src record", "5 min", "complete", IDLE_COV % "1 boundary"),
    (B, "recorded idle, idle_src transcript", "12.5 min", "complete", IDLE_COV % "1 boundary"),
    (B, "recorded idle unknown", "0", "complete", IDLEU_COV),
    (B, "over-cap reports", "1", "complete", OVER_COV % "0 boundaries"),
    (B, "rewrites (deltas)", "unknown; known subtotal 3", "unknown", REW_COV % "1 boundary"),
    (B, "cumulative rewrites snapshots", "unknown; known subtotal 1", "unknown", BS_COV % 1),
    # Refusals. Tool: B1 1, five zeros = 1 over 6; V1 "unknown", H1, H2, K1 absent. Fence: B1 2,
    # V1 4 from fence_denials_transcript, five zeros = 6 over 7. Sandbox: CR-1 3, CR-2 0 and 1 = 4
    # over 3; seven closes carry no sandbox channel. B2 spawn-failed is not applicable throughout.
    (RF, "helper tool", "unknown; known subtotal 1", "unknown",
     "11 closes: 6 known, 1 not applicable, 4 unknown or invalid; " + GAPS0),
    (RF, "helper fence", "unknown; known subtotal 6", "unknown",
     "11 closes: 7 known, 1 not applicable, 3 unknown or invalid; " + GAPS0),
    (RF, "helper sandbox", "unknown; known subtotal 4", "unknown",
     "11 closes: 3 known, 1 not applicable, 7 unknown or invalid; " + GAPS0),
    (RF, "head fence (boundaries)", "unknown; known subtotal 2", "unknown", HF_COV % ("2 boundaries", 1, GAPS0)),
    (RF, "boundary summary of helper tool refusals", "1", "complete", HS_COV % ("0 boundaries", GAPS0)),
    # Spend: priced B1 2.5 + plain B1 1.25 + CR-9 0 + the beat 0.05 = 3.80; H1 has neither basis
    # nor price (unknown basis, counted missing), H2 a price with no basis (undeclared). Plan:
    # CR-1 complete 1000 in, 200 out; CR-2 second complete 300 in, 30 out (1300 in, 230 out);
    # CR-2 first incomplete 500 in, 50 out; K1 no usage. V1 unpriced; B2 not applicable. H1's
    # unknown basis could be a plan close of any state, so every basis count and every plan token
    # total, the writer's incomplete subtotal included, is a known subtotal (1 close of unknown
    # basis). Snapshots: gate 9.0, boundary 10.0, gate 10.5, boundary 14.0, head-exit 13.75,
    # run-close 15.0 = 6 dated values.
    (S, "priced total (USD, Claude CLI result basis)", "unknown; known subtotal $3.80", "unknown",
     PRICED_COV % ("3 priced closes", "1 priced hold beat", 1, 1, 0, 0, GAPS0)),
    (S, "plan usage closes (GPT-6 Astra, not priced)", "unknown; known subtotal 4", "unknown", PLAN_COV % (2, 0, 1, 1, 0, 0)),
    SP_TCI + ("unknown; known subtotal 1300", "unknown", TOK_COV % (tc(2), 2, 0, pl(1, "close"), GAPS0)),
    SP_TCO + ("unknown; known subtotal 230", "unknown", TOK_COV % (tc(2), 2, 0, pl(1, "close"), GAPS0)),
    SP_TII + ("unknown; known subtotal 500", "unknown", TOK_COV % (ti(1), 1, 0, pl(1, "close"), GAPS0)),
    SP_TIO + ("unknown; known subtotal 50", "unknown", TOK_COV % (ti(1), 1, 0, pl(1, "close"), GAPS0)),
    (S, "unpriced closes (transcript estimate)", "unknown; known subtotal 1", "unknown", "token totals only; no dollar figure"),
    (S, "not applicable (no process started)", "unknown; known subtotal 1", "unknown", "exit_class spawn-failed"),
    (S, "hold beats not priced", "0", "complete", "plan usage or no process"),
    (S, "cumulative run or head spend snapshots", "6", "complete", SS_COV % 0),
]

SCENE_A_COVERAGE = [
    # Seven *.jsonl names: five admitted (run-a, run-plain-b, run-hist-c, run-kill-d, and
    # build-20260914-fit, whose run id lacks the run- prefix), two not (the pinned event logs L2 and
    # L5), listed in name order; six other files (four .md, a .log, the table).
    candidates_line(7, 5, 5, 2),
    pinned_line(2),
    "  - `%s`" % PINNED[1],
    "  - `%s`" % PINNED[3],
    others_line(6),
    "- Records read: 4 with events in the interval, 1 outside it; 4 without run-open (counted like any other).",
    "- Records holding invalid or undated lines: 0, each named in the detail in every report until mended.",
    "- Episodes open or unresolved at acquisition: 0 (0 opened after the interval's end; 0 unresolved by an "
    "invalid close or opening), named in the detail; such an episode counts nowhere until a valid close resolves it.",
    "- Runs open at acquisition: 0.",
    "- Lines under a historical event name (FIELDS.md): 0, each marked in the detail.",
    # 23 named gaps: durations 1 null + 2 absent; 1 status outside; 1 null rewrites; 1 null
    # rewrites_total; tool 1 "unknown" + 3 absent, fence 3 absent (6 "not on the close"); sandbox
    # 7; 1 null head_denials; spend 1 unknown basis + 1 undeclared.
    "- Named gaps affecting this interval's figures: 23:",
    "  - a price with no cost_src: its basis is undeclared: 1 (affects Priced spend)",
    "  - denials are not on the close: 6 (affects Refusals)",
    "  - denials are recorded as \"unknown\": 1 (affects Refusals)",
    "  - duration_s is not on the close: 2 (affects Helper time)",
    "  - duration_s is recorded as null: 1 (affects Helper time)",
    "  - exit_class '\u2026' is outside the writers' vocabulary: 1 (affects Failed closes)",
    "  - head_denials is recorded as null: 1 (affects Refusals)",
    "  - no cost_src and no price on the close: 1 (affects Priced spend)",
    "  - no sandbox channel on the close: 7 (affects Refusals)",
    "  - rewrites is recorded as null: 1 (affects Phase boundaries)",
    "  - rewrites_total is recorded as null: 1 (affects Phase boundaries)",
]

V0 = " (0 not applicable, 0 unknown or invalid; 0 named gaps (detail))"
V01 = " (0 not applicable, 1 unknown or invalid; 0 named gaps (detail))"
ALL_A = "- (all): unknown; known subtotal 6600.75 s (110.0 min) over 11 closes (3 unknown or invalid; 0 named gaps (detail))"
SCENE_A_VIEWS = {
    # The three views count the same 11 episodes and the same 6600.75 s; a view row with an
    # unknown duration reads unknown with its known subtotal, in the detail as in the main report.
    # Keys in name order: run-a sorts before run-hist-c, run-kill-d and run-plain-b.
    "### By run": ["- run-a: unknown; known subtotal 4800.5 s (80.0 min) over 6 closes (1 not applicable, 1 unknown or invalid; 0 named gaps (detail))",
                   "- run-hist-c: unknown; known subtotal 600 s (10.0 min) over 2 closes" + V01,
                   "- run-kill-d: unknown; known subtotal 0 s (0.0 min) over 1 close" + V01,
                   "- run-plain-b: 1200.25 s (20.0 min) over 2 closes" + V0,
                   ALL_A],
    "### By class": ["- builder: unknown; known subtotal 1800 s (30.0 min) over 3 closes (1 not applicable, 1 unknown or invalid; 0 named gaps (detail))",
                     "- critic: unknown; known subtotal 3000.5 s (50.0 min) over 5 closes" + V01,
                     "- reflector: 600 s (10.0 min) over 1 close" + V0,
                     "- verifier: unknown; known subtotal 0 s (0.0 min) over 1 close" + V01,
                     "- writer: 1200.25 s (20.0 min) over 1 close" + V0,
                     ALL_A],
    "### By helper": ['- run-a/"B1": 1800 s (30.0 min) over 1 close' + V0,
                      '- run-a/"B2": 0 s (0.0 min) over 1 close (1 not applicable, 0 unknown or invalid; 0 named gaps (detail))',
                      '- run-a/"CR-1": 1500.5 s (25.0 min) over 1 close' + V0,
                      '- run-a/"CR-2": 1500 s (25.0 min) over 2 closes' + V0,
                      '- run-a/"V1": unknown; known subtotal 0 s (0.0 min) over 1 close' + V01,
                      '- run-hist-c/"H1": unknown; known subtotal 0 s (0.0 min) over 1 close' + V01,
                      '- run-hist-c/"H2": 600 s (10.0 min) over 1 close' + V0,
                      '- run-kill-d/"K1": unknown; known subtotal 0 s (0.0 min) over 1 close' + V01,
                      '- run-plain-b/"B1": 1200.25 s (20.0 min) over 1 close' + V0,
                      '- run-plain-b/"CR-9": 0 s (0.0 min) over 1 close' + V0,
                      ALL_A],
}

# ------------------------------------------------------------------------ cases ------------

CASES = []
ROUTE_CASES = {}            # the class "record content stops the report", closed by route (this fold)
CR4_CASES = {}              # CR-WASTE4's findings (the fourth fold)
CR3_CASES = {}              # CR-WASTE3's findings (the third fold; 1 is the input contract, now B17)
FINDING_CASES = {}          # CR-WASTE2's findings (the second fold)
CR1_CASES = {}              # CR-WASTE1's findings (the first fold)
B17_CASES = {}              # the owner's input contract, decision B17 (B-WASTE14's fold)
CR5_CASES = {}              # CR-WASTE5's findings (B-WASTE15's fold; 2 is the generated records)
CR6_CASES = {}              # CR-WASTE6's findings (B-WASTE16's fold)
CR6_FAMILIES = {}           # the family of each CR-WASTE6 finding, closed (B-WASTE16's fold; 4 is the generated records)


def case(test, name, finding=None, cr1=None, cr3=None, cr4=None, route=None, b17=None, cr5=None, cr6=None, family=None):
    def deco(fn):
        full = "T%d.%s" % (test, name)
        CASES.append((full, test, fn))
        for tags, store in ((finding, FINDING_CASES), (cr1, CR1_CASES), (cr3, CR3_CASES), (cr4, CR4_CASES),
                            (route, ROUTE_CASES), (b17, B17_CASES), (cr5, CR5_CASES), (cr6, CR6_CASES),
                            (family, CR6_FAMILIES)):
            for f in ((tags,) if isinstance(tags, int) else (tags or ())):
                store.setdefault(f, []).append(full)
        return fn
    return deco


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def expect_rows(main, want):
    err = compare_rows(rows_of(main), want)
    expect(err is None, err)


def last_line(err):
    """The last line of a run's stderr: an abort's exception, named."""
    lines = [l for l in (err or "").strip().split("\n") if l.strip()]
    return lines[-1][:300] if lines else "no stderr"


@case(1, "scene-a-table", finding=1, cr1=(3, 4, 5))
def t1_table(ctx):
    fx = Fx(ctx.root, "scene-a", script=ctx.script)
    scene_a(fx)
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d: %s" % (code, err))
    expect_rows(main, SCENE_A_ROWS)


@case(1, "scene-a-coverage-and-header", finding=1, cr3=1)
def t1_coverage(ctx):
    fx = Fx(ctx.root, "scene-a", script=ctx.script)
    scene_a(fx)
    code, out, err, main, detail = fx.report()
    got = section(main, "## Coverage by reason")
    expect(got == SCENE_A_COVERAGE, "coverage differs:\n%s" % "\n".join(
        "got  %s\nwant %s" % (g, w) for g, w in zip(got + [""] * 30, SCENE_A_COVERAGE + [""] * 30) if g != w))
    want_head = [
        "# Weekly waste report, records only: 2026-10-05..2026-10-12",
        "- Interval: [2026-10-05 00:00 +0100, 2026-10-12 00:00 +0100), local time (GMT/BST).",
        "- Detail: [waste-detail-2026-10-12.md](waste-detail-2026-10-12.md), every named gap with the figures it affects.",
        "1 linked in the detail (each run's own table, by path, never regenerated or read).",
    ]
    for line in want_head:
        expect(line in main.split("\n"), "missing line: %s" % line)
    expect(os.path.exists(os.path.join(fx.tools, "reports", "waste-detail-2026-10-12.md")), "detail missing")
    want_keys = ["- %s@2026-10-05..2026-10-12: listed by this report; open" % k for k in (
        "helper-time", "failed-closes", "review-activity", "phase-boundaries", "refusals",
        "priced-spend", "coverage")]
    got_keys = dispositions_lines(main)
    expect(got_keys == want_keys, "keys: %r" % got_keys)


@case(1, "scene-a-views-reconcile", cr1=3)
def t1_views(ctx):
    fx = Fx(ctx.root, "scene-a", script=ctx.script)
    scene_a(fx)
    code, out, err, main, detail = fx.report()
    lines = detail.split("\n")
    for head, want_lines in SCENE_A_VIEWS.items():
        i = lines.index(head)
        got = lines[i + 1:i + 1 + len(want_lines)]
        expect(got == want_lines, "%s:\n%s" % (head, "\n".join(got)))


@case(1, "scene-a-detail-states-and-gaps", finding=1, cr1=3, cr3=1)
def t1_detail(ctx):
    fx = Fx(ctx.root, "scene-a", script=ctx.script)
    scene_a(fx)
    code, out, err, main, detail = fx.report()
    for needle in (
        # The null rewrites_total is a named snapshot gap, no longer dropped silently.
        "- run-a.jsonl:19 · 2026-10-05 13:00:00 +0100 · rewrites_total is recorded as null · affects: Phase boundaries: rewrites snapshots",
        "- run-a.jsonl:19 · 2026-10-05 13:00:00 +0100 · phase-boundary · unknown (rewrites_total is recorded as null)",
        "- run-a.jsonl:20 · 2026-10-05 13:30:00 +0100 · head-exit · spent_usd 13.75",
        "- run-a.jsonl:2 · 2026-10-05 09:05:00 +0100 · gate · run_spend_usd 9.0",
        "- run-a.jsonl:12 · 2026-10-05 11:30:00 +0100 · phase-boundary · rewrites_total 3",
        # Every value state shows: measured zero, known, not applicable, unknown.
        '| run-plain-b:"CR-9":3 | critic | lane-open line 3, 2026-10-06 11:00:00 +0100 | lane-closed line 4, 2026-10-06 11:10:00 +0100 | 0 (measured zero) |',
        '| run-a:"B2":16 | builder | lane-open line 16, 2026-10-05 12:10:00 +0100 | lane-closed line 17, 2026-10-05 12:10:30 +0100 | not applicable (no process started (exit_class spawn-failed)) |',
        '| run-a:"V1":14 | verifier | lane-open line 14, 2026-10-05 11:40:00 +0100 | lane-closed line 15, 2026-10-05 12:00:00 +0100 | unknown (duration_s is recorded as null) |',
        '| run-a:"CR-2":10 | critic | lane-resumed line 10, 2026-10-05 11:00:00 +0100 | lane-closed line 11, 2026-10-05 11:20:00 +0100 | 900 |',
        "limit (later resumed)",
        'run-plain-b:"B1":1 | writer | lane-open line 1, 2026-10-06 10:00:00 +0100 | lane-closed line 2, 2026-10-06 10:20:00.25 +0100 | 1200.25',
        # Named gaps with the parts they affect, each on its own identity.
        '- run-hist-c.jsonl:2 "H1" · 2026-10-07 08:30:00 +0100 · duration_s is not on the close · affects: Helper time',
        '- run-kill-d.jsonl:2 "K1" · 2026-10-08 10:30:00 +0100 · duration_s is not on the close · affects: Helper time',
        '- run-a.jsonl:15 "V1" · 2026-10-05 12:00:00 +0100 · duration_s is recorded as null · affects: Helper time',
        '- run-hist-c.jsonl:2 "H1" · 2026-10-07 08:30:00 +0100 · exit_class \'complete\' is outside the writers\' vocabulary · affects: Failed closes',
        '- run-a.jsonl:15 "V1" · 2026-10-05 12:00:00 +0100 · denials are recorded as "unknown" · affects: Refusals: helper tool',
        '- run-a.jsonl:5 "B1" · 2026-10-05 09:40:00 +0100 · no sandbox channel on the close · affects: Refusals: helper sandbox',
        "- run-a.jsonl:19 · 2026-10-05 13:00:00 +0100 · head_denials is recorded as null · affects: Refusals: head fence",
        "- run-a.jsonl:19 · 2026-10-05 13:00:00 +0100 · rewrites is recorded as null · affects: Phase boundaries",
        '- run-hist-c.jsonl:4 "H2" · 2026-10-07 09:00:00 +0100 · a price with no cost_src: its basis is undeclared · affects: Priced spend: closes',
        '- run-a · item item1 · 3 reviewing-class episodes from 2 helpers ("CR-1" critic, "CR-2" critic) · gate line 2 · grouped by position, not an evidenced association · two or more: a cue for the Sunday walk-through, not an evidenced loop · rounds unresolved',
        '- run-a · item item2 · 1 reviewing-class episode from 1 helper ("V1" verifier) · gate line 13 · grouped by position, not an evidenced association · rounds unresolved',
        '- run-plain-b "CR-9" (critic) · no positional group: no gate before its opening on the record',
        '- run-hist-c "H1" (critic) · no positional group: no gate before its opening on the record',
        # The pinned event logs are listed, never opened: what they hold is unknown.
        "| %s | %s | - | - | - | - | - | - | - |" % (PINNED[1], NOT_ADMITTED_CELL),
        "| %s | %s | - | - | - | - | - | - | - |" % (PINNED[3], NOT_ADMITTED_CELL),
        # Each plan close shows the writer's state and each token direction (finding 2).
        "| plan usage, complete; input 1000, output 200 |",
        "| plan usage, incomplete; input 500, output 50 |",
        "| plan usage, complete; input 300, output 30 |",
        "| plan usage, missing (no usage reported) |",
        "- run-a: [run-a-waste-table.md](<",
        "- priced closes, sum of the recorded values: $3.75 (the main report rounds to the cent)",
        "- run-a.jsonl:12 · 2026-10-05 11:30:00 +0100 · from 'item1' to 'item2' · idle_min 12.5 (transcript) · over_cap_reports 1 · rewrites 3 (cumulative 3) · denials 0 · head_denials 2 (2 head-fence deny lines) · run_spend_usd 10.0",
    ):
        expect(needle in detail, "detail lacks: %s" % needle)
    expect(section(detail, "## Episodes open or unresolved at acquisition") == ["- none"], "open list not empty")


# Finding 4 of CR-WASTE2: every line of scene A's detail, fixed by hand from the fixture and the
# definitions (FIELDS.md), so a change to any rendered value, the ordinary run-close snapshot's
# 15.0 included, fails. Byte sizes are the fixture files' own (os.path.getsize, never the reader).
# Named gaps sort by place, then reason, then parts: run-a.jsonl:15 sorts before :19 and :5.
SCENE_A_GAPS = [
    '- run-a.jsonl:15 "V1" · 2026-10-05 12:00:00 +0100 · denials are recorded as "unknown" · affects: Refusals: helper tool',
    '- run-a.jsonl:15 "V1" · 2026-10-05 12:00:00 +0100 · duration_s is recorded as null · affects: Helper time',
    '- run-a.jsonl:15 "V1" · 2026-10-05 12:00:00 +0100 · no sandbox channel on the close · affects: Refusals: helper sandbox',
    "- run-a.jsonl:19 · 2026-10-05 13:00:00 +0100 · head_denials is recorded as null · affects: Refusals: head fence",
    "- run-a.jsonl:19 · 2026-10-05 13:00:00 +0100 · rewrites is recorded as null · affects: Phase boundaries",
    "- run-a.jsonl:19 · 2026-10-05 13:00:00 +0100 · rewrites_total is recorded as null · affects: Phase boundaries: rewrites snapshots",
    '- run-a.jsonl:5 "B1" · 2026-10-05 09:40:00 +0100 · no sandbox channel on the close · affects: Refusals: helper sandbox',
    '- run-hist-c.jsonl:2 "H1" · 2026-10-07 08:30:00 +0100 · denials are not on the close · affects: Refusals: helper fence',
    '- run-hist-c.jsonl:2 "H1" · 2026-10-07 08:30:00 +0100 · denials are not on the close · affects: Refusals: helper tool',
    '- run-hist-c.jsonl:2 "H1" · 2026-10-07 08:30:00 +0100 · duration_s is not on the close · affects: Helper time',
    '- run-hist-c.jsonl:2 "H1" · 2026-10-07 08:30:00 +0100 · exit_class \'complete\' is outside the writers\' vocabulary · affects: Failed closes',
    '- run-hist-c.jsonl:2 "H1" · 2026-10-07 08:30:00 +0100 · no cost_src and no price on the close · affects: Priced spend: closes',
    '- run-hist-c.jsonl:2 "H1" · 2026-10-07 08:30:00 +0100 · no sandbox channel on the close · affects: Refusals: helper sandbox',
    '- run-hist-c.jsonl:4 "H2" · 2026-10-07 09:00:00 +0100 · a price with no cost_src: its basis is undeclared · affects: Priced spend: closes',
    '- run-hist-c.jsonl:4 "H2" · 2026-10-07 09:00:00 +0100 · denials are not on the close · affects: Refusals: helper fence',
    '- run-hist-c.jsonl:4 "H2" · 2026-10-07 09:00:00 +0100 · denials are not on the close · affects: Refusals: helper tool',
    '- run-hist-c.jsonl:4 "H2" · 2026-10-07 09:00:00 +0100 · no sandbox channel on the close · affects: Refusals: helper sandbox',
    '- run-kill-d.jsonl:2 "K1" · 2026-10-08 10:30:00 +0100 · denials are not on the close · affects: Refusals: helper fence',
    '- run-kill-d.jsonl:2 "K1" · 2026-10-08 10:30:00 +0100 · denials are not on the close · affects: Refusals: helper tool',
    '- run-kill-d.jsonl:2 "K1" · 2026-10-08 10:30:00 +0100 · duration_s is not on the close · affects: Helper time',
    '- run-kill-d.jsonl:2 "K1" · 2026-10-08 10:30:00 +0100 · no sandbox channel on the close · affects: Refusals: helper sandbox',
    '- run-plain-b.jsonl:2 "B1" · 2026-10-06 10:20:00.25 +0100 · no sandbox channel on the close · affects: Refusals: helper sandbox',
    '- run-plain-b.jsonl:4 "CR-9" · 2026-10-06 11:10:00 +0100 · no sandbox channel on the close · affects: Refusals: helper sandbox',
]
NA_SPAWN = "not applicable (no process started (exit_class spawn-failed))"
NO_SB = "unknown (no sandbox channel on the close)"
NO_DEN = "unknown (denials are not on the close)"
Z0 = "0 (measured zero)"
G_LINE = "item %s (by position: the last gate before its opening, line %d)"
NO_GATE = "none: no gate before its opening on the record"
# The episodes closing in the interval, in the order of the records (by name) and of the closes in
# each: run-a (B1, CR-1, CR-2, CR-2 resumed, V1, B2), run-hist-c (H1, H2), run-kill-d (K1),
# run-plain-b (B1, CR-9). Decimal values print as recorded less trailing zeros (1800.0 -> 1800);
# priced dollars to at least two places.
SCENE_A_EPISODE_ROWS = [
    '| run-a:"B1":3 | builder | lane-open line 3, 2026-10-05 09:10:00 +0100 | lane-closed line 5, 2026-10-05 09:40:00 +0100 | 1800 | completed | 1 | 2 | %s | priced $2.50 | - |' % NO_SB,
    '| run-a:"CR-1":6 | critic | lane-open line 6, 2026-10-05 09:45:00 +0100 | lane-closed line 7, 2026-10-05 10:15:00 +0100 | 1500.5 | completed | %s | %s | 3 | plan usage, complete; input 1000, output 200 | %s |' % (Z0, Z0, G_LINE % ("item1", 2)),
    '| run-a:"CR-2":8 | critic | lane-open line 8, 2026-10-05 10:20:00 +0100 | lane-closed line 9, 2026-10-05 10:50:00 +0100 | 600 | limit (later resumed) | %s | %s | %s | plan usage, incomplete; input 500, output 50 | %s |' % (Z0, Z0, Z0, G_LINE % ("item1", 2)),
    '| run-a:"CR-2":10 | critic | lane-resumed line 10, 2026-10-05 11:00:00 +0100 | lane-closed line 11, 2026-10-05 11:20:00 +0100 | 900 | completed | %s | %s | 1 | plan usage, complete; input 300, output 30 | %s |' % (Z0, Z0, G_LINE % ("item1", 2)),
    '| run-a:"V1":14 | verifier | lane-open line 14, 2026-10-05 11:40:00 +0100 | lane-closed line 15, 2026-10-05 12:00:00 +0100 | unknown (duration_s is recorded as null) | watch-closed | unknown (denials are recorded as "unknown") | 4 | %s | unpriced (a transcript estimate carries no dollar figure) | %s |' % (NO_SB, G_LINE % ("item2", 13)),
    '| run-a:"B2":16 | builder | lane-open line 16, 2026-10-05 12:10:00 +0100 | lane-closed line 17, 2026-10-05 12:10:30 +0100 | %s | spawn-failed | %s | %s | %s | na (no process started (exit_class spawn-failed)) | - |' % (NA_SPAWN, NA_SPAWN, NA_SPAWN, NA_SPAWN),
    '| run-hist-c:"H1":1 | critic | lane-open line 1, 2026-10-07 08:00:00 +0100 | lane-closed line 2, 2026-10-07 08:30:00 +0100 | unknown (duration_s is not on the close) | outside (exit_class \'complete\' is outside the writers\' vocabulary) | %s | %s | %s | unknown-basis (no cost_src and no price on the close) | %s |' % (NO_DEN, NO_DEN, NO_SB, NO_GATE),
    '| run-hist-c:"H2":3 | reflector | lane-open line 3, 2026-10-07 08:40:00 +0100 | lane-closed line 4, 2026-10-07 09:00:00 +0100 | 600 | completed | %s | %s | %s | undeclared $0.50 | - |' % (NO_DEN, NO_DEN, NO_SB),
    '| run-kill-d:"K1":1 | builder | lane-open line 1, 2026-10-08 10:00:00 +0100 | lane-closed line 2, 2026-10-08 10:30:00 +0100 | unknown (duration_s is not on the close) | killed | %s | %s | %s | plan usage, missing (no usage reported) | - |' % (NO_DEN, NO_DEN, NO_SB),
    '| run-plain-b:"B1":1 | writer | lane-open line 1, 2026-10-06 10:00:00 +0100 | lane-closed line 2, 2026-10-06 10:20:00.25 +0100 | 1200.25 | completed | %s | %s | %s | priced $1.25 | - |' % (Z0, Z0, NO_SB),
    '| run-plain-b:"CR-9":3 | critic | lane-open line 3, 2026-10-06 11:00:00 +0100 | lane-closed line 4, 2026-10-06 11:10:00 +0100 | %s | completed | %s | %s | %s | priced $0.00 | %s |' % (Z0, Z0, Z0, NO_SB, NO_GATE),
]
# The dated snapshots in record order, each as recorded (the run-close's 15.0 among them).
SCENE_A_SNAPSHOTS = [
    "- run-a.jsonl:2 · 2026-10-05 09:05:00 +0100 · gate · run_spend_usd 9.0",
    "- run-a.jsonl:12 · 2026-10-05 11:30:00 +0100 · phase-boundary · rewrites_total 3",
    "- run-a.jsonl:12 · 2026-10-05 11:30:00 +0100 · phase-boundary · run_spend_usd 10.0",
    "- run-a.jsonl:13 · 2026-10-05 11:35:00 +0100 · gate · run_spend_usd 10.5",
    "- run-a.jsonl:19 · 2026-10-05 13:00:00 +0100 · phase-boundary · unknown (rewrites_total is recorded as null)",
    "- run-a.jsonl:19 · 2026-10-05 13:00:00 +0100 · phase-boundary · run_spend_usd 14.0",
    "- run-a.jsonl:20 · 2026-10-05 13:30:00 +0100 · head-exit · spent_usd 13.75",
    "- run-a.jsonl:21 · 2026-10-05 14:00:00 +0100 · run-close · run_spend_usd 15.0",
]


def scene_a_detail(fx):
    """Every line of scene A's detail file, the records folder and byte sizes from the fixture."""
    R = os.path.realpath(fx.records)
    size = lambda n: os.path.getsize(os.path.join(fx.records, n))
    na_row = "| %s | " + NOT_ADMITTED_CELL + " | - | - | - | - | - | - | - |"
    out = ["# Weekly waste report detail: 2026-10-05..2026-10-12", "",
           "Companion of waste-report-2026-10-12.md. Read to judge a specific item.", "",
           "## Named gaps and the figures they affect", ""] + SCENE_A_GAPS + [
        "", "## Inventory: every candidate record", "",
        "| Record | Status | Bytes | Lines | First event | Last event | run-open | Invalid or undated lines | Dated order |",
        "|---|---|---|---|---|---|---|---|---|",
        "| build-20260914-fit.jsonl | read | %d | 2 | 2026-09-20 10:00:00 +0100 | 2026-09-20 10:10:00 +0100 | no | 0 | ordered |" % size("build-20260914-fit.jsonl"),
        na_row % PINNED[1],
        na_row % PINNED[3],
        "| run-a.jsonl | read | %d | 21 | 2026-10-05 09:00:00 +0100 | 2026-10-05 14:00:00 +0100 | yes | 0 | ordered |" % size("run-a.jsonl"),
        "| run-hist-c.jsonl | read | %d | 4 | 2026-10-07 08:00:00 +0100 | 2026-10-07 09:00:00 +0100 | no | 0 | ordered |" % size("run-hist-c.jsonl"),
        "| run-kill-d.jsonl | read | %d | 2 | 2026-10-08 10:00:00 +0100 | 2026-10-08 10:30:00 +0100 | no | 0 | ordered |" % size("run-kill-d.jsonl"),
        "| run-plain-b.jsonl | read | %d | 4 | 2026-10-06 10:00:00 +0100 | 2026-10-06 11:10:00 +0100 | no | 0 | ordered |" % size("run-plain-b.jsonl"),
        "", "## Records holding invalid or undated lines (named in every report)", "", "- none",
        "", "## Episodes open or unresolved at acquisition", "", "- none",
        "", "## Runs open at acquisition", "", "- none",
        "", "## Episodes closing in the interval", "",
        "| Episode | Class | Opening | Close | Duration | Exit | Tool | Fence | Sandbox | Spend basis | Positional group |",
        "|---|---|---|---|---|---|---|---|---|---|---|"] + SCENE_A_EPISODE_ROWS + [
        "", "## Lines under a historical event name (named in every report)", "",
        "Read by the compatibility rule in FIELDS.md: an opening or close under a historical name reads as "
        "the writers' event, its values from the writers' field names only; an end marker closes nothing "
        "and is noted on the episode it follows.", "", "- none",
        "", "## Helper time by run, class and helper", "",
        "The three views count the same episodes; concurrent durations add as helper consumption, not "
        "elapsed time. A view total is unknown when any of its closes has no usable duration or a named "
        "gap reaches it.", ""]
    for head in ("### By run", "### By class", "### By helper"):
        out += [head] + SCENE_A_VIEWS[head] + [""]
    out += ["## Review activity: reviewing-class episodes and positional candidate groups", "",
            "Whether repeated review of one item was a loop is judged in the Sunday walk-through under "
            "CUSTOMISATION.md's rules \"Rounds are judged by progress, not counted\" and \"Stopped designs\".", "",
            "- Evidenced item associations: none recorded. No opening or close records the item it serves "
            "(FIELDS.md), so no episode is tied to an item by the record, and rounds stay unresolved.",
            "- Reviewing-class episodes are counted by class alone (critic, verifier, gate-judge); a class is "
            "not evidence that an episode reviewed anything.",
            "- Positional candidate groups gather the reviewing-class episodes whose last gate before the "
            "opening is dated, allowed and names an item, with no gate between the opening and the close: a "
            "cue for the walk-through, not an association.", "",
            '- run-a · item item1 · 3 reviewing-class episodes from 2 helpers ("CR-1" critic, "CR-2" critic) · gate '
            "line 2 · grouped by position, not an evidenced association · two or more: a cue for the Sunday "
            "walk-through, not an evidenced loop · rounds unresolved",
            '- run-a · item item2 · 1 reviewing-class episode from 1 helper ("V1" verifier) · gate line 13 · '
            "grouped by position, not an evidenced association · rounds unresolved",
            '- run-hist-c "H1" (critic) · no positional group: no gate before its opening on the record',
            '- run-plain-b "CR-9" (critic) · no positional group: no gate before its opening on the record',
            "", "## Phase boundaries", "",
            "- run-a.jsonl:12 · 2026-10-05 11:30:00 +0100 · from 'item1' to 'item2' · idle_min 12.5 (transcript) "
            "· over_cap_reports 1 · rewrites 3 (cumulative 3) · denials 0 · head_denials 2 (2 head-fence deny "
            "lines) · run_spend_usd 10.0",
            "- run-a.jsonl:19 · 2026-10-05 13:00:00 +0100 · from 'item2' to 'item3' · idle_min 5.0 (record) · "
            "over_cap_reports 0 · rewrites None (cumulative None) · denials 1 · head_denials None (None) · "
            "run_spend_usd 14.0",
            "", "## Cumulative snapshots (dated, never summed)", ""] + SCENE_A_SNAPSHOTS + [
            # 2.5 + 1.25 + 0 = 3.75 over the priced closes; the beat's 0.05 is in the main total only. By
            # session: each of the four priced lines (B1's close s-b1 and its beat s-b1-hold, plain B1 s-pb1, CR-9
            # s-cr9) names a session of its own, one line each, so 2.5 + 0.05 + 1.25 + 0 = 3.80, a known subtotal
            # (H1's unknown basis and H2's undeclared price reach it); no session holds two lines.
            "", "## Priced spend, exact", "",
            "- priced closes, sum of the recorded values: $3.75 (the main report rounds to the cent)",
            SESSION_ROW % ("unknown; known subtotal $3.80", "4 sessions"),
            SESSION_READ % (0, 0, 0, 4),
            SESSION_LISTED % 0,
            "", "## Hold beats", "",
            "- run-a.jsonl:18 · 2026-10-05 12:30:00 +0100 · cost_src result · total_cost_usd 0.05",
            "", "## Per-run waste tables (linked by path, never read)", "",
            "- run-a: [run-a-waste-table.md](<%s/run-a-waste-table.md>)" % R, ""]
    return out


def first_difference(got, want):
    for i in range(max(len(got), len(want))):
        g = got[i] if i < len(got) else "<none>"
        w = want[i] if i < len(want) else "<none>"
        if g != w:
            return "line %d (%d got, %d want):\n got  %s\n want %s" % (i + 1, len(got), len(want), g, w)
    return None


@case(1, "scene-a-detail-every-line", finding=4, cr3=1)
def t1_detail_every_line(ctx):
    fx = Fx(ctx.root, "scene-a", script=ctx.script)
    scene_a(fx)
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d: %s" % (code, err))
    got = detail.split("\n")
    # The ordinary run-close snapshot's rendered amount first, then every other line.
    expect(SCENE_A_SNAPSHOTS[-1] in got, "the run-close snapshot line is not rendered as recorded: %r"
           % [l for l in got if "run-close" in l])
    diff = first_difference(got, scene_a_detail(fx))
    expect(diff is None, diff)


def scene_a_main(fx):
    """Every line of scene A's main report but the acquisition and runtime lines (masked)."""
    rows = ["| " + " | ".join(r) + " |" for r in SCENE_A_ROWS]
    keys = ["- %s@2026-10-05..2026-10-12: listed by this report; open" % k for k in (
        "helper-time", "failed-closes", "review-activity", "phase-boundaries", "refusals",
        "priced-spend", "coverage")]
    return ["# Weekly waste report, records only: 2026-10-05..2026-10-12", "",
            "The weekly report shows recorded helper consumption and recorded operational outcomes across "
            "runs, so the Sunday review can identify concentrations and possible recurrence. It does not "
            "measure avoidable time or certify that a week contained no waste. Fine-grained diagnosis "
            "remains in each run's own evidence.", "",
            "- Interval: [2026-10-05 00:00 +0100, 2026-10-12 00:00 +0100), local time (GMT/BST).",
            "- Episodes count wholly at their close; boundary events at their own timestamps. Report "
            "generation succeeding is not evidence of completeness.",
            "- Detail: [waste-detail-2026-10-12.md](waste-detail-2026-10-12.md), every named gap with the "
            "figures it affects.", "", "## Coverage by reason", ""] + SCENE_A_COVERAGE + [
            "", "## Figures", "",
            "Each total is complete only when every input it declares is available; otherwise it reads "
            "unknown with its known subtotal. A missing field is never a zero. A gap counts only against "
            "the parts, runs, helpers, classes, idle sources and spend bases its input could feed.", "",
            "| Figure | Part | Value | Status | Coverage |", "|---|---|---|---|---|"] + rows + [
            "", "Whether repeated review of one item was a loop is judged in the Sunday walk-through under "
            "CUSTOMISATION.md's rules \"Rounds are judged by progress, not counted\" and \"Stopped designs\".",
            "", "## Determinations applied", "", "- none", "", "## Dispositions", "",
            "The store `%s` is the one authority; editing this list changes nothing. Record one with "
            "`weekly-waste.py dispose <key> <fixed|registered|kept|owner> --note \"...\"`."
            % os.path.join(os.path.realpath(fx.tools), "dispositions.jsonl"), ""] + keys + [
            "", "Recorded since the previous report:", "", "- none", "", "## Per-run waste tables", "",
            "1 linked in the detail (each run's own table, by path, never regenerated or read).", "", ""]


@case(1, "scene-a-main-every-line", finding=4, cr3=1)
def t1_main_every_line(ctx):
    fx = Fx(ctx.root, "scene-a", script=ctx.script)
    scene_a(fx)
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d: %s" % (code, err))
    got = [l for l in main.split("\n") if not l.startswith("- Acquired:") and not l.startswith("- Runtime:")]
    expect(len(got) == len(main.split("\n")) - 2, "the acquisition and runtime lines are not one each")
    diff = first_difference(got, scene_a_main(fx))
    expect(diff is None, diff)


@case(1, "parallel-resume-cumulative")
def t1_parallel(ctx):
    # Concurrent durations add; a resumed helper's episodes each count once; repeated cumulative
    # totals are snapshots. P1 3600 + P2 3600 (overlapping 10:30-11:00) + P1 resumed 600 = 7800 s;
    # 7800/60 = 130.0. Boundaries: rewrites deltas 5 then 0 = 5; cumulative 5 and 5 listed as two
    # snapshots and never added; run_spend_usd 7.0 twice: two spend snapshots.
    fx = Fx(ctx.root, "parallel", script=ctx.script)
    c = {"cost_src": "codex-plan", "total_cost_usd": None, "harness": "codex", "class": "builder",
         "exit_class": "completed", "usage": {"input_tokens": 1, "output_tokens": 1, "calls": 1},
         "usage_state": "complete", "usage_complete": True, "sandbox_denials": 0,
         "denials": {"tool": 0, "fence": 0, "sandbox": 0}}
    fx.write("run-par.jsonl", [
        {"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "P1", "harness": "codex", "class": "builder"},
        {"ts": "2026-10-06T10:30:00+0100", "event": "lane-open", "lane": "P2", "harness": "codex", "class": "builder"},
        dict(c, ts="2026-10-06T11:00:00+0100", event="lane-closed", lane="P1", duration_s=3600.0),
        dict(c, ts="2026-10-06T11:30:00+0100", event="lane-closed", lane="P2", duration_s=3600.0),
        {"ts": "2026-10-06T11:40:00+0100", "event": "lane-resumed", "lane": "P1", "harness": "codex", "class": "builder"},
        dict(c, ts="2026-10-06T11:50:00+0100", event="lane-closed", lane="P1", duration_s=600.0),
        {"ts": "2026-10-06T12:00:00+0100", "event": "phase-boundary", "idle_min": 1.0, "idle_src": "transcript",
         "denials": 0, "head_denials": 0, "over_cap_reports": 0, "rewrites": 5, "rewrites_total": 5,
         "run_spend_usd": 7.0},
        {"ts": "2026-10-06T13:00:00+0100", "event": "phase-boundary", "idle_min": 1.0, "idle_src": "transcript",
         "denials": 0, "head_denials": 0, "over_cap_reports": 0, "rewrites": 0, "rewrites_total": 5,
         "run_spend_usd": 7.0},
    ])
    code, out, err, main, detail = fx.report()
    m = as_map(rows_of(main))
    expect(m[(H, "total")] == ("7800 s (130.0 min)", "complete",
                               "3 closes: 3 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "total %r" % (m[(H, "total")],))
    expect(m[(H, 'helper run-par/"P1"')] == ("4200 s (70.0 min)", "complete", "2 closes: 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "P1 %r" % (m[(H, 'helper run-par/"P1"')],))
    expect(m[(H, 'helper run-par/"P2"')][0] == "3600 s (60.0 min)", "P2 %r" % (m[(H, 'helper run-par/"P2"')],))
    expect(m[(F, "closes")][0] == "3", "closes %r" % (m[(F, "closes")],))
    expect(m[(B, "rewrites (deltas)")][0] == "5", "rewrites %r" % (m[(B, "rewrites (deltas)")],))
    expect(m[(B, "recorded idle, idle_src transcript")][0] == "2 min", "idle")
    expect(m[(B, "cumulative rewrites snapshots")] == ("2", "complete", BS_COV % 0), "rewrites snapshots %r" % (m[(B, "cumulative rewrites snapshots")],))
    expect(m[SP_SS] == ("2", "complete", SS_COV % 0), "spend snapshots %r" % (m[SP_SS],))
    # Three complete plan closes of 1 token in and 1 out each: 3 in, 3 out.
    expect(m[SP_TCI][:2] == ("3", "complete") and m[SP_TCO][:2] == ("3", "complete"),
           "tokens %r %r" % (m[SP_TCI], m[SP_TCO]))


# CR-WASTE5 finding 2 (B-WASTE15's fold): every sum of recorded decimals is exact within the reader's
# range, and the three helper-time views reconcile to the same exact total. The sums below were fixed by
# hand and checked at 200 digits of decimal precision, never by the reader.
MIXED_TOTAL = "999999999999999.000000000000120000000000000001"     # 999999999999999 + 3 x 4e-14 + 1e-30


@case(1, "mixed-scale-durations-reconcile-exactly", cr5=3)
def t1_mixed_scale(ctx):
    # run-big: A (builder) 999999999999999 s, the largest within the range, and B, C, D (writer) 0.00000000000004 s
    # each; run-tiny: E (reflector) 0.000000000000000000000000000001 s, the most places within it. Exactly:
    # total 999999999999999.000000000000120000000000000001 s (45 digits); run-big 999999999999999.00000000000012;
    # builder 999999999999999, writer 0.00000000000012. Minutes, half-even to 0.1 from the exact value: the
    # total /60 = 16666666666666.65000000000000200...: 16666666666666.7; builder 16666666666666.65 exactly, a
    # tie: 16666666666666.6 (even). The B-WASTE14 version summed under 28 digits: its total lost every small
    # duration (999999999999999 s, 16666666666666.6 min) and its class view's `all` line kept 0.0000000000001 of
    # them, so its three views disagreed.
    fx = Fx(ctx.root, "t1-mixed-scale", script=ctx.script)
    fx.write("run-big.jsonl", plan_episode("A", "builder", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", Raw("999999999999999"))
             + plan_episode("B", "writer", "2026-10-06T10:02:00+0100", "2026-10-06T10:03:00+0100", Raw("0.00000000000004"))
             + plan_episode("C", "writer", "2026-10-06T10:04:00+0100", "2026-10-06T10:05:00+0100", Raw("0.00000000000004"))
             + plan_episode("D", "writer", "2026-10-06T10:06:00+0100", "2026-10-06T10:07:00+0100", Raw("0.00000000000004")))
    fx.write("run-tiny.jsonl", plan_episode("E", "reflector", "2026-10-06T10:08:00+0100", "2026-10-06T10:09:00+0100",
                                            Raw("0.000000000000000000000000000001")))
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d: %s" % (code, last_line(err)))
    big, tiny, w1, w3 = "999999999999999", "0.000000000000000000000000000001", "0.00000000000004", "0.00000000000012"
    rb = "999999999999999.00000000000012"
    total = MIXED_TOTAL + " s (16666666666666.7 min)"
    s = lambda v, m: "%s s (%s min)" % (v, m)
    cov = lambda k: "%s: 0 not applicable, 0 unknown or invalid; %s" % (pl(k, "close"), GAPS0)
    want = builder_rows(5, total, {}, {'run-big/"A"': s(big, "16666666666666.6"), 'run-big/"B"': s(w1, "0.0"), 'run-big/"C"': s(w1, "0.0")})
    del want[(H, "class builder")]
    want.update({(H, "run run-big"): (s(rb, "16666666666666.7"), "complete", cov(4)),
                 (H, "run run-tiny"): (s(tiny, "0.0"), "complete", cov(1)),
                 (H, "class builder"): (s(big, "16666666666666.6"), "complete", cov(1)),
                 (H, "class writer"): (s(w3, "0.0"), "complete", cov(3)),
                 (H, "class reflector"): (s(tiny, "0.0"), "complete", cov(1))})
    e = compare_map(rows_of(main), want)
    expect(e is None, e)
    all_line = "- (all): %s over 5 closes (0 unknown or invalid; 0 named gaps (detail))" % total
    views = {"### By run": ["- run-big: %s over 4 closes%s" % (s(rb, "16666666666666.7"), V0),
                            "- run-tiny: %s over 1 close%s" % (s(tiny, "0.0"), V0), all_line],
             "### By class": ["- builder: %s over 1 close%s" % (s(big, "16666666666666.6"), V0),
                              "- reflector: %s over 1 close%s" % (s(tiny, "0.0"), V0),
                              "- writer: %s over 3 closes%s" % (s(w3, "0.0"), V0), all_line],
             "### By helper": ['- run-big/"A": %s over 1 close%s' % (s(big, "16666666666666.6"), V0)]
                              + ["- run-big/%s: %s over 1 close%s" % (json.dumps(h), s(w1, "0.0"), V0) for h in "BCD"]
                              + ['- run-tiny/"E": %s over 1 close%s' % (s(tiny, "0.0"), V0), all_line]}
    lines = detail.split("\n")
    for head, want_lines in views.items():
        i = lines.index(head)
        got = lines[i + 1:i + 1 + len(want_lines)]
        expect(got == want_lines, "%s:\n%s" % (head, first_difference(got, want_lines)))


# ------------------------------------------------------------------------ test 2 -----------
# One plan-usage critic close with every field complete, a decided gate before it and a boundary
# after. Each case changes one field and fixes by hand the rows that must change, the named gaps
# the detail lists and the cells it shows; every other row must equal the base.

def base_events(close_changes=None, close_drop=(), boundary_changes=None, boundary_drop=(),
                open_changes=None, open_drop=(), gate=True, gate_changes=None, gate_drop=(),
                extra=()):
    op = {"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "L", "harness": "codex", "class": "critic"}
    op.update(open_changes or {})
    for k in open_drop:
        op.pop(k, None)
    close = {"ts": "2026-10-06T10:01:30.500+0100", "event": "lane-closed", "lane": "L", "harness": "codex",
             "session_id": "s-L", "class": "critic", "exit_class": "completed", "duration_s": 90.5, "cost_src": "codex-plan",
             "total_cost_usd": None, "usage": {"input_tokens": 10, "output_tokens": 2, "calls": 1},
             "usage_complete": True, "usage_state": "complete", "sandbox_denials": 0,
             "denials": {"tool": 0, "fence": 0, "sandbox": 0}}
    close.update(close_changes or {})
    if close.get("cost_src") == "result" and "usage" not in (close_changes or {}):
        close["usage"] = fixture_inventory(close.get("total_cost_usd"))
    for k in close_drop:
        close.pop(k, None)
    bd = {"ts": "2026-10-06T11:00:00+0100", "event": "phase-boundary", "idle_min": 2.5, "idle_src": "transcript",
          "over_cap_reports": 0, "rewrites": 1, "rewrites_total": 1, "head_denials": 0, "denials": 0,
          "run_spend_usd": 1.0}
    bd.update(boundary_changes or {})
    for k in boundary_drop:
        bd.pop(k, None)
    evs = []
    if gate:
        g = {"ts": "2026-10-06T09:59:00+0100", "event": "gate", "item": "i1", "decision": "allow",
             "run_spend_usd": 0.5}
        g.update(gate_changes or {})
        for k in gate_drop:
            g.pop(k, None)
        evs.append(g)
    return evs + [op, close, bd] + list(extra)


ONE = "1 close: 1 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0
VIEW = "1 close: 0 not applicable, 0 unknown or invalid; " + GAPS0
CH = "1 close: 1 known, 0 not applicable, 0 unknown or invalid; " + GAPS0
BASE = {
    (H, "total"): ("90.5 s (1.5 min)", "complete", ONE),
    (H, "run run-r"): ("90.5 s (1.5 min)", "complete", VIEW),
    (H, "class critic"): ("90.5 s (1.5 min)", "complete", VIEW),
    (H, 'helper run-r/"L"'): ("90.5 s (1.5 min)", "complete", VIEW),
    (F, "closes"): ("1", "complete", GAPS0),
    (F, "completed"): ("1", "complete", "exit_class completed"),
    (F, "non-completed"): ("0", "complete", NONCOMP % (0, 0, GAPS0)),
    (F, "status unknown or invalid"): ("0", "complete", "no usable exit_class"),
    (F, "non-completed, later resumed"): ("0", "complete", LATER),
    (RV, "reviewing-class episodes"): ("1", "complete", RVC_COV % ("0 closes", GAPS0)),
    (RV, "evidenced item associations"): EVID[2:],
    (RV, "positional candidate groups"): ("1", "complete", GROUPS_COV % GAPS0),
    (RV, "reviewing-class episodes with no positional group"): ("0", "complete", NOGROUP_COV),
    (RV, "candidate groups with two or more reviewing-class episodes"): ("0", "complete", MULTI_COV),
    (RV, "rounds"): ROUNDS[2:],
    (B, "boundary events"): ("1", "complete", "counted at their own timestamps; " + GAPS0),
    (B, "recorded idle, idle_src transcript"): ("2.5 min", "complete", IDLE_COV % "1 boundary"),
    (B, "recorded idle unknown"): ("0", "complete", IDLEU_COV),
    (B, "over-cap reports"): ("0", "complete", OVER_COV % "0 boundaries"),
    (B, "rewrites (deltas)"): ("1", "complete", REW_COV % "0 boundaries"),
    (B, "cumulative rewrites snapshots"): ("1", "complete", BS_COV % 0),
    (RF, "helper tool"): ("0", "complete", CH),
    (RF, "helper fence"): ("0", "complete", CH),
    (RF, "helper sandbox"): ("0", "complete", CH),
    (RF, "head fence (boundaries)"): ("0", "complete", HF_COV % ("1 boundary", 0, GAPS0)),
    (RF, "boundary summary of helper tool refusals"): ("0", "complete", HS_COV % ("0 boundaries", GAPS0)),
    SP_T: ("$0.00", "complete", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 0, 0, GAPS0)),
    SP_PC: ("1", "complete", PLAN_COV % (1, 0, 0, 0, 0, 0)),
    SP_TCI: tok(10, 1, 0, tc(1)),
    SP_TCO: tok(2, 1, 0, tc(1)),
    SP_TII: tok(0, 0, 0, ti(0)),
    SP_TIO: tok(0, 0, 0, ti(0)),
    SP_UN: ("0", "complete", "token totals only; no dollar figure"),
    SP_NA: ("0", "complete", "exit_class spawn-failed"),
    SP_HB: ("0", "complete", "plan usage or no process"),
    SP_SS: ("2", "complete", SS_COV % 0),
}
CW = 'run-r.jsonl:3 "L" · 2026-10-06 10:01:30.5 +0100'     # the close
BW = "run-r.jsonl:4 · 2026-10-06 11:00:00 +0100"          # the boundary
GW = "run-r.jsonl:1 · 2026-10-06 09:59:00 +0100"          # the gate
BASE_ROW = ('| run-r:"L":2 | critic | lane-open line 2, 2026-10-06 10:00:00 +0100 | lane-closed line 3, '
            "2026-10-06 10:01:30.5 +0100 | 90.5 | completed | 0 (measured zero) | 0 (measured zero) | "
            "0 (measured zero) | plan usage, complete; input 10, output 2 | item i1 (by position: the "
            "last gate before its opening, line 1) |")


def gl(where, reason, part):
    return "- %s · %s · affects: %s" % (where, reason, part)


def views(value):
    return {(H, "run run-r"): value, (H, "class critic"): value, (H, 'helper run-r/"L"'): value}


UNK_H = ("unknown; known subtotal 0 s (0.0 min)", "unknown", "1 close: 0 timed, 0 not applicable, 1 unknown or invalid; " + GAPS0)
UNK_V = ("unknown; known subtotal 0 s (0.0 min)", "unknown", "1 close: 0 not applicable, 1 unknown or invalid; " + GAPS0)
UNK_CH = "1 close: 0 known, 0 not applicable, 1 unknown or invalid; " + GAPS0


def unk_duration():
    out = {(H, "total"): UNK_H}
    out.update(views(UNK_V))
    return out


def unk_exit(outside=0, unk=1):
    out = {(F, "completed"): ("unknown; known subtotal 0", "unknown", "exit_class completed"),
           (F, "non-completed"): ("unknown; known subtotal 0", "unknown", NONCOMP % (outside, unk, GAPS0))}
    if unk:
        out[(F, "status unknown or invalid")] = ("1", "complete", "no usable exit_class")
    return out


def unk_channel(*chs):
    return dict(((RF, "helper " + ch), ("unknown; known subtotal 0", "unknown", UNK_CH)) for ch in chs)


def basis(kind, price=None):
    """The spend rows for the close's basis, fixed from the definitions: priced and undeclared
    and missing and invalid-price leave the basis counts known; an unknown or invalid basis
    could be any basis, so every basis count reads unknown with its known subtotal."""
    plan0 = ("0", "complete", PLAN_COV % (0, 0, 0, 0, 0, 0))
    out = {SP_PC: plan0, SP_TCI: tok(0, 0, 0, tc(0)), SP_TCO: tok(0, 0, 0, tc(0)),
           SP_TII: tok(0, 0, 0, ti(0)), SP_TIO: tok(0, 0, 0, ti(0))}
    if kind == "priced":
        out[SP_T] = (price, "complete", PRICED_COV % ("1 priced close", "0 priced hold beats", 0, 0, 0, 0, GAPS0))
    elif kind == "missing":
        out[SP_T] = ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 1, 0, 0, 0, GAPS0))
    elif kind == "invalid-price":
        out[SP_T] = ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 1, 0, GAPS0))
    elif kind == "undeclared":
        out[SP_T] = ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 1, 0, 0, GAPS0))
    elif kind == "unpriced":
        out[SP_UN] = ("1", "complete", "token totals only; no dollar figure")
    elif kind in ("invalid-basis", "unknown-basis"):
        out[SP_T] = ("unknown; known subtotal $0.00", "unknown", PRICED_COV % (
            "0 priced closes", "0 priced hold beats", 1 if kind == "unknown-basis" else 0, 0,
            1 if kind == "invalid-basis" else 0, 0, GAPS0))
        out[SP_PC] = ("unknown; known subtotal 0", "unknown", PLAN_COV % (0, 0, 0, 0, 0, 0))
        # The close could be a plan close of any state: every token total is a known subtotal.
        out[SP_TCI] = out[SP_TCO] = tok(0, 0, 0, tc(0), could=1)
        out[SP_TII] = out[SP_TIO] = tok(0, 0, 0, ti(0), could=1)
        out[SP_UN] = ("unknown; known subtotal 0", "unknown", "token totals only; no dollar figure")
        out[SP_NA] = ("unknown; known subtotal 0", "unknown", "exit_class spawn-failed")
    return out


def plan(state):
    """The plan rows when the close's plan state is invalid or unknown: it is a plan close (the
    count is complete) whose tokens could belong to either state, so every token total is a known
    subtotal of 0."""
    counts = (0, 0, 0, 0, 1, 0) if state == "unknown" else (0, 0, 0, 0, 0, 1)
    return {SP_PC: ("1", "complete", PLAN_COV % counts),
            SP_TCI: tok(0, 0, 0, tc(0), could=1), SP_TCO: tok(0, 0, 0, tc(0), could=1),
            SP_TII: tok(0, 0, 0, ti(0), could=1), SP_TIO: tok(0, 0, 0, ti(0), could=1)}


def plan_rows(state, tin, tout):
    """The plan rows for one plan close of a known state (complete, zero or incomplete) whose input
    and output token values are each a number (known) or None (unknown or invalid)."""
    pc = {"complete": (1, 0, 0, 0, 0, 0), "zero": (0, 1, 0, 0, 0, 0), "incomplete": (0, 0, 1, 0, 0, 0)}[state]
    out = {SP_PC: ("1", "complete", PLAN_COV % pc)}
    inc = state == "incomplete"
    members = ti(1) if inc else tc(1)
    rows = ((SP_TII, SP_TIO) if inc else (SP_TCI, SP_TCO))
    for key, v in zip(rows, (tin, tout)):
        out[key] = tok(v or 0, 0 if v is None else 1, 1 if v is None else 0, members,
                       status="incomplete" if inc else None)
    for key in ((SP_TCI, SP_TCO) if inc else (SP_TII, SP_TIO)):
        out[key] = tok(0, 0, 0, tc(0) if inc else ti(0))
    return out


def class_unknown(key):
    return {(RV, "reviewing-class episodes"): ("unknown; known subtotal 0", "unknown", RVC_COV % ("1 close", GAPS0)),
            (RV, "positional candidate groups"): ("unknown; known subtotal 0", "unknown", GROUPS_COV % GAPS0),
            (RV, "reviewing-class episodes with no positional group"): ("unknown; known subtotal 0", "unknown", NOGROUP_COV),
            (RV, "candidate groups with two or more reviewing-class episodes"): ("unknown; known subtotal 0", "unknown", MULTI_COV),
            (H, "class " + key): ("90.5 s (1.5 min)", "complete", VIEW)}


# The one reviewing-class episode has no positional group: it could join a group or form one, so
# both group counts read unknown with their known subtotal 0 (unresolved coverage kept).
NO_GROUP = {(RV, "positional candidate groups"): ("unknown; known subtotal 0", "unknown", GROUPS_COV % GAPS0),
            (RV, "reviewing-class episodes with no positional group"): ("1", "complete", NOGROUP_COV),
            (RV, "candidate groups with two or more reviewing-class episodes"): ("unknown; known subtotal 0", "unknown", MULTI_COV)}
IDLE_UNK = {(B, "recorded idle unknown"): ("1", "complete", IDLEU_COV)}
# The base boundary's idle_min unusable: its own source, transcript, keeps its row, now unknown
# with known subtotal 0 min (finding 3 of CR-WASTE2: only that source's sum depends on it).
IDLE_SRC_UNK = dict(IDLE_UNK)
IDLE_SRC_UNK[(B, "recorded idle, idle_src transcript")] = (
    "unknown; known subtotal 0 min", "unknown",
    "0 boundaries, 1 more without a usable idle_min; not independently verified head idleness")
NO_IDLE_ROW = ((B, "recorded idle, idle_src transcript"),)
HEAD_UNK = {(RF, "head fence (boundaries)"): ("unknown; known subtotal 0", "unknown", HF_COV % ("1 boundary", 1, GAPS0))}
SUM_UNK = {(RF, "boundary summary of helper tool refusals"): ("unknown; known subtotal 0", "unknown", HS_COV % ("1 boundary", GAPS0))}
BS_UNK = {(B, "cumulative rewrites snapshots"): ("unknown; known subtotal 0", "unknown", BS_COV % 1)}
SS_UNK1 = {SP_SS: ("unknown; known subtotal 1", "unknown", SS_COV % 1)}
SS_UNK2 = {SP_SS: ("unknown; known subtotal 2", "unknown", SS_COV % 1)}
HEAD_EXIT = {"ts": "2026-10-06T11:30:00+0100", "event": "head-exit", "band": 40, "spent_usd": 2.5}
HXW = "run-r.jsonl:5 · 2026-10-06 11:30:00 +0100"
# A beat names its own session (s-beat), so it is a session of one line beside the base close's (FIELDS.md, "Priced spend").
BEAT = {"ts": "2026-10-06T11:15:00+0100", "event": "hold-beat", "lane": "L", "session_id": "s-beat", "cost_src": "result",
        "total_cost_usd": 0.2, "usage": fixture_beat_usage()}
BTW = "run-r.jsonl:5 · 2026-10-06 11:15:00 +0100"
RUN_CLOSE = {"ts": "2026-10-06T11:45:00+0100", "event": "run-close", "run_spend_usd": 3.0, "run_spend_src": "x"}
RCW = "run-r.jsonl:5 · 2026-10-06 11:45:00 +0100"
PG = "Review activity and possible loops: positional groups"


def mk(**kw):
    return kw


# An undated close of helper Z in run-r (finding 4 of CR-WASTE1, finding 3 of CR-WASTE2): the episode
# parts of the run read unknown with their known subtotals and one named gap; the review counts are
# added only when the close could be of a reviewing class (REVIEW_REACHED).
UNDATED_CLOSE = {
    (H, "total"): ("unknown; known subtotal 90.5 s (1.5 min)", "unknown", "1 close: 1 timed, 0 not applicable, 0 unknown or invalid; " + G1),
    (H, "run run-r"): ("unknown; known subtotal 90.5 s (1.5 min)", "unknown", "1 close: 0 not applicable, 0 unknown or invalid; " + G1),
    (F, "closes"): ("unknown; known subtotal 1", "unknown", G1),
    (F, "completed"): ("unknown; known subtotal 1", "unknown", "exit_class completed"),
    (F, "non-completed"): ("unknown; known subtotal 0", "unknown", NONCOMP % (0, 0, G1)),
    (F, "status unknown or invalid"): ("unknown; known subtotal 0", "unknown", "no usable exit_class"),
    (F, "non-completed, later resumed"): ("unknown; known subtotal 0", "unknown", LATER),
    (RF, "helper tool"): ("unknown; known subtotal 0", "unknown", "1 close: 1 known, 0 not applicable, 0 unknown or invalid; " + G1),
    (RF, "helper fence"): ("unknown; known subtotal 0", "unknown", "1 close: 1 known, 0 not applicable, 0 unknown or invalid; " + G1),
    (RF, "helper sandbox"): ("unknown; known subtotal 0", "unknown", "1 close: 1 known, 0 not applicable, 0 unknown or invalid; " + G1),
    SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 0, 0, G1)),
    SP_PC: ("unknown; known subtotal 1", "unknown", PLAN_COV % (1, 0, 0, 0, 0, 0)),
    SP_TCI: tok(10, 1, 0, tc(1), gaps=1), SP_TCO: tok(2, 1, 0, tc(1), gaps=1),
    SP_TII: tok(0, 0, 0, ti(0), gaps=1), SP_TIO: tok(0, 0, 0, ti(0), gaps=1),
    SP_UN: ("unknown; known subtotal 0", "unknown", "token totals only; no dollar figure"),
    SP_NA: ("unknown; known subtotal 0", "unknown", "exit_class spawn-failed"),
}
REVIEW_REACHED = {
    (H, "class critic"): ("unknown; known subtotal 90.5 s (1.5 min)", "unknown", "1 close: 0 not applicable, 0 unknown or invalid; " + G1),
    (RV, "reviewing-class episodes"): ("unknown; known subtotal 1", "unknown", RVC_COV % ("0 closes", G1)),
    (RV, "positional candidate groups"): ("unknown; known subtotal 1", "unknown", GROUPS_COV % G1),
    (RV, "reviewing-class episodes with no positional group"): ("unknown; known subtotal 0", "unknown", NOGROUP_COV),
    (RV, "candidate groups with two or more reviewing-class episodes"): ("unknown; known subtotal 0", "unknown", MULTI_COV),
}


# (name, base_events keywords, row changes, rows dropped, the named gaps the detail lists (in its
# order), detail needles (the first states the case's own defect, so a reader with that defect
# fails there), the finding the case was added for, other records).
T2_CASES = [
    # duration_s: zero, positive (the base), absent, null, wrong type, negative, boolean, n/a.
    ("duration-zero", mk(close_changes={"duration_s": 0}),
     dict([((H, "total"), ("0 s (0.0 min)", "complete", ONE))] + list(views(("0 s (0.0 min)", "complete", VIEW)).items())),
     (), [], ["+0100 | 0 (measured zero) | completed |"], None),
    ("duration-positive", {}, {}, (), [], [BASE_ROW], None),
    ("duration-absent", mk(close_drop=("duration_s",)), unk_duration(), (),
     [gl(CW, "duration_s is not on the close", "Helper time")],
     ["| unknown (duration_s is not on the close) |"], None),
    ("duration-unknown-labelled-in-both-files", mk(close_changes={"duration_s": None}), unk_duration(), (),
     [gl(CW, "duration_s is recorded as null", "Helper time")],
     ["- run-r: unknown; known subtotal 0 s (0.0 min) over 1 close (0 not applicable, 1 unknown or invalid; 0 named gaps (detail))",
      "- critic: unknown; known subtotal 0 s (0.0 min) over 1 close (0 not applicable, 1 unknown or invalid; 0 named gaps (detail))",
      '- run-r/"L": unknown; known subtotal 0 s (0.0 min) over 1 close (0 not applicable, 1 unknown or invalid; 0 named gaps (detail))',
      "- (all): unknown; known subtotal 0 s (0.0 min) over 1 close (1 unknown or invalid; 0 named gaps (detail))",
      "| unknown (duration_s is recorded as null) |"], 3),
    ("duration-wrong-type", mk(close_changes={"duration_s": "90.5"}), unk_duration(), (),
     [gl(CW, "duration_s is a string", "Helper time")], ["| invalid (duration_s is a string) |"], None),
    ("duration-negative", mk(close_changes={"duration_s": -1}), unk_duration(), (),
     [gl(CW, "duration_s is negative", "Helper time")], ["| invalid (duration_s is negative) |"], None),
    ("duration-boolean", mk(close_changes={"duration_s": True}), unk_duration(), (),
     [gl(CW, "duration_s is a boolean", "Helper time")], ["| invalid (duration_s is a boolean) |"], None),
    # Documented non-applicability: the GPT-6 Astra wrapper's spawn failure (codex-lane.py:915-919):
    # no process, so no duration and no refusals; still a plan-usage close with no usage.
    ("spawn-failed-not-applicable",
     mk(close_changes={"exit_class": "spawn-failed", "exit_code": 3},
        close_drop=("duration_s", "denials", "sandbox_denials", "usage", "usage_state", "usage_complete")),
     dict([((H, "total"), ("0 s (0.0 min)", "complete", "1 close: 0 timed, 1 not applicable, 0 unknown or invalid; " + GAPS0))]
          + list(views(("0 s (0.0 min)", "complete", "1 close: 1 not applicable, 0 unknown or invalid; " + GAPS0)).items())
          + [((F, "completed"), ("0", "complete", "exit_class completed")),
             ((F, "non-completed"), ("1", "complete", NONCOMP % (0, 0, GAPS0))),
             ((F, "status spawn-failed"), ("1", "complete", "recorded exit_class")),
             ((RF, "helper tool"), ("0", "complete", "1 close: 0 known, 1 not applicable, 0 unknown or invalid; " + GAPS0)),
             ((RF, "helper fence"), ("0", "complete", "1 close: 0 known, 1 not applicable, 0 unknown or invalid; " + GAPS0)),
             ((RF, "helper sandbox"), ("0", "complete", "1 close: 0 known, 1 not applicable, 0 unknown or invalid; " + GAPS0)),
             (SP_PC, ("1", "complete", PLAN_COV % (0, 0, 0, 1, 0, 0))),
             (SP_TCI, tok(0, 0, 0, tc(0))), (SP_TCO, tok(0, 0, 0, tc(0)))]), (), [],
     ["| not applicable (no process started (exit_class spawn-failed)) |",
      "| plan usage, missing (no usage reported) |"], None),
    # exit_class: a non-completed value, absent, null, wrong type, blank, outside the vocabulary.
    ("exit-limit", mk(close_changes={"exit_class": "limit"}),
     {(F, "completed"): ("0", "complete", "exit_class completed"),
      (F, "non-completed"): ("1", "complete", NONCOMP % (0, 0, GAPS0)),
      (F, "status limit"): ("1", "complete", "recorded exit_class")}, (), [], ["| limit |"], None),
    ("exit-absent", mk(close_drop=("exit_class",)), unk_exit(), (),
     [gl(CW, "exit_class is not on the close", "Failed closes")], ["| unknown (exit_class is not on the close) |"], None),
    ("exit-null", mk(close_changes={"exit_class": None}), unk_exit(), (),
     [gl(CW, "exit_class is recorded as null", "Failed closes")], ["| unknown (exit_class is recorded as null) |"], None),
    ("exit-wrong-type", mk(close_changes={"exit_class": 0}), unk_exit(), (),
     [gl(CW, "exit_class is a number", "Failed closes")], ["| invalid (exit_class is a number) |"], None),
    ("exit-blank", mk(close_changes={"exit_class": " "}), unk_exit(), (),
     [gl(CW, "exit_class is blank", "Failed closes")], ["| invalid (exit_class is blank) |"], 3),
    ("exit-outside", mk(close_changes={"exit_class": "complete"}),
     dict(list(unk_exit(outside=1, unk=0).items())
          + [((F, "status outside the writers' vocabulary: complete"), ("1", "complete", "shown as recorded; neither completed nor non-completed"))]),
     (), [gl(CW, "exit_class 'complete' is outside the writers' vocabulary", "Failed closes")],
     ["| outside (exit_class 'complete' is outside the writers' vocabulary) |"], None),
    # Refusal channels: tool, fence and sandbox each with zero (the base), positive, absent, null,
    # wrong type and negative; the watch close's "unknown" with and without its transcript fence
    # count; the denials object absent, null, of the wrong kind and as the historical prose.
    ("tool-positive", mk(close_changes={"denials": {"tool": 2, "fence": 0, "sandbox": 0}}),
     {(RF, "helper tool"): ("2", "complete", CH)}, (), [], ["| completed | 2 | 0 (measured zero) |"], None),
    ("tool-absent", mk(close_changes={"denials": {"fence": 0, "sandbox": 0}}), unk_channel("tool"), (),
     [gl(CW, "denials.tool is not on the record", "Refusals: helper tool")], ["| unknown (denials.tool is not on the record) |"], None),
    ("tool-null", mk(close_changes={"denials": {"tool": None, "fence": 0, "sandbox": 0}}), unk_channel("tool"), (),
     [gl(CW, "denials.tool is recorded as null", "Refusals: helper tool")], ["| unknown (denials.tool is recorded as null) |"], None),
    ("tool-wrong-type", mk(close_changes={"denials": {"tool": "2", "fence": 0, "sandbox": 0}}), unk_channel("tool"), (),
     [gl(CW, "denials.tool is a string", "Refusals: helper tool")], ["| invalid (denials.tool is a string) |"], None),
    ("tool-negative", mk(close_changes={"denials": {"tool": -1, "fence": 0, "sandbox": 0}}), unk_channel("tool"), (),
     [gl(CW, "denials.tool is negative", "Refusals: helper tool")], ["| invalid (denials.tool is negative) |"], 3),
    ("fence-positive", mk(close_changes={"denials": {"tool": 0, "fence": 3, "sandbox": 0}}),
     {(RF, "helper fence"): ("3", "complete", CH)}, (), [], ["| 0 (measured zero) | 3 | 0 (measured zero) |"], None),
    ("fence-absent", mk(close_changes={"denials": {"tool": 0, "sandbox": 0}}), unk_channel("fence"), (),
     [gl(CW, "denials.fence is not on the record", "Refusals: helper fence")], ["| unknown (denials.fence is not on the record) |"], 3),
    ("fence-null", mk(close_changes={"denials": {"tool": 0, "fence": None, "sandbox": 0}}), unk_channel("fence"), (),
     [gl(CW, "denials.fence is recorded as null", "Refusals: helper fence")], ["| unknown (denials.fence is recorded as null) |"], 3),
    ("fence-wrong-type", mk(close_changes={"denials": {"tool": 0, "fence": True, "sandbox": 0}}), unk_channel("fence"), (),
     [gl(CW, "denials.fence is a boolean", "Refusals: helper fence")], ["| invalid (denials.fence is a boolean) |"], 3),
    ("fence-negative", mk(close_changes={"denials": {"tool": 0, "fence": -3, "sandbox": 0}}), unk_channel("fence"), (),
     [gl(CW, "denials.fence is negative", "Refusals: helper fence")], ["| invalid (denials.fence is negative) |"], 3),
    ("watch-close-unknown", mk(close_changes={"denials": "unknown", "fence_denials_transcript": 4}),
     dict(list(unk_channel("tool").items()) + [((RF, "helper fence"), ("4", "complete", CH))]), (),
     [gl(CW, "denials are recorded as \"unknown\"", "Refusals: helper tool")],
     ["| unknown (denials are recorded as \"unknown\") | 4 | 0 (measured zero) |"], None),
    ("fence-transcript-absent", mk(close_changes={"denials": "unknown"}), unk_channel("tool", "fence"), (),
     [gl(CW, "denials are recorded as \"unknown\"", "Refusals: helper fence"),
      gl(CW, "denials are recorded as \"unknown\"", "Refusals: helper tool")],
     ["| unknown (denials are recorded as \"unknown\") | unknown (denials are recorded as \"unknown\") |"], 3),
    ("fence-transcript-null", mk(close_changes={"denials": "unknown", "fence_denials_transcript": None}),
     unk_channel("tool", "fence"), (),
     [gl(CW, "denials are recorded as \"unknown\"", "Refusals: helper tool"),
      gl(CW, "fence_denials_transcript is recorded as null", "Refusals: helper fence")],
     ["| unknown (fence_denials_transcript is recorded as null) |"], 3),
    ("fence-transcript-wrong-type", mk(close_changes={"denials": "unknown", "fence_denials_transcript": "4"}),
     unk_channel("tool", "fence"), (),
     [gl(CW, "denials are recorded as \"unknown\"", "Refusals: helper tool"),
      gl(CW, "fence_denials_transcript is a string", "Refusals: helper fence")],
     ["| invalid (fence_denials_transcript is a string) |"], 3),
    ("denials-absent", mk(close_drop=("denials",)), unk_channel("tool", "fence"), (),
     [gl(CW, "denials are not on the close", "Refusals: helper fence"),
      gl(CW, "denials are not on the close", "Refusals: helper tool")],
     ["| unknown (denials are not on the close) | unknown (denials are not on the close) | 0 (measured zero) |"], 3),
    ("denials-null", mk(close_changes={"denials": None}), unk_channel("tool", "fence"), (),
     [gl(CW, "denials are recorded as null", "Refusals: helper fence"),
      gl(CW, "denials are recorded as null", "Refusals: helper tool")],
     ["| unknown (denials are recorded as null) | unknown (denials are recorded as null) | 0 (measured zero) |"], 3),
    ("denials-wrong-type", mk(close_changes={"denials": [1]}), unk_channel("tool", "fence"), (),
     [gl(CW, "denials is a list", "Refusals: helper fence"), gl(CW, "denials is a list", "Refusals: helper tool")],
     ["| invalid (denials is a list) | invalid (denials is a list) | 0 (measured zero) |"], 3),
    ("denials-none-reported", mk(close_changes={"denials": "none reported"}), unk_channel("tool", "fence"), (),
     [gl(CW, "denials is a string ('none reported')", "Refusals: helper fence"),
      gl(CW, "denials is a string ('none reported')", "Refusals: helper tool")],
     ["| invalid (denials is a string ('none reported')) |"], 3),
    ("sandbox-positive", mk(close_changes={"denials": {"tool": 0, "fence": 0, "sandbox": 2}, "sandbox_denials": 2}),
     {(RF, "helper sandbox"): ("2", "complete", CH)}, (), [], ["| 0 (measured zero) | 2 | plan usage"], None),
    ("sandbox-absent-claude-shape", mk(close_changes={"denials": {"tool": 0, "fence": 0, "fence_allows": 0}},
                                       close_drop=("sandbox_denials",)), unk_channel("sandbox"), (),
     [gl(CW, "no sandbox channel on the close", "Refusals: helper sandbox")], ["| unknown (no sandbox channel on the close) |"], None),
    ("sandbox-null", mk(close_changes={"denials": {"tool": 0, "fence": 0}, "sandbox_denials": None}), unk_channel("sandbox"), (),
     [gl(CW, "sandbox_denials is recorded as null", "Refusals: helper sandbox")], ["| unknown (sandbox_denials is recorded as null) |"], None),
    ("sandbox-wrong-type", mk(close_changes={"denials": {"tool": 0, "fence": 0, "sandbox": "2"}, "sandbox_denials": 2}),
     unk_channel("sandbox"), (), [gl(CW, "denials.sandbox is a string", "Refusals: helper sandbox")],
     ["| invalid (denials.sandbox is a string) |"], None),
    ("sandbox-disagree", mk(close_changes={"denials": {"tool": 0, "fence": 0, "sandbox": 2}, "sandbox_denials": 3}),
     unk_channel("sandbox"), (), [gl(CW, "denials.sandbox 2 and sandbox_denials 3 disagree", "Refusals: helper sandbox")],
     ["| invalid (denials.sandbox 2 and sandbox_denials 3 disagree) |"], None),
    ("sandbox-negative", mk(close_changes={"denials": {"tool": 0, "fence": 0}, "sandbox_denials": -1}), unk_channel("sandbox"), (),
     [gl(CW, "sandbox_denials is negative", "Refusals: helper sandbox")], ["| invalid (sandbox_denials is negative) |"], 3),
    ("sandbox-denials-field-only", mk(close_changes={"denials": {"tool": 0, "fence": 0}, "sandbox_denials": 2}),
     {(RF, "helper sandbox"): ("2", "complete", CH)}, (), [], ["| 0 (measured zero) | 2 | plan usage"], 3),
    # Spend: every basis and every value of the price beside it.
    ("priced", mk(close_changes={"cost_src": "result", "total_cost_usd": 1.5}), basis("priced", "$1.50"), (), [],
     ["| priced $1.50 |"], None),
    ("priced-zero", mk(close_changes={"cost_src": "result", "total_cost_usd": 0}), basis("priced", "$0.00"), (), [],
     ["| priced $0.00 |"], None),
    ("price-null", mk(close_changes={"cost_src": "result", "total_cost_usd": None}), basis("missing"), (),
     [gl(CW, "total_cost_usd is null on a result-priced close", "Priced spend: closes")],
     ["| missing (total_cost_usd is null on a result-priced close) |"], None),
    ("price-absent", mk(close_changes={"cost_src": "result"}, close_drop=("total_cost_usd",)), basis("missing"), (),
     [gl(CW, "total_cost_usd is absent on a result-priced close", "Priced spend: closes")],
     ["| missing (total_cost_usd is absent on a result-priced close) |"], None),
    ("price-wrong-type", mk(close_changes={"cost_src": "result", "total_cost_usd": "1.5"}), basis("invalid-price"), (),
     [gl(CW, "total_cost_usd is a string", "Priced spend: closes")], ["| invalid-price (total_cost_usd is a string) |"], None),
    ("price-negative", mk(close_changes={"cost_src": "result", "total_cost_usd": -1}), basis("invalid-price"), (),
     [gl(CW, "total_cost_usd is negative", "Priced spend: closes")], ["| invalid-price (total_cost_usd is negative) |"], 3),
    ("unpriced-transcript-estimate", mk(close_changes={"cost_src": "transcript-estimate", "total_cost_usd": None}),
     basis("unpriced"), (), [], ["| unpriced (a transcript estimate carries no dollar figure) |"], None),
    ("transcript-estimate-priced", mk(close_changes={"cost_src": "transcript-estimate", "total_cost_usd": 0.4}),
     basis("invalid-basis"), (), [gl(CW, "total_cost_usd is a price on a transcript-estimate close", "Priced spend: closes")],
     ["| invalid-basis (total_cost_usd is a price on a transcript-estimate close) |"], 3),
    ("undeclared-basis", mk(close_changes={"total_cost_usd": 0.7}, close_drop=("cost_src",)), basis("undeclared"), (),
     [gl(CW, "a price with no cost_src: its basis is undeclared", "Priced spend: closes")], ["| undeclared $0.70 |"], None),
    ("no-basis-no-price", mk(close_drop=("cost_src", "total_cost_usd")), basis("unknown-basis"), (),
     [gl(CW, "no cost_src and no price on the close", "Priced spend: closes")],
     ["| unknown-basis (no cost_src and no price on the close) |"], None),
    ("cost-src-null", mk(close_changes={"cost_src": None, "total_cost_usd": None}), basis("unknown-basis"), (),
     [gl(CW, "cost_src recorded as null and no price on the close", "Priced spend: closes")],
     ["| unknown-basis (cost_src recorded as null and no price on the close) |"], 3),
    ("cost-src-outside", mk(close_changes={"cost_src": "estimate"}), basis("invalid-basis"), (),
     [gl(CW, "cost_src 'estimate' is not a known basis", "Priced spend: closes")],
     ["| invalid-basis (cost_src 'estimate' is not a known basis) |"], 3),
    ("cost-src-wrong-type", mk(close_changes={"cost_src": 5}), basis("invalid-basis"), (),
     [gl(CW, "cost_src is a number, not a known basis", "Priced spend: closes")],
     ["| invalid-basis (cost_src is a number, not a known basis) |"], 3),
    ("plan-price-number", mk(close_changes={"total_cost_usd": 1.5}), basis("invalid-basis"), (),
     [gl(CW, "total_cost_usd is a price on a plan-usage close", "Priced spend: closes")],
     ["| invalid-basis (total_cost_usd is a price on a plan-usage close) |"], 3),
    ("plan-price-wrong-type", mk(close_changes={"total_cost_usd": "bad"}), basis("invalid-basis"), (),
     [gl(CW, "total_cost_usd is a string on a plan-usage close", "Priced spend: closes")],
     ["| invalid-basis (total_cost_usd is a string on a plan-usage close) |"], 3),
    # Plan usage: every usage_state the writer writes, the writer's own reading of a close written
    # before usage_state (codex-lane.py:723-735) with each of its inputs, and every invalid present
    # value kept invalid: an outside state, a wrong kind, null, a wrong usage object.
    ("plan-zero", mk(close_changes={"usage_state": "zero", "usage": {"input_tokens": 0, "output_tokens": 0, "calls": 1}}),
     plan_rows("zero", 0, 0), (), [], ["| plan usage, zero; input 0 (measured zero), output 0 (measured zero) |"], None),
    ("plan-zero-nonzero-tokens", mk(close_changes={"usage_state": "zero"}), plan("invalid"), (),
     [gl(CW, "usage_state zero with non-zero tokens", "Priced spend: plan usage")],
     ["| plan usage, invalid (usage_state zero with non-zero tokens); input 10, output 2 |"], 3),
    ("plan-incomplete", mk(close_changes={"usage_state": "incomplete", "usage_complete": False}),
     plan_rows("incomplete", 10, 2), (), [], ["| plan usage, incomplete; input 10, output 2 |"], None),
    ("plan-missing", mk(close_changes={"usage_state": "missing", "usage_complete": False, "usage": {"input_tokens": 0, "output_tokens": 0, "calls": 0}}),
     {SP_PC: ("1", "complete", PLAN_COV % (0, 0, 0, 1, 0, 0)), SP_TCI: tok(0, 0, 0, tc(0)), SP_TCO: tok(0, 0, 0, tc(0))}, (), [],
     ["| plan usage, missing (no usage reported) |"], None),
    ("plan-historical-incomplete", mk(close_changes={"usage_complete": False}, close_drop=("usage_state",)),
     plan_rows("incomplete", 10, 2), (), [], ["| plan usage, incomplete; input 10, output 2 |"], None),
    ("plan-historical-no-calls", mk(close_changes={"usage_complete": False, "usage": {"input_tokens": 0, "output_tokens": 0, "calls": 0}},
                                    close_drop=("usage_state",)),
     {SP_PC: ("1", "complete", PLAN_COV % (0, 0, 0, 1, 0, 0)), SP_TCI: tok(0, 0, 0, tc(0)), SP_TCO: tok(0, 0, 0, tc(0))}, (), [],
     ["| plan usage, missing (no usage reported) |"], None),
    ("plan-historical-complete", mk(close_drop=("usage_state",)), {}, (), [], [BASE_ROW], 3),
    ("plan-historical-no-complete-field", mk(close_drop=("usage_state", "usage_complete")), {}, (), [], [BASE_ROW], 3),
    ("plan-historical-no-usage", mk(close_drop=("usage_state", "usage", "usage_complete")),
     {SP_PC: ("1", "complete", PLAN_COV % (0, 0, 0, 1, 0, 0)), SP_TCI: tok(0, 0, 0, tc(0)), SP_TCO: tok(0, 0, 0, tc(0))}, (), [],
     ["| plan usage, missing (no usage reported) |"], 3),
    ("plan-historical-calls-wrong-type", mk(close_changes={"usage_complete": False, "usage": {"input_tokens": 10, "output_tokens": 2, "calls": "1"}},
                                            close_drop=("usage_state",)), plan("invalid"), (),
     [gl(CW, "usage.calls is a string", "Priced spend: plan usage")],
     ["| plan usage, invalid (usage.calls is a string); input 10, output 2 |"], 3),
    ("plan-historical-complete-wrong-type", mk(close_changes={"usage_complete": "yes"}, close_drop=("usage_state",)),
     plan("invalid"), (), [gl(CW, "usage_complete is a string", "Priced spend: plan usage")],
     ["| plan usage, invalid (usage_complete is a string); input 10, output 2 |"], 3),
    ("plan-historical-complete-null", mk(close_changes={"usage_complete": None}, close_drop=("usage_state",)),
     plan("unknown"), (), [gl(CW, "usage_complete is recorded as null", "Priced spend: plan usage")],
     ["| plan usage, unknown (usage_complete is recorded as null); input 10, output 2 |"], 3),
    ("plan-state-outside-vocabulary", mk(close_changes={"usage_state": "done"}), plan("invalid"), (),
     [gl(CW, "usage_state 'done' is outside the writer's vocabulary", "Priced spend: plan usage")],
     ["| plan usage, invalid (usage_state 'done' is outside the writer's vocabulary); input 10, output 2 |"], 3),
    ("plan-state-wrong-type", mk(close_changes={"usage_state": 5}), plan("invalid"), (),
     [gl(CW, "usage_state is a number", "Priced spend: plan usage")],
     ["| plan usage, invalid (usage_state is a number); input 10, output 2 |"], 3),
    ("plan-state-null", mk(close_changes={"usage_state": None}), plan("unknown"), (),
     [gl(CW, "usage_state is recorded as null", "Priced spend: plan usage")],
     ["| plan usage, unknown (usage_state is recorded as null); input 10, output 2 |"], 3),
    # Finding 2 of CR-WASTE2: each token direction is read on its own, under each state. Absent or
    # null is unknown, another kind, a negative or a fraction invalid; the writer's state stays as
    # recorded whatever the tokens (an incomplete close stays incomplete), and the direction that
    # is known stays known with its coverage, in the main report and in the detail. The first
    # needle is the plan-closes row's state counts, whose label every version renders.
    ("plan-complete-input-absent", mk(close_changes={"usage": {"output_tokens": 2, "calls": 1}}),
     plan_rows("complete", None, 2), (), [gl(CW, "usage.input_tokens is not on the close", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input unknown (usage.input_tokens is not on the close), output 2 |"], "F2"),
    ("plan-complete-input-null", mk(close_changes={"usage": {"input_tokens": None, "output_tokens": 2, "calls": 1}}),
     plan_rows("complete", None, 2), (), [gl(CW, "usage.input_tokens is recorded as null", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input unknown (usage.input_tokens is recorded as null), output 2 |"], "F2"),
    ("plan-complete-input-wrong-type", mk(close_changes={"usage": {"input_tokens": "10", "output_tokens": 2, "calls": 1}}),
     plan_rows("complete", None, 2), (), [gl(CW, "usage.input_tokens is a string", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input invalid (usage.input_tokens is a string), output 2 |"], "F2"),
    ("plan-complete-input-negative", mk(close_changes={"usage": {"input_tokens": -1, "output_tokens": 2, "calls": 1}}),
     plan_rows("complete", None, 2), (), [gl(CW, "usage.input_tokens is negative", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input invalid (usage.input_tokens is negative), output 2 |"], "F2"),
    ("plan-complete-output-absent", mk(close_changes={"usage": {"input_tokens": 10, "calls": 1}}),
     plan_rows("complete", 10, None), (), [gl(CW, "usage.output_tokens is not on the close", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input 10, output unknown (usage.output_tokens is not on the close) |"], "F2"),
    ("plan-complete-output-null", mk(close_changes={"usage": {"input_tokens": 10, "output_tokens": None, "calls": 1}}),
     plan_rows("complete", 10, None), (), [gl(CW, "usage.output_tokens is recorded as null", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input 10, output unknown (usage.output_tokens is recorded as null) |"], "F2"),
    ("plan-complete-output-wrong-type", mk(close_changes={"usage": {"input_tokens": 10, "output_tokens": "2", "calls": 1}}),
     plan_rows("complete", 10, None), (), [gl(CW, "usage.output_tokens is a string", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input 10, output invalid (usage.output_tokens is a string) |"], "F2"),
    ("plan-complete-output-fraction", mk(close_changes={"usage": {"input_tokens": 10, "output_tokens": 2.5, "calls": 1}}),
     plan_rows("complete", 10, None), (), [gl(CW, "usage.output_tokens is a non-integer number", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input 10, output invalid (usage.output_tokens is a non-integer number) |"], "F2"),
    ("plan-complete-usage-absent", mk(close_changes={}, close_drop=("usage",)),
     plan_rows("complete", None, None), (), [gl(CW, "usage is not on the close", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input unknown (usage is not on the close), output unknown (usage is not on the close) |"], "F2"),
    ("plan-complete-usage-null", mk(close_changes={"usage": None}),
     plan_rows("complete", None, None), (), [gl(CW, "usage is recorded as null", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input unknown (usage is recorded as null), output unknown (usage is recorded as null) |"], "F2"),
    ("plan-complete-usage-wrong-type", mk(close_changes={"usage": "x"}),
     plan_rows("complete", None, None), (), [gl(CW, "usage is a string", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input invalid (usage is a string), output invalid (usage is a string) |"], "F2"),
    ("plan-incomplete-input-absent", mk(close_changes={"usage_state": "incomplete", "usage_complete": False, "usage": {"output_tokens": 2, "calls": 1}}),
     plan_rows("incomplete", None, 2), (), [gl(CW, "usage.input_tokens is not on the close", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 0, incomplete 1, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, incomplete; input unknown (usage.input_tokens is not on the close), output 2 |"], "F2"),
    ("plan-incomplete-input-null", mk(close_changes={"usage_state": "incomplete", "usage_complete": False, "usage": {"input_tokens": None, "output_tokens": 2, "calls": 1}}),
     plan_rows("incomplete", None, 2), (), [gl(CW, "usage.input_tokens is recorded as null", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 0, incomplete 1, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, incomplete; input unknown (usage.input_tokens is recorded as null), output 2 |"], "F2"),
    ("plan-incomplete-input-wrong-type", mk(close_changes={"usage_state": "incomplete", "usage_complete": False, "usage": {"input_tokens": "10", "output_tokens": 2, "calls": 1}}),
     plan_rows("incomplete", None, 2), (), [gl(CW, "usage.input_tokens is a string", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 0, incomplete 1, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, incomplete; input invalid (usage.input_tokens is a string), output 2 |"], "F2"),
    ("plan-incomplete-input-negative", mk(close_changes={"usage_state": "incomplete", "usage_complete": False, "usage": {"input_tokens": -1, "output_tokens": 2, "calls": 1}}),
     plan_rows("incomplete", None, 2), (), [gl(CW, "usage.input_tokens is negative", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 0, incomplete 1, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, incomplete; input invalid (usage.input_tokens is negative), output 2 |"], "F2"),
    ("plan-incomplete-output-absent", mk(close_changes={"usage_state": "incomplete", "usage_complete": False, "usage": {"input_tokens": 10, "calls": 1}}),
     plan_rows("incomplete", 10, None), (), [gl(CW, "usage.output_tokens is not on the close", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 0, incomplete 1, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, incomplete; input 10, output unknown (usage.output_tokens is not on the close) |"], "F2"),
    ("plan-incomplete-output-null", mk(close_changes={"usage_state": "incomplete", "usage_complete": False, "usage": {"input_tokens": 10, "output_tokens": None, "calls": 1}}),
     plan_rows("incomplete", 10, None), (), [gl(CW, "usage.output_tokens is recorded as null", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 0, incomplete 1, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, incomplete; input 10, output unknown (usage.output_tokens is recorded as null) |"], "F2"),
    ("plan-incomplete-output-wrong-type", mk(close_changes={"usage_state": "incomplete", "usage_complete": False, "usage": {"input_tokens": 10, "output_tokens": "2", "calls": 1}}),
     plan_rows("incomplete", 10, None), (), [gl(CW, "usage.output_tokens is a string", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 0, incomplete 1, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, incomplete; input 10, output invalid (usage.output_tokens is a string) |"], "F2"),
    ("plan-incomplete-output-fraction", mk(close_changes={"usage_state": "incomplete", "usage_complete": False, "usage": {"input_tokens": 10, "output_tokens": 2.5, "calls": 1}}),
     plan_rows("incomplete", 10, None), (), [gl(CW, "usage.output_tokens is a non-integer number", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 0, incomplete 1, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, incomplete; input 10, output invalid (usage.output_tokens is a non-integer number) |"], "F2"),
    ("plan-incomplete-usage-absent", mk(close_changes={"usage_state": "incomplete", "usage_complete": False}, close_drop=("usage",)),
     plan_rows("incomplete", None, None), (), [gl(CW, "usage is not on the close", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 0, incomplete 1, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, incomplete; input unknown (usage is not on the close), output unknown (usage is not on the close) |"], "F2"),
    ("plan-incomplete-usage-null", mk(close_changes={"usage_state": "incomplete", "usage_complete": False, "usage": None}),
     plan_rows("incomplete", None, None), (), [gl(CW, "usage is recorded as null", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 0, incomplete 1, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, incomplete; input unknown (usage is recorded as null), output unknown (usage is recorded as null) |"], "F2"),
    ("plan-incomplete-usage-wrong-type", mk(close_changes={"usage_state": "incomplete", "usage_complete": False, "usage": "x"}),
     plan_rows("incomplete", None, None), (), [gl(CW, "usage is a string", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 0, incomplete 1, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, incomplete; input invalid (usage is a string), output invalid (usage is a string) |"], "F2"),
    ("plan-zero-input-absent", mk(close_changes={"usage_state": "zero", "usage": {"output_tokens": 0, "calls": 1}}),
     plan_rows("zero", None, 0), (), [gl(CW, "usage.input_tokens is not on the close", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 1, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, zero; input unknown (usage.input_tokens is not on the close), output 0 (measured zero) |"], "F2"),
    ("plan-historical-incomplete-input-absent", mk(close_changes={"usage_complete": False, "usage": {"output_tokens": 2, "calls": 1}}, close_drop=("usage_state",)),
     plan_rows("incomplete", None, 2), (), [gl(CW, "usage.input_tokens is not on the close", "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 0, measured zero 0, incomplete 1, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, incomplete; input unknown (usage.input_tokens is not on the close), output 2 |"], "F2"),
    # Class: on the opening only (used), absent and null on both, of the wrong kind, blank,
    # conflicting. An unusable class makes the review counts known subtotals.
    ("class-on-opening-only", mk(close_drop=("class",)), {}, (), [], [BASE_ROW], None),
    ("class-absent", mk(close_drop=("class",), open_drop=("class",)), class_unknown("(class unrecorded)"), ((H, "class critic"),),
     [gl(CW, "no class on the close or the opening", "Review activity and possible loops: reviewing-class episodes")],
     ['| run-r:"L":2 | (class unrecorded) |'], None),
    ("class-null", mk(close_changes={"class": None}, open_changes={"class": None}), class_unknown("(class unrecorded)"),
     ((H, "class critic"),),
     [gl(CW, "no class on the close or the opening", "Review activity and possible loops: reviewing-class episodes")],
     ['| run-r:"L":2 | (class unrecorded) |'], 3),
    ("class-wrong-type", mk(close_changes={"class": 5}), class_unknown("(class invalid)"), ((H, "class critic"),),
     [gl(CW, "the close's class is a number", "Review activity and possible loops: reviewing-class episodes")],
     ['| run-r:"L":2 | (class invalid) |'], 3),
    ("class-blank", mk(close_drop=("class",), open_changes={"class": " "}), class_unknown("(class invalid)"), ((H, "class critic"),),
     [gl(CW, "the opening's class is blank", "Review activity and possible loops: reviewing-class episodes")],
     ['| run-r:"L":2 | (class invalid) |'], 3),
    ("class-conflicting", mk(close_changes={"class": "builder"}), class_unknown("(class conflicting)"), ((H, "class critic"),),
     [gl(CW, "the close's class 'builder' and the opening's 'critic' disagree", "Review activity and possible loops: reviewing-class episodes")],
     ['| run-r:"L":2 | (class conflicting) |'], None),
    # The gate before the opening: absent; present with its item absent, null, of the wrong kind
    # or blank; refused; with no decision, a null one or one outside the vocabulary; undated.
    ("gate-absent", mk(gate=False), dict(list(NO_GROUP.items()) + [(SP_SS, ("1", "complete", SS_COV % 0))]), (), [],
     ["| none: no gate before its opening on the record |", '| run-r:"L":1 | critic |'], None),
    ("gate-item-field-absent", mk(gate_drop=("item",)), NO_GROUP, (), [],
     ["| none: the last gate before its opening (line 1) has no usable item (absent) |"], 3),
    ("gate-item-null", mk(gate_changes={"item": None}), NO_GROUP, (), [],
     ["| none: the last gate before its opening (line 1) has no usable item (null) |"], 3),
    ("gate-item-wrong-type", mk(gate_changes={"item": 5}), NO_GROUP, (), [],
     ["| none: the last gate before its opening (line 1) has no usable item (a number) |"], 3),
    ("gate-item-blank", mk(gate_changes={"item": " "}), NO_GROUP, (), [],
     ["| none: the last gate before its opening (line 1) has no usable item (blank) |"], 3),
    ("gate-refused", mk(gate_changes={"decision": "refuse"}), NO_GROUP, (), [],
     ["| none: the last gate before its opening (line 1) refused item i1 |"], 5),
    ("gate-decision-absent", mk(gate_drop=("decision",)), NO_GROUP, (), [],
     ["| none: the last gate before its opening (line 1) records no decision |"], 5),
    ("gate-decision-null", mk(gate_changes={"decision": None}), NO_GROUP, (), [],
     ["| none: the last gate before its opening (line 1) records its decision as null |"], 5),
    ("gate-decision-outside", mk(gate_changes={"decision": "maybe"}), NO_GROUP, (), [],
     ["| none: the last gate before its opening (line 1) records the decision 'maybe', outside the writer's vocabulary |"], 5),
    # An undated gate is a named gap of the positional groups and the snapshots only: the count of
    # reviewing-class episodes stays known (finding 4's scoping).
    ("gate-undated", mk(gate_changes={"ts": "bad"}),
     {(RV, "positional candidate groups"): ("unknown; known subtotal 0", "unknown", GROUPS_COV % G1),
      (RV, "reviewing-class episodes with no positional group"): ("unknown; known subtotal 1", "unknown", NOGROUP_COV),
      (RV, "candidate groups with two or more reviewing-class episodes"): ("unknown; known subtotal 0", "unknown", MULTI_COV),
      SP_SS: ("unknown; known subtotal 1", "unknown", SS_COV % 0)}, (),
     [gl("run-r.jsonl:1 · time unknown", "no usable timestamp ('bad')", PG + "; Priced spend: snapshots")],
     ["| none: the last gate before its opening (line 1) is invalid: no usable timestamp ('bad') |"], 5),
    # Boundary fields: idle_min and idle_src, over_cap_reports, the rewrites delta, head_denials
    # and the boundary's own summary, each through its values.
    ("idle-zero", mk(boundary_changes={"idle_min": 0}),
     {(B, "recorded idle, idle_src transcript"): ("0 min", "complete", IDLE_COV % "1 boundary")}, (), [], ["· idle_min 0 (transcript) ·"], None),
    ("idle-absent", mk(boundary_drop=("idle_min",)), IDLE_SRC_UNK, (),
     [gl(BW, "idle_min is not on the boundary", "Phase boundaries")], ["ROW:Phase boundaries|recorded idle, idle_src transcript|unknown; known subtotal 0 min|unknown", "· idle_min None (transcript) ·"], "F3"),
    ("idle-null", mk(boundary_changes={"idle_min": None}), IDLE_SRC_UNK, (),
     [gl(BW, "idle_min is recorded as null", "Phase boundaries")], ["ROW:Phase boundaries|recorded idle, idle_src transcript|unknown; known subtotal 0 min|unknown", "· idle_min None (transcript) ·"], "F3"),
    ("idle-wrong-type", mk(boundary_changes={"idle_min": "2.5"}), IDLE_SRC_UNK, (),
     [gl(BW, "idle_min is a string", "Phase boundaries")], ["ROW:Phase boundaries|recorded idle, idle_src transcript|unknown; known subtotal 0 min|unknown", "· idle_min 2.5 (transcript) ·"], "F3"),
    ("idle-negative", mk(boundary_changes={"idle_min": -1}), IDLE_SRC_UNK, (),
     [gl(BW, "idle_min is negative", "Phase boundaries")], ["ROW:Phase boundaries|recorded idle, idle_src transcript|unknown; known subtotal 0 min|unknown", "· idle_min -1 (transcript) ·"], (3, "F3")),
    ("idle-source-absent", mk(boundary_drop=("idle_src",)),
     {(B, "recorded idle, idle_src (source unrecorded)"): ("2.5 min", "complete", IDLE_COV % "1 boundary")}, NO_IDLE_ROW, [],
     ["· idle_min 2.5 (None) ·"], None),
    ("idle-source-null", mk(boundary_changes={"idle_src": None}),
     {(B, "recorded idle, idle_src (source unrecorded)"): ("2.5 min", "complete", IDLE_COV % "1 boundary")}, NO_IDLE_ROW, [],
     ["· idle_min 2.5 (None) ·"], 3),
    ("idle-source-wrong-type", mk(boundary_changes={"idle_src": 5}), IDLE_UNK, NO_IDLE_ROW,
     [gl(BW, "idle_src is a number", "Phase boundaries")], ["· idle_min 2.5 (5) ·"], 3),
    # A blank recorded string is shown quoted in the boundary's line (CR-WASTE5 finding 1: a string
    # with white space at an end is shown by its repr), so it cannot read as nothing.
    ("idle-source-blank", mk(boundary_changes={"idle_src": " "}), IDLE_UNK, NO_IDLE_ROW,
     [gl(BW, "idle_src is blank", "Phase boundaries")], ["· idle_min 2.5 (' ') ·"], 3),
    ("over-cap-absent", mk(boundary_drop=("over_cap_reports",)),
     {(B, "over-cap reports"): ("unknown; known subtotal 0", "unknown", OVER_COV % "1 boundary")}, (),
     [gl(BW, "over_cap_reports is not on the record", "Phase boundaries")], ["· over_cap_reports None ·"], None),
    ("over-cap-positive", mk(boundary_changes={"over_cap_reports": 2}),
     {(B, "over-cap reports"): ("2", "complete", OVER_COV % "0 boundaries")}, (), [], ["· over_cap_reports 2 ·"], None),
    ("over-cap-null", mk(boundary_changes={"over_cap_reports": None}),
     {(B, "over-cap reports"): ("unknown; known subtotal 0", "unknown", OVER_COV % "1 boundary")}, (),
     [gl(BW, "over_cap_reports is recorded as null", "Phase boundaries")], ["· over_cap_reports None ·"], 3),
    ("over-cap-wrong-type", mk(boundary_changes={"over_cap_reports": "1"}),
     {(B, "over-cap reports"): ("unknown; known subtotal 0", "unknown", OVER_COV % "1 boundary")}, (),
     [gl(BW, "over_cap_reports is a string", "Phase boundaries")], ["· over_cap_reports 1 ·"], 3),
    ("over-cap-negative", mk(boundary_changes={"over_cap_reports": -1}),
     {(B, "over-cap reports"): ("unknown; known subtotal 0", "unknown", OVER_COV % "1 boundary")}, (),
     [gl(BW, "over_cap_reports is negative", "Phase boundaries")], ["· over_cap_reports -1 ·"], 3),
    ("rewrites-null", mk(boundary_changes={"rewrites": None}),
     {(B, "rewrites (deltas)"): ("unknown; known subtotal 0", "unknown", REW_COV % "1 boundary")}, (),
     [gl(BW, "rewrites is recorded as null", "Phase boundaries")], ["· rewrites None (cumulative 1) ·"], None),
    ("rewrites-absent", mk(boundary_drop=("rewrites",)),
     {(B, "rewrites (deltas)"): ("unknown; known subtotal 0", "unknown", REW_COV % "1 boundary")}, (),
     [gl(BW, "rewrites is not on the boundary", "Phase boundaries")], ["· rewrites None (cumulative 1) ·"], 3),
    ("rewrites-wrong-type", mk(boundary_changes={"rewrites": 1.5}),
     {(B, "rewrites (deltas)"): ("unknown; known subtotal 0", "unknown", REW_COV % "1 boundary")}, (),
     [gl(BW, "rewrites is a non-integer number", "Phase boundaries")], ["· rewrites 1.5 (cumulative 1) ·"], 3),
    ("rewrites-zero", mk(boundary_changes={"rewrites": 0}),
     {(B, "rewrites (deltas)"): ("0", "complete", REW_COV % "0 boundaries")}, (), [], ["· rewrites 0 (cumulative 1) ·"], 3),
    # A delta is kept as recorded, a decrease included (handsoff.py:3411 subtracts the same head's
    # previous cumulative figure).
    ("rewrites-negative", mk(boundary_changes={"rewrites": -2}),
     {(B, "rewrites (deltas)"): ("-2", "complete", REW_COV % "0 boundaries")}, (), [], ["· rewrites -2 (cumulative 1) ·"], 3),
    # Snapshots: rewrites_total and run_spend_usd on the boundary, run_spend_usd on the gate and the
    # run-close, a plain run's spend_usd, and head-exit's spent_usd, each through its values. An
    # absent, null or invalid snapshot is named and leaves its snapshot row a known subtotal.
    ("rewrites-total-null", mk(boundary_changes={"rewrites_total": None}), BS_UNK, (),
     [gl(BW, "rewrites_total is recorded as null", "Phase boundaries: rewrites snapshots")],
     ["· phase-boundary · unknown (rewrites_total is recorded as null)"], 3),
    ("rewrites-total-absent", mk(boundary_drop=("rewrites_total",)), BS_UNK, (),
     [gl(BW, "rewrites_total is not on the event", "Phase boundaries: rewrites snapshots")],
     ["· phase-boundary · unknown (rewrites_total is not on the event)"], 3),
    ("rewrites-total-wrong-type", mk(boundary_changes={"rewrites_total": "1"}), BS_UNK, (),
     [gl(BW, "rewrites_total is a string", "Phase boundaries: rewrites snapshots")],
     ["· phase-boundary · invalid (rewrites_total is a string)"], 3),
    ("rewrites-total-negative", mk(boundary_changes={"rewrites_total": -1}), BS_UNK, (),
     [gl(BW, "rewrites_total is negative", "Phase boundaries: rewrites snapshots")],
     ["· phase-boundary · invalid (rewrites_total is negative)"], 3),
    ("rewrites-total-zero", mk(boundary_changes={"rewrites_total": 0}), {}, (), [],
     ["- run-r.jsonl:4 · 2026-10-06 11:00:00 +0100 · phase-boundary · rewrites_total 0"], 3),
    ("boundary-run-spend-null", mk(boundary_changes={"run_spend_usd": None}), SS_UNK1, (),
     [gl(BW, "run_spend_usd is recorded as null", "Priced spend: snapshots")],
     ["· phase-boundary · unknown (run_spend_usd is recorded as null)"], 3),
    ("boundary-run-spend-absent", mk(boundary_drop=("run_spend_usd",)), SS_UNK1, (),
     [gl(BW, "run_spend_usd is not on the event", "Priced spend: snapshots")],
     ["· phase-boundary · unknown (run_spend_usd is not on the event)"], 3),
    ("boundary-run-spend-wrong-type", mk(boundary_changes={"run_spend_usd": "1"}), SS_UNK1, (),
     [gl(BW, "run_spend_usd is a string", "Priced spend: snapshots")],
     ["· phase-boundary · invalid (run_spend_usd is a string)"], 3),
    ("boundary-run-spend-negative", mk(boundary_changes={"run_spend_usd": -1}), SS_UNK1, (),
     [gl(BW, "run_spend_usd is negative", "Priced spend: snapshots")],
     ["· phase-boundary · invalid (run_spend_usd is negative)"], 3),
    ("boundary-run-spend-zero", mk(boundary_changes={"run_spend_usd": 0}), {}, (), [],
     ["- run-r.jsonl:4 · 2026-10-06 11:00:00 +0100 · phase-boundary · run_spend_usd 0"], 3),
    ("gate-run-spend-null", mk(gate_changes={"run_spend_usd": None}), SS_UNK1, (),
     [gl(GW, "run_spend_usd is recorded as null", "Priced spend: snapshots")],
     ["- run-r.jsonl:1 · 2026-10-06 09:59:00 +0100 · gate · unknown (run_spend_usd is recorded as null)"], 3),
    ("head-exit-spent-number", mk(extra=[HEAD_EXIT]), {SP_SS: ("3", "complete", SS_COV % 0)}, (), [],
     ["- run-r.jsonl:5 · 2026-10-06 11:30:00 +0100 · head-exit · spent_usd 2.5"], 3),
    ("head-exit-spent-null", mk(extra=[dict(HEAD_EXIT, spent_usd=None)]), SS_UNK2, (),
     [gl(HXW, "spent_usd is recorded as null", "Priced spend: snapshots")],
     ["- run-r.jsonl:5 · 2026-10-06 11:30:00 +0100 · head-exit · unknown (spent_usd is recorded as null)"], 3),
    ("head-exit-spent-absent", mk(extra=[dict((k, v) for k, v in HEAD_EXIT.items() if k != "spent_usd")]), SS_UNK2, (),
     [gl(HXW, "spent_usd is not on the event", "Priced spend: snapshots")],
     ["- run-r.jsonl:5 · 2026-10-06 11:30:00 +0100 · head-exit · unknown (spent_usd is not on the event)"], 3),
    ("head-exit-spent-wrong-type", mk(extra=[dict(HEAD_EXIT, spent_usd="2.5")]), SS_UNK2, (),
     [gl(HXW, "spent_usd is a string", "Priced spend: snapshots")],
     ["- run-r.jsonl:5 · 2026-10-06 11:30:00 +0100 · head-exit · invalid (spent_usd is a string)"], 3),
    ("head-exit-spent-negative", mk(extra=[dict(HEAD_EXIT, spent_usd=-1)]), SS_UNK2, (),
     [gl(HXW, "spent_usd is negative", "Priced spend: snapshots")],
     ["- run-r.jsonl:5 · 2026-10-06 11:30:00 +0100 · head-exit · invalid (spent_usd is negative)"], 3),
    ("run-close-spend-null", mk(extra=[dict(RUN_CLOSE, run_spend_usd=None)]), SS_UNK2, (),
     [gl(RCW, "run_spend_usd is recorded as null", "Priced spend: snapshots")],
     ["- run-r.jsonl:5 · 2026-10-06 11:45:00 +0100 · run-close · unknown (run_spend_usd is recorded as null)"], 3),
    ("plain-run-close-spend", mk(extra=[{"ts": "2026-10-06T11:45:00+0100", "event": "run-close", "shape": "plain-lane-run",
                                         "spend_usd": 3.0, "spend_src": "sum of 1 lane-closed total_cost_usd"}]),
     {SP_SS: ("3", "complete", SS_COV % 0)}, (), [],
     ["- run-r.jsonl:5 · 2026-10-06 11:45:00 +0100 · run-close · spend_usd 3.0"], 3),
    ("head-fence-positive", mk(boundary_changes={"head_denials": 2}),
     {(RF, "head fence (boundaries)"): ("2", "complete", HF_COV % ("1 boundary", 0, GAPS0))}, (), [], ["· head_denials 2 (None) ·"], None),
    ("head-fence-null", mk(boundary_changes={"head_denials": None}), HEAD_UNK, (),
     [gl(BW, "head_denials is recorded as null", "Refusals: head fence")], ["· head_denials None (None) ·"], None),
    ("head-fence-absent", mk(boundary_drop=("head_denials",)), HEAD_UNK, (),
     [gl(BW, "head_denials is not on the record", "Refusals: head fence")], ["· head_denials None (None) ·"], 3),
    ("head-fence-wrong-type", mk(boundary_changes={"head_denials": "2"}), HEAD_UNK, (),
     [gl(BW, "head_denials is a string", "Refusals: head fence")], ["· head_denials 2 (None) ·"], 3),
    ("head-fence-negative", mk(boundary_changes={"head_denials": -2}), HEAD_UNK, (),
     [gl(BW, "head_denials is negative", "Refusals: head fence")], ["· head_denials -2 (None) ·"], 3),
    ("head-fence-source-shown", mk(boundary_changes={"head_denials": None, "head_denials_src": "unmeasured: no events.log"}), HEAD_UNK, (),
     [gl(BW, "head_denials is recorded as null", "Refusals: head fence")], ["· head_denials None (unmeasured: no events.log) ·"], 3),
    ("summary-absent", mk(boundary_drop=("denials",)), SUM_UNK, (),
     [gl(BW, "denials (the boundary's helper summary) is not on the record", "Refusals: boundary summary")], ["· denials None ·"], None),
    ("summary-null", mk(boundary_changes={"denials": None}), SUM_UNK, (),
     [gl(BW, "denials (the boundary's helper summary) is recorded as null", "Refusals: boundary summary")], ["· denials None ·"], 3),
    ("summary-wrong-type", mk(boundary_changes={"denials": "1"}), SUM_UNK, (),
     [gl(BW, "denials (the boundary's helper summary) is a string", "Refusals: boundary summary")], ["· denials 1 ·"], 3),
    ("summary-positive", mk(boundary_changes={"denials": 3}),
     {(RF, "boundary summary of helper tool refusals"): ("3", "complete", HS_COV % ("0 boundaries", GAPS0))}, (), [],
     ["· denials 3 ·"], 3),
    # Hold beats: priced, plan usage, a missing price and a price of the wrong kind. A beat whose
    # recorded basis is known (result) but whose amount is missing or invalid leaves the priced
    # total unknown and the count of beats not priced complete (finding 3 of CR-WASTE2); only a beat
    # of unknown or invalid basis reaches that count (the control).
    ("beat-priced", mk(extra=[BEAT]),
     {SP_T: ("$0.20", "complete", PRICED_COV % ("0 priced closes", "1 priced hold beat", 0, 0, 0, 0, GAPS0))}, (), [],
     ["- run-r.jsonl:5 · 2026-10-06 11:15:00 +0100 · cost_src result · total_cost_usd 0.2"], 3),
    ("beat-plan", mk(extra=[dict(BEAT, cost_src="codex-plan", total_cost_usd=None)]),
     {SP_HB: ("1", "complete", "plan usage or no process")}, (), [],
     ["- run-r.jsonl:5 · 2026-10-06 11:15:00 +0100 · cost_src codex-plan · total_cost_usd None"], 3),
    ("beat-price-null", mk(extra=[dict(BEAT, total_cost_usd=None)]),
     {SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 1, 0, 0, 0, GAPS0))}, (),
     [gl(BTW, "total_cost_usd is null on a result-priced close", "Priced spend: hold beats")],
     ["ROW:Priced spend|hold beats not priced|0|complete",
      "- run-r.jsonl:5 · 2026-10-06 11:15:00 +0100 · cost_src result · total_cost_usd None"], (3, "F3")),
    ("beat-price-wrong-type", mk(extra=[dict(BEAT, total_cost_usd="0.2")]),
     {SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 1, 0, GAPS0))}, (),
     [gl(BTW, "total_cost_usd is a string", "Priced spend: hold beats")],
     ["ROW:Priced spend|hold beats not priced|0|complete",
      "- run-r.jsonl:5 · 2026-10-06 11:15:00 +0100 · cost_src result · total_cost_usd 0.2"], (3, "F3")),
    ("beat-basis-unknown-control", mk(extra=[dict((k, v) for k, v in BEAT.items() if k not in ("cost_src", "total_cost_usd"))]),
     {SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 1, 0, 0, 0, GAPS0)),
      SP_HB: ("unknown; known subtotal 0", "unknown", "plan usage or no process")}, (),
     [gl(BTW, "no cost_src and no price on the close", "Priced spend: hold beats")],
     ["ROW:Priced spend|hold beats not priced|unknown; known subtotal 0|unknown",
      "- run-r.jsonl:5 · 2026-10-06 11:15:00 +0100 · cost_src None · total_cost_usd None"], "F3"),
    # Finding 4 of CR-WASTE1: a damaged source beside an independent valid source keeps the
    # latter's totals known; the uncertainty is named at the affected part, run, helper or class.
    # (a) An undated boundary of source transcript: boundary figures, the transcript idle sum, the
    # head fence, the boundary summary and the snapshots read unknown; every helper channel and
    # every episode figure stays complete.
    ("scope-undated-boundary-beside-known-closes",
     mk(extra=[{"ts": "bad", "event": "phase-boundary", "idle_min": 1, "idle_src": "transcript", "over_cap_reports": 0,
                "rewrites": 0, "rewrites_total": 1, "head_denials": 5, "denials": 0, "run_spend_usd": 1.0}]),
     {(B, "boundary events"): ("unknown; known subtotal 1", "unknown", "counted at their own timestamps; " + G1),
      (B, "recorded idle, idle_src transcript"): ("unknown; known subtotal 2.5 min", "unknown", IDLE_COV % "1 boundary"),
      (B, "recorded idle unknown"): ("unknown; known subtotal 0", "unknown", IDLEU_COV),
      (B, "over-cap reports"): ("unknown; known subtotal 0", "unknown", OVER_COV % "0 boundaries"),
      (B, "rewrites (deltas)"): ("unknown; known subtotal 1", "unknown", REW_COV % "0 boundaries"),
      (B, "cumulative rewrites snapshots"): ("unknown; known subtotal 1", "unknown", BS_COV % 0),
      (RF, "head fence (boundaries)"): ("unknown; known subtotal 0", "unknown", HF_COV % ("1 boundary", 0, G1)),
      (RF, "boundary summary of helper tool refusals"): ("unknown; known subtotal 0", "unknown", HS_COV % ("0 boundaries", G1)),
      SP_SS: ("unknown; known subtotal 2", "unknown", SS_COV % 0)}, (),
     [gl("run-r.jsonl:5 · time unknown", "no usable timestamp ('bad')", BOUNDARY_PARTS)],
     ["ROW:Refusals|helper tool|0|complete", "ROW:Refusals|helper sandbox|0|complete", BASE_ROW], 4),
    # (b) An undated close of another helper whose class, builder, is known and named by no other
    # line of that helper: every episode figure of the run reads unknown, but the head fence and the
    # boundary summary stay complete, and so do the critic class row, the helper run-r/L row and the
    # reviewing-class counts, which a builder's close cannot reach (finding 3 of CR-WASTE2; the
    # reviewed expectation made those counts unknown).
    ("scope-undated-close-beside-known-boundary",
     mk(extra=[{"ts": "bad", "event": "lane-closed", "lane": "Z", "class": "builder", "exit_class": "completed",
                "duration_s": 10}]),
     dict(UNDATED_CLOSE), (),
     [gl("run-r.jsonl:5 · time unknown", "no usable timestamp ('bad')", EPISODE_PARTS)],
     ["ROW:Review activity and possible loops|reviewing-class episodes|1|complete",
      "ROW:Review activity and possible loops|positional candidate groups|1|complete",
      "ROW:Refusals|head fence (boundaries)|0|complete", 'ROW:Helper time|helper run-r/"L"|90.5 s (1.5 min)|complete',
      "ROW:Helper time|class critic|90.5 s (1.5 min)|complete", BASE_ROW], (4, "F3")),
    # (b2) The control: the same undated close with class critic could be a reviewing-class
    # episode, so the review counts and the critic class row read unknown with known subtotals.
    ("scope-undated-close-of-reviewing-class-control",
     mk(extra=[{"ts": "bad", "event": "lane-closed", "lane": "Z", "class": "critic", "exit_class": "completed",
                "duration_s": 10}]),
     dict(list(UNDATED_CLOSE.items()) + list(REVIEW_REACHED.items())), (),
     [gl("run-r.jsonl:5 · time unknown", "no usable timestamp ('bad')", EPISODE_PARTS)],
     ["ROW:Review activity and possible loops|reviewing-class episodes|unknown; known subtotal 1|unknown",
      "ROW:Helper time|class critic|unknown; known subtotal 90.5 s (1.5 min)|unknown", BASE_ROW], "F3"),
    # (b3) The control: the undated close names builder, but its helper's opening names critic, so
    # the episode's class could conflict and be any class: the review counts read unknown.
    ("scope-undated-close-conflicting-class-control",
     mk(extra=[{"ts": "2026-10-06T11:10:00+0100", "event": "lane-open", "lane": "Z", "class": "critic"},
               {"ts": "bad", "event": "lane-closed", "lane": "Z", "class": "builder", "exit_class": "completed",
                "duration_s": 10}]),
     dict(list(UNDATED_CLOSE.items()) + list(REVIEW_REACHED.items())), (),
     [gl("run-r.jsonl:6 · time unknown", "no usable timestamp ('bad')", EPISODE_PARTS)],
     ["ROW:Review activity and possible loops|reviewing-class episodes|unknown; known subtotal 1|unknown",
      '- run-r:"Z":5 · unresolved · opened 2026-10-06 11:10:00 +0100 · line 6 closes it with no usable timestamp (\'bad\'): a malformed close is not evidence that the episode resolved · its record holds invalid lines',
      BASE_ROW], "F3"),
    # Idle minutes by source (finding 3 of CR-WASTE2). (i) A boundary of source record without a
    # usable idle_min beside the base boundary of source transcript: only the record sum is
    # unknown (known subtotal 0 min); the transcript sum stays complete.
    ("scope-idle-source-known",
     mk(extra=[{"ts": "2026-10-06T11:30:00+0100", "event": "phase-boundary", "idle_src": "record", "over_cap_reports": 0,
                "rewrites": 0, "rewrites_total": 1, "head_denials": 0, "denials": 0, "run_spend_usd": 1.0}]),
     {(B, "boundary events"): ("2", "complete", "counted at their own timestamps; " + GAPS0),
      (B, "recorded idle, idle_src record"): ("unknown; known subtotal 0 min", "unknown",
                                              "0 boundaries, 1 more without a usable idle_min; not independently verified head idleness"),
      (B, "recorded idle unknown"): ("1", "complete", IDLEU_COV),
      (B, "cumulative rewrites snapshots"): ("2", "complete", BS_COV % 0),
      (RF, "head fence (boundaries)"): ("0", "complete", HF_COV % ("2 boundaries", 0, GAPS0)),
      SP_SS: ("3", "complete", SS_COV % 0)}, (),
     [gl("run-r.jsonl:5 · 2026-10-06 11:30:00 +0100", "idle_min is not on the boundary", "Phase boundaries")],
     ["ROW:Phase boundaries|recorded idle, idle_src transcript|2.5 min|complete", "· idle_min None (record) ·"], "F3"),
    # (ii) The control: a boundary whose idle_src is unusable could belong to any source, so the
    # transcript sum reads unknown.
    ("scope-idle-source-invalid-control",
     mk(extra=[{"ts": "2026-10-06T11:30:00+0100", "event": "phase-boundary", "idle_min": 1, "idle_src": 5,
                "over_cap_reports": 0, "rewrites": 0, "rewrites_total": 1, "head_denials": 0, "denials": 0,
                "run_spend_usd": 1.0}]),
     {(B, "boundary events"): ("2", "complete", "counted at their own timestamps; " + GAPS0),
      (B, "recorded idle, idle_src transcript"): ("unknown; known subtotal 2.5 min", "unknown", IDLE_COV % "1 boundary"),
      (B, "recorded idle unknown"): ("1", "complete", IDLEU_COV),
      (B, "cumulative rewrites snapshots"): ("2", "complete", BS_COV % 0),
      (RF, "head fence (boundaries)"): ("0", "complete", HF_COV % ("2 boundaries", 0, GAPS0)),
      SP_SS: ("3", "complete", SS_COV % 0)}, (),
     [gl("run-r.jsonl:5 · 2026-10-06 11:30:00 +0100", "idle_src is a number", "Phase boundaries")],
     ["ROW:Phase boundaries|recorded idle, idle_src transcript|unknown; known subtotal 2.5 min|unknown"], "F3"),
    # (iii) An undated boundary of source record: every boundary figure reads unknown, and a record
    # row appears (known subtotal 0 min); the transcript sum, which that boundary cannot reach,
    # stays complete.
    ("scope-undated-boundary-of-another-source",
     mk(extra=[{"ts": "bad", "event": "phase-boundary", "idle_min": 1, "idle_src": "record", "over_cap_reports": 0,
                "rewrites": 0, "rewrites_total": 1, "head_denials": 5, "denials": 0, "run_spend_usd": 1.0}]),
     {(B, "boundary events"): ("unknown; known subtotal 1", "unknown", "counted at their own timestamps; " + G1),
      (B, "recorded idle, idle_src record"): ("unknown; known subtotal 0 min", "unknown", IDLE_COV % "0 boundaries"),
      (B, "recorded idle unknown"): ("unknown; known subtotal 0", "unknown", IDLEU_COV),
      (B, "over-cap reports"): ("unknown; known subtotal 0", "unknown", OVER_COV % "0 boundaries"),
      (B, "rewrites (deltas)"): ("unknown; known subtotal 1", "unknown", REW_COV % "0 boundaries"),
      (B, "cumulative rewrites snapshots"): ("unknown; known subtotal 1", "unknown", BS_COV % 0),
      (RF, "head fence (boundaries)"): ("unknown; known subtotal 0", "unknown", HF_COV % ("1 boundary", 0, G1)),
      (RF, "boundary summary of helper tool refusals"): ("unknown; known subtotal 0", "unknown", HS_COV % ("0 boundaries", G1)),
      SP_SS: ("unknown; known subtotal 2", "unknown", SS_COV % 0)}, (),
     [gl("run-r.jsonl:5 · time unknown", "no usable timestamp ('bad')", BOUNDARY_PARTS)],
     ["ROW:Phase boundaries|recorded idle, idle_src transcript|2.5 min|complete"], "F3"),
    # (c) An undated line of unknown kind in another record: every figure is unknown, but the run
    # row and the helper row of the valid record stay complete; the damaged record gets its own row.
    ("scope-damaged-record-beside-valid-record", {},
     {(H, "total"): ("unknown; known subtotal 90.5 s (1.5 min)", "unknown", "1 close: 1 timed, 0 not applicable, 0 unknown or invalid; " + G1),
      (H, "run run-s"): ("unknown; known subtotal 0 s (0.0 min)", "unknown", "0 closes: 0 not applicable, 0 unknown or invalid; " + G1),
      (H, "class critic"): ("unknown; known subtotal 90.5 s (1.5 min)", "unknown", "1 close: 0 not applicable, 0 unknown or invalid; " + G1),
      (F, "closes"): ("unknown; known subtotal 1", "unknown", G1),
      (F, "completed"): ("unknown; known subtotal 1", "unknown", "exit_class completed"),
      (F, "non-completed"): ("unknown; known subtotal 0", "unknown", NONCOMP % (0, 0, G1)),
      (F, "status unknown or invalid"): ("unknown; known subtotal 0", "unknown", "no usable exit_class"),
      (F, "non-completed, later resumed"): ("unknown; known subtotal 0", "unknown", LATER),
      (RV, "reviewing-class episodes"): ("unknown; known subtotal 1", "unknown", RVC_COV % ("0 closes", G1)),
      (RV, "positional candidate groups"): ("unknown; known subtotal 1", "unknown", GROUPS_COV % G1),
      (RV, "reviewing-class episodes with no positional group"): ("unknown; known subtotal 0", "unknown", NOGROUP_COV),
      (RV, "candidate groups with two or more reviewing-class episodes"): ("unknown; known subtotal 0", "unknown", MULTI_COV),
      (B, "boundary events"): ("unknown; known subtotal 1", "unknown", "counted at their own timestamps; " + G1),
      (B, "recorded idle, idle_src transcript"): ("unknown; known subtotal 2.5 min", "unknown", IDLE_COV % "1 boundary"),
      (B, "recorded idle unknown"): ("unknown; known subtotal 0", "unknown", IDLEU_COV),
      (B, "over-cap reports"): ("unknown; known subtotal 0", "unknown", OVER_COV % "0 boundaries"),
      (B, "rewrites (deltas)"): ("unknown; known subtotal 1", "unknown", REW_COV % "0 boundaries"),
      (B, "cumulative rewrites snapshots"): ("unknown; known subtotal 1", "unknown", BS_COV % 0),
      (RF, "helper tool"): ("unknown; known subtotal 0", "unknown", "1 close: 1 known, 0 not applicable, 0 unknown or invalid; " + G1),
      (RF, "helper fence"): ("unknown; known subtotal 0", "unknown", "1 close: 1 known, 0 not applicable, 0 unknown or invalid; " + G1),
      (RF, "helper sandbox"): ("unknown; known subtotal 0", "unknown", "1 close: 1 known, 0 not applicable, 0 unknown or invalid; " + G1),
      (RF, "head fence (boundaries)"): ("unknown; known subtotal 0", "unknown", HF_COV % ("1 boundary", 0, G1)),
      (RF, "boundary summary of helper tool refusals"): ("unknown; known subtotal 0", "unknown", HS_COV % ("0 boundaries", G1)),
      SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 0, 0, G1)),
      SP_PC: ("unknown; known subtotal 1", "unknown", PLAN_COV % (1, 0, 0, 0, 0, 0)),
      SP_TCI: tok(10, 1, 0, tc(1), gaps=1), SP_TCO: tok(2, 1, 0, tc(1), gaps=1),
      SP_TII: tok(0, 0, 0, ti(0), gaps=1), SP_TIO: tok(0, 0, 0, ti(0), gaps=1),
      SP_UN: ("unknown; known subtotal 0", "unknown", "token totals only; no dollar figure"),
      SP_NA: ("unknown; known subtotal 0", "unknown", "exit_class spawn-failed"),
      SP_HB: ("unknown; known subtotal 0", "unknown", "plan usage or no process"),
      SP_SS: ("unknown; known subtotal 2", "unknown", SS_COV % 0)}, (),
     ["- run-s.jsonl:1 · time unknown · not JSON · affects: every figure"],
     ["ROW:Helper time|run run-r|90.5 s (1.5 min)|complete",
      "- run-r: 90.5 s (1.5 min) over 1 close (0 not applicable, 0 unknown or invalid; 0 named gaps (detail))",
      '- run-r/"L": 90.5 s (1.5 min) over 1 close (0 not applicable, 0 unknown or invalid; 0 named gaps (detail))',
      "- run-s: unknown; known subtotal 0 s (0.0 min) over 0 closes (0 not applicable, 0 unknown or invalid; 1 named gap (detail))"],
     4, {"run-s.jsonl": ['{"event": "lane-closed", "lane": "Q"']}),
]

# CR-WASTE3 finding 2: a spawn failure's documented non-applicability covers the absent fields only.
# The close keeps no duration, no denials and no usage (codex-lane.py:915-919), so duration, tool
# and fence are not applicable as before; a standalone sandbox_denials it does record is read as
# recorded: invalid stays invalid and null unknown, each named on the sandbox channel alone, and a
# count stays a count. Every other figure is the spawn-failure control's (spawn-failed-not-applicable).
NA_CH = "1 close: 0 known, 1 not applicable, 0 unknown or invalid; " + GAPS0
SPAWN_NA = "not applicable (no process started (exit_class spawn-failed))"
SPAWN_DROP = ("duration_s", "denials", "usage", "usage_state", "usage_complete")
SBP = "Refusals: helper sandbox"
SSP = "Priced spend: snapshots"
UNK_SB = ("unknown; known subtotal 0", "unknown", UNK_CH)


def spawn_rows(sandbox):
    return dict([((H, "total"), ("0 s (0.0 min)", "complete", "1 close: 0 timed, 1 not applicable, 0 unknown or invalid; " + GAPS0))]
                + list(views(("0 s (0.0 min)", "complete", "1 close: 1 not applicable, 0 unknown or invalid; " + GAPS0)).items())
                + [((F, "completed"), ("0", "complete", "exit_class completed")),
                   ((F, "non-completed"), ("1", "complete", NONCOMP % (0, 0, GAPS0))),
                   ((F, "status spawn-failed"), ("1", "complete", "recorded exit_class")),
                   ((RF, "helper tool"), ("0", "complete", NA_CH)), ((RF, "helper fence"), ("0", "complete", NA_CH)),
                   ((RF, "helper sandbox"), sandbox),
                   (SP_PC, ("1", "complete", PLAN_COV % (0, 0, 0, 1, 0, 0))),
                   (SP_TCI, tok(0, 0, 0, tc(0))), (SP_TCO, tok(0, 0, 0, tc(0)))])


def spawn_case(name, value, sandbox, gaps, cell):
    # The first needle is the close's four cells: exit, tool, fence, sandbox.
    return (name, mk(close_changes={"exit_class": "spawn-failed", "exit_code": 3, "sandbox_denials": value},
                     close_drop=SPAWN_DROP),
            spawn_rows(sandbox), (), gaps, ["| spawn-failed | %s | %s | %s |" % (SPAWN_NA, SPAWN_NA, cell)], "G2")


MISSING_PLAN = {SP_PC: ("1", "complete", PLAN_COV % (0, 0, 0, 1, 0, 0)), SP_TCI: tok(0, 0, 0, tc(0)), SP_TCO: tok(0, 0, 0, tc(0))}
BEAT_INVALID_BASIS = {SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 1, 0, GAPS0)),
                      SP_HB: ("unknown; known subtotal 0", "unknown", "plan usage or no process")}
SS3 = {SP_SS: ("3", "complete", SS_COV % 0)}
PLAIN_CLOSE = {"ts": "2026-10-06T11:45:00+0100", "event": "run-close", "shape": "plain-lane-run", "spend_usd": 3.0,
               "spend_src": "sum of 1 lane-closed total_cost_usd"}
SNAP = "- run-r.jsonl:5 · 2026-10-06 11:45:00 +0100 · run-close · "


def without(event, field):
    return dict((k, v) for k, v in event.items() if k != field)


# CR-WASTE3 finding 3: the cells of the field and state matrix (FIELDS.md, "Field and state coverage")
# the earlier suite left without a case. Each is fixed by hand from the value rules: an absent or
# null field is unknown and named, another kind, a negative, a fraction for a count or a word
# outside the writer's vocabulary invalid and named, a known 0 a measured zero; a field outside its
# event's format is not read.
T2_CASES += [
    spawn_case("spawn-failed-sandbox-invalid-string", "bad", UNK_SB, [gl(CW, "sandbox_denials is a string", SBP)],
               "invalid (sandbox_denials is a string)"),
    spawn_case("spawn-failed-sandbox-null", None, UNK_SB, [gl(CW, "sandbox_denials is recorded as null", SBP)],
               "unknown (sandbox_denials is recorded as null)"),
    spawn_case("spawn-failed-sandbox-negative", -1, UNK_SB, [gl(CW, "sandbox_denials is negative", SBP)],
               "invalid (sandbox_denials is negative)"),
    spawn_case("spawn-failed-sandbox-fraction", 1.5, UNK_SB, [gl(CW, "sandbox_denials is a non-integer number", SBP)],
               "invalid (sandbox_denials is a non-integer number)"),
    spawn_case("spawn-failed-sandbox-boolean", True, UNK_SB, [gl(CW, "sandbox_denials is a boolean", SBP)],
               "invalid (sandbox_denials is a boolean)"),
    spawn_case("spawn-failed-sandbox-zero", 0, ("0", "complete", CH), [], "0 (measured zero)"),
    spawn_case("spawn-failed-sandbox-positive", 2, ("2", "complete", CH), [], "2"),
    # lane.py's spawn failure (lane.py:3244-3252) carries no cost fields either: its spend is not
    # applicable by the same documented rule, and it is no plan close.
    ("spawn-failed-claude-shape",
     mk(close_changes={"exit_class": "spawn-failed", "exit_code": 3},
        close_drop=SPAWN_DROP + ("sandbox_denials", "cost_src", "total_cost_usd")),
     dict(list(spawn_rows(("0", "complete", NA_CH)).items())
          + [(SP_PC, ("0", "complete", PLAN_COV % (0, 0, 0, 0, 0, 0))), (SP_NA, ("1", "complete", "exit_class spawn-failed"))]),
     (), [], ["| na (no process started (exit_class spawn-failed)) |"], "G3"),
    # The sandbox channel's two fields, each on its own.
    ("denials-sandbox-null", mk(close_changes={"denials": {"tool": 0, "fence": 0, "sandbox": None}}, close_drop=("sandbox_denials",)),
     unk_channel("sandbox"), (), [gl(CW, "denials.sandbox is recorded as null", SBP)],
     ["| unknown (denials.sandbox is recorded as null) |"], "G3"),
    ("denials-sandbox-negative", mk(close_changes={"denials": {"tool": 0, "fence": 0, "sandbox": -1}}, close_drop=("sandbox_denials",)),
     unk_channel("sandbox"), (), [gl(CW, "denials.sandbox is negative", SBP)], ["| invalid (denials.sandbox is negative) |"], "G3"),
    ("sandbox-denials-wrong-type", mk(close_changes={"denials": {"tool": 0, "fence": 0}, "sandbox_denials": "2"}),
     unk_channel("sandbox"), (), [gl(CW, "sandbox_denials is a string", SBP)], ["| invalid (sandbox_denials is a string) |"], "G3"),
    ("tool-fraction", mk(close_changes={"denials": {"tool": 1.5, "fence": 0, "sandbox": 0}}), unk_channel("tool"), (),
     [gl(CW, "denials.tool is a non-integer number", "Refusals: helper tool")], ["| invalid (denials.tool is a non-integer number) |"], "G3"),
    # fence_denials_transcript: its zero and a negative beside the watch close's "unknown"; beside a
    # denials object it is no input of any channel (the fence comes from denials.fence).
    ("fence-transcript-zero", mk(close_changes={"denials": "unknown", "fence_denials_transcript": 0}), unk_channel("tool"), (),
     [gl(CW, "denials are recorded as \"unknown\"", "Refusals: helper tool")],
     ["| unknown (denials are recorded as \"unknown\") | 0 (measured zero) | 0 (measured zero) |"], "G3"),
    ("fence-transcript-negative", mk(close_changes={"denials": "unknown", "fence_denials_transcript": -4}),
     unk_channel("tool", "fence"), (),
     [gl(CW, "denials are recorded as \"unknown\"", "Refusals: helper tool"),
      gl(CW, "fence_denials_transcript is negative", "Refusals: helper fence")],
     ["| invalid (fence_denials_transcript is negative) |"], "G3"),
    ("fence-transcript-beside-denials-object", mk(close_changes={"fence_denials_transcript": "bad"}), {}, (), [], [BASE_ROW], "G3"),
    # Plan usage: the output direction negative; usage.calls absent, null and negative on a close read
    # by the writer's own rule (codex-lane.py:723-735: absent or null calls read as no usage reported);
    # usage_complete is not read beside a recorded usage_state.
    ("plan-complete-output-negative", mk(close_changes={"usage": {"input_tokens": 10, "output_tokens": -2, "calls": 1}}),
     plan_rows("complete", 10, None), (), [gl(CW, "usage.output_tokens is negative", "Priced spend: plan usage")],
     ["| plan usage, complete; input 10, output invalid (usage.output_tokens is negative) |"], "G3"),
    ("plan-historical-calls-absent", mk(close_changes={"usage_complete": False, "usage": {"input_tokens": 10, "output_tokens": 2}},
                                        close_drop=("usage_state",)),
     MISSING_PLAN, (), [], ["| plan usage, missing (no usage reported) |"], "G3"),
    ("plan-historical-calls-null", mk(close_changes={"usage_complete": False, "usage": {"input_tokens": 10, "output_tokens": 2, "calls": None}},
                                      close_drop=("usage_state",)),
     MISSING_PLAN, (), [], ["| plan usage, missing (no usage reported) |"], "G3"),
    ("plan-historical-calls-negative", mk(close_changes={"usage_complete": False, "usage": {"input_tokens": 10, "output_tokens": 2, "calls": -1}},
                                          close_drop=("usage_state",)),
     plan("invalid"), (), [gl(CW, "usage.calls is negative", "Priced spend: plan usage")],
     ["| plan usage, invalid (usage.calls is negative); input 10, output 2 |"], "G3"),
    ("plan-state-beside-wrong-complete-field", mk(close_changes={"usage_complete": "yes"}), {}, (), [], [BASE_ROW], "G3"),
    # The gate: a decision of the wrong kind; run_spend_usd zero, absent, of the wrong kind, negative.
    ("gate-decision-wrong-type", mk(gate_changes={"decision": 5}), NO_GROUP, (), [],
     ["| none: the last gate before its opening (line 1) records a decision that is a number |"], "G3"),
    ("gate-run-spend-zero", mk(gate_changes={"run_spend_usd": 0}), {}, (), [],
     ["- run-r.jsonl:1 · 2026-10-06 09:59:00 +0100 · gate · run_spend_usd 0"], "G3"),
    ("gate-run-spend-absent", mk(gate_drop=("run_spend_usd",)), SS_UNK1, (), [gl(GW, "run_spend_usd is not on the event", SSP)],
     ["- run-r.jsonl:1 · 2026-10-06 09:59:00 +0100 · gate · unknown (run_spend_usd is not on the event)"], "G3"),
    ("gate-run-spend-wrong-type", mk(gate_changes={"run_spend_usd": "0.5"}), SS_UNK1, (), [gl(GW, "run_spend_usd is a string", SSP)],
     ["- run-r.jsonl:1 · 2026-10-06 09:59:00 +0100 · gate · invalid (run_spend_usd is a string)"], "G3"),
    ("gate-run-spend-negative", mk(gate_changes={"run_spend_usd": -0.5}), SS_UNK1, (), [gl(GW, "run_spend_usd is negative", SSP)],
     ["- run-r.jsonl:1 · 2026-10-06 09:59:00 +0100 · gate · invalid (run_spend_usd is negative)"], "G3"),
    # The boundary's helper summary, negative.
    ("summary-negative", mk(boundary_changes={"denials": -1}), SUM_UNK, (),
     [gl(BW, "denials (the boundary's helper summary) is negative", "Refusals: boundary summary")], ["· denials -1 ·"], "G3"),
    # Hold beats: a zero, absent and negative price on a recorded result basis (only the priced
    # total reads unknown); a null basis beside a price (undeclared); a basis of the wrong kind or
    # outside the vocabulary (invalid: the count of beats not priced reads unknown too).
    ("beat-price-zero", mk(extra=[dict(BEAT, total_cost_usd=0)]),
     {SP_T: ("$0.00", "complete", PRICED_COV % ("0 priced closes", "1 priced hold beat", 0, 0, 0, 0, GAPS0))}, (), [],
     ["- run-r.jsonl:5 · 2026-10-06 11:15:00 +0100 · cost_src result · total_cost_usd 0"], "G3"),
    ("beat-price-absent", mk(extra=[without(BEAT, "total_cost_usd")]),
     {SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 1, 0, 0, 0, GAPS0))}, (),
     [gl(BTW, "total_cost_usd is absent on a result-priced close", "Priced spend: hold beats")],
     ["ROW:Priced spend|hold beats not priced|0|complete",
      "- run-r.jsonl:5 · 2026-10-06 11:15:00 +0100 · cost_src result · total_cost_usd None"], "G3"),
    ("beat-price-negative", mk(extra=[dict(BEAT, total_cost_usd=-0.2)]),
     {SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 1, 0, GAPS0))}, (),
     [gl(BTW, "total_cost_usd is negative", "Priced spend: hold beats")],
     ["ROW:Priced spend|hold beats not priced|0|complete", "· cost_src result · total_cost_usd -0.2"], "G3"),
    ("beat-cost-src-null", mk(extra=[dict(BEAT, cost_src=None)]),
     {SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 1, 0, 0, GAPS0))}, (),
     [gl(BTW, "a price with cost_src recorded as null: its basis is undeclared", "Priced spend: hold beats")],
     ["ROW:Priced spend|hold beats not priced|0|complete", "· cost_src None · total_cost_usd 0.2"], "G3"),
    ("beat-cost-src-wrong-type", mk(extra=[dict(BEAT, cost_src=5)]), BEAT_INVALID_BASIS, (),
     [gl(BTW, "cost_src is a number, not a known basis", "Priced spend: hold beats")],
     ["ROW:Priced spend|hold beats not priced|unknown; known subtotal 0|unknown", "· cost_src 5 · total_cost_usd 0.2"], "G3"),
    ("beat-cost-src-outside", mk(extra=[dict(BEAT, cost_src="estimate")]), BEAT_INVALID_BASIS, (),
     [gl(BTW, "cost_src 'estimate' is not a known basis", "Priced spend: hold beats")],
     ["· cost_src estimate · total_cost_usd 0.2"], "G3"),
    # The run-close: `shape` selects its snapshot field, and the writer writes it only as
    # plain-lane-run (handsoff.py:1423, 7881). Absent is the ordinary close; null is unknown and any
    # other value or kind invalid, named, never read as the ordinary close. Each snapshot field
    # through its values; each field is no input on the other shape.
    ("run-close-shape-null", mk(extra=[dict(RUN_CLOSE, shape=None)]), SS_UNK2, (), [gl(RCW, "shape is recorded as null", SSP)],
     [SNAP + "unknown (shape is recorded as null)"], "G3"),
    ("run-close-shape-outside", mk(extra=[dict(RUN_CLOSE, shape="x")]), SS_UNK2, (),
     [gl(RCW, "shape 'x' is outside the writer's vocabulary", SSP)], [SNAP + "invalid (shape 'x' is outside the writer's vocabulary)"], "G3"),
    ("run-close-shape-wrong-type", mk(extra=[dict(RUN_CLOSE, shape=5)]), SS_UNK2, (), [gl(RCW, "shape is a number", SSP)],
     [SNAP + "invalid (shape is a number)"], "G3"),
    ("run-close-spend-number", mk(extra=[RUN_CLOSE]), SS3, (), [], [SNAP + "run_spend_usd 3.0"], "G3"),
    ("run-close-spend-zero", mk(extra=[dict(RUN_CLOSE, run_spend_usd=0)]), SS3, (), [], [SNAP + "run_spend_usd 0"], "G3"),
    ("run-close-spend-absent", mk(extra=[without(RUN_CLOSE, "run_spend_usd")]), SS_UNK2, (),
     [gl(RCW, "run_spend_usd is not on the event", SSP)], [SNAP + "unknown (run_spend_usd is not on the event)"], "G3"),
    ("run-close-spend-wrong-type", mk(extra=[dict(RUN_CLOSE, run_spend_usd="3")]), SS_UNK2, (),
     [gl(RCW, "run_spend_usd is a string", SSP)], [SNAP + "invalid (run_spend_usd is a string)"], "G3"),
    ("run-close-spend-negative", mk(extra=[dict(RUN_CLOSE, run_spend_usd=-3)]), SS_UNK2, (),
     [gl(RCW, "run_spend_usd is negative", SSP)], [SNAP + "invalid (run_spend_usd is negative)"], "G3"),
    # The review's own expectation (CR-WASTE3 finding 3): a plain run's close without spend_usd leaves
    # two known spend snapshots and one unknown, with a named spend_usd gap; the episode figures are
    # unchanged.
    ("plain-run-close-spend-absent", mk(extra=[without(PLAIN_CLOSE, "spend_usd")]), SS_UNK2, (),
     [gl(RCW, "spend_usd is not on the event", SSP)], [SNAP + "unknown (spend_usd is not on the event)"], "G3"),
    ("plain-run-close-spend-null", mk(extra=[dict(PLAIN_CLOSE, spend_usd=None)]), SS_UNK2, (),
     [gl(RCW, "spend_usd is recorded as null", SSP)], [SNAP + "unknown (spend_usd is recorded as null)"], "G3"),
    ("plain-run-close-spend-zero", mk(extra=[dict(PLAIN_CLOSE, spend_usd=0)]), SS3, (), [], [SNAP + "spend_usd 0"], "G3"),
    ("plain-run-close-spend-wrong-type", mk(extra=[dict(PLAIN_CLOSE, spend_usd="3.0")]), SS_UNK2, (),
     [gl(RCW, "spend_usd is a string", SSP)], [SNAP + "invalid (spend_usd is a string)"], "G3"),
    ("plain-run-close-spend-negative", mk(extra=[dict(PLAIN_CLOSE, spend_usd=-3.0)]), SS_UNK2, (),
     [gl(RCW, "spend_usd is negative", SSP)], [SNAP + "invalid (spend_usd is negative)"], "G3"),
    ("plain-run-close-reads-spend-not-run-spend", mk(extra=[dict(PLAIN_CLOSE, run_spend_usd="bad")]), SS3, (), [],
     [SNAP + "spend_usd 3.0"], "G3"),
    ("run-close-ordinary-ignores-spend-usd", mk(extra=[dict(RUN_CLOSE, spend_usd="bad")]), SS3, (), [],
     [SNAP + "run_spend_usd 3.0"], "G3"),
    ("head-exit-spent-zero", mk(extra=[dict(HEAD_EXIT, spent_usd=0)]), SS3, (), [],
     ["- run-r.jsonl:5 · 2026-10-06 11:30:00 +0100 · head-exit · spent_usd 0"], "G3"),
]

# The reader's range (FIELDS.md, "The reader's range"), written out here from that section, never
# taken from the reader: a recorded number it sums, rounds or renders is read only when its magnitude
# is below 10^15 and it has at most 30 places after the decimal point as written; any other is
# invalid, named, its figure unknown with the known subtotal kept. 10^15 is the first value beyond;
# 1e-31 has 31 places.
E15 = 10 ** 15
BR = "beyond the reader's range (magnitude too large)"
BP = "beyond the reader's range (too many decimal places)"
BOUNDARY_SNAP = "- run-r.jsonl:4 · 2026-10-06 11:00:00 +0100 · phase-boundary · "
GATE_SNAP = "- run-r.jsonl:1 · 2026-10-06 09:59:00 +0100 · gate · "
HEAD_SNAP = "- run-r.jsonl:5 · 2026-10-06 11:30:00 +0100 · head-exit · "

# Route 0: every numeric field the reader consumes, one case each at 10^15 (the "Other invalid"
# column of FIELDS.md's matrix; T2.field-state-matrix-complete holds every such row to one), each
# decimal field once more at 31 places, and the two edges read as known: the largest magnitude within
# the range (999999999999999 s, whose minutes 16666666666666.65 round half-even to .6) and the most
# places within it (a price of 1e-30, $0.00 to the cent, its exact value kept in the detail). Each
# invalid case's expected rows are its field's negative case's, the reason its own.
T2_CASES += [
    ("duration-beyond-range", mk(close_changes={"duration_s": E15}), unk_duration(), (),
     [gl(CW, "duration_s is " + BR, "Helper time")], ["| invalid (duration_s is %s) |" % BR], "R0"),
    ("duration-beyond-places", mk(close_changes={"duration_s": 1e-31}), unk_duration(), (),
     [gl(CW, "duration_s is " + BP, "Helper time")], ["| invalid (duration_s is %s) |" % BP], "R0"),
    ("duration-largest-within-range", mk(close_changes={"duration_s": E15 - 1}),
     dict([((H, "total"), ("999999999999999 s (16666666666666.6 min)", "complete", ONE))]
          + list(views(("999999999999999 s (16666666666666.6 min)", "complete", VIEW)).items())), (), [],
     ["+0100 | 999999999999999 | completed |"], "R0"),
    ("tool-beyond-range", mk(close_changes={"denials": {"tool": E15, "fence": 0, "sandbox": 0}}), unk_channel("tool"), (),
     [gl(CW, "denials.tool is " + BR, "Refusals: helper tool")], ["| invalid (denials.tool is %s) |" % BR], "R0"),
    ("fence-beyond-range", mk(close_changes={"denials": {"tool": 0, "fence": E15, "sandbox": 0}}), unk_channel("fence"), (),
     [gl(CW, "denials.fence is " + BR, "Refusals: helper fence")], ["| invalid (denials.fence is %s) |" % BR], "R0"),
    ("denials-sandbox-beyond-range", mk(close_changes={"denials": {"tool": 0, "fence": 0, "sandbox": E15}}, close_drop=("sandbox_denials",)),
     unk_channel("sandbox"), (), [gl(CW, "denials.sandbox is " + BR, SBP)], ["| invalid (denials.sandbox is %s) |" % BR], "R0"),
    ("sandbox-denials-beyond-range", mk(close_changes={"denials": {"tool": 0, "fence": 0}, "sandbox_denials": E15}),
     unk_channel("sandbox"), (), [gl(CW, "sandbox_denials is " + BR, SBP)], ["| invalid (sandbox_denials is %s) |" % BR], "R0"),
    ("fence-transcript-beyond-range", mk(close_changes={"denials": "unknown", "fence_denials_transcript": E15}),
     unk_channel("tool", "fence"), (),
     [gl(CW, "denials are recorded as \"unknown\"", "Refusals: helper tool"),
      gl(CW, "fence_denials_transcript is " + BR, "Refusals: helper fence")],
     ["| invalid (fence_denials_transcript is %s) |" % BR], "R0"),
    ("price-beyond-range", mk(close_changes={"cost_src": "result", "total_cost_usd": E15}), basis("invalid-price"), (),
     [gl(CW, "total_cost_usd is " + BR, "Priced spend: closes")], ["| invalid-price (total_cost_usd is %s) |" % BR], "R0"),
    ("price-beyond-places", mk(close_changes={"cost_src": "result", "total_cost_usd": 1e-31}), basis("invalid-price"), (),
     [gl(CW, "total_cost_usd is " + BP, "Priced spend: closes")], ["| invalid-price (total_cost_usd is %s) |" % BP], "R0"),
    ("price-most-places-within-range", mk(close_changes={"cost_src": "result", "total_cost_usd": 1e-30}), basis("priced", "$0.00"), (), [],
     ["| priced $0.000000000000000000000000000001 |",
      "- priced closes, sum of the recorded values: $0.000000000000000000000000000001 (the main report rounds to the cent)"], "R0"),
    # A price with no cost_src beyond the range is no undeclared price but an invalid basis, as a
    # negative one is: the close could belong to any basis.
    ("undeclared-price-beyond-range", mk(close_changes={"total_cost_usd": E15}, close_drop=("cost_src",)), basis("invalid-basis"), (),
     [gl(CW, "total_cost_usd is %s with no cost_src" % BR, "Priced spend: closes")],
     ["| invalid-basis (total_cost_usd is %s with no cost_src) |" % BR], "R0"),
    ("plan-complete-input-beyond-range", mk(close_changes={"usage": {"input_tokens": E15, "output_tokens": 2, "calls": 1}}),
     plan_rows("complete", None, 2), (), [gl(CW, "usage.input_tokens is " + BR, "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input invalid (usage.input_tokens is %s), output 2 |" % BR], "R0"),
    ("plan-complete-output-beyond-range", mk(close_changes={"usage": {"input_tokens": 10, "output_tokens": E15, "calls": 1}}),
     plan_rows("complete", 10, None), (), [gl(CW, "usage.output_tokens is " + BR, "Priced spend: plan usage")],
     ["COV:Priced spend|plan usage closes (GPT-6 Astra, not priced)|complete 1, measured zero 0, incomplete 0, no usage reported 0, unknown 0, invalid 0",
      "| plan usage, complete; input 10, output invalid (usage.output_tokens is %s) |" % BR], "R0"),
    ("plan-historical-calls-beyond-range", mk(close_changes={"usage_complete": False, "usage": {"input_tokens": 10, "output_tokens": 2, "calls": E15}},
                                              close_drop=("usage_state",)),
     plan("invalid"), (), [gl(CW, "usage.calls is " + BR, "Priced spend: plan usage")],
     ["| plan usage, invalid (usage.calls is %s); input 10, output 2 |" % BR], "R0"),
    ("gate-run-spend-beyond-range", mk(gate_changes={"run_spend_usd": E15}), SS_UNK1, (), [gl(GW, "run_spend_usd is " + BR, SSP)],
     [GATE_SNAP + "invalid (run_spend_usd is %s)" % BR], "R0"),
    ("gate-run-spend-beyond-places", mk(gate_changes={"run_spend_usd": 1e-31}), SS_UNK1, (), [gl(GW, "run_spend_usd is " + BP, SSP)],
     [GATE_SNAP + "invalid (run_spend_usd is %s)" % BP], "R0"),
    ("idle-beyond-range", mk(boundary_changes={"idle_min": E15}), IDLE_SRC_UNK, (), [gl(BW, "idle_min is " + BR, "Phase boundaries")],
     ["ROW:Phase boundaries|recorded idle, idle_src transcript|unknown; known subtotal 0 min|unknown",
      "· idle_min 1000000000000000 (transcript) ·"], "R0"),
    ("idle-beyond-places", mk(boundary_changes={"idle_min": 1e-31}), IDLE_SRC_UNK, (), [gl(BW, "idle_min is " + BP, "Phase boundaries")],
     ["ROW:Phase boundaries|recorded idle, idle_src transcript|unknown; known subtotal 0 min|unknown",
      "· idle_min 1E-31 (transcript) ·"], "R0"),
    ("over-cap-beyond-range", mk(boundary_changes={"over_cap_reports": E15}),
     {(B, "over-cap reports"): ("unknown; known subtotal 0", "unknown", OVER_COV % "1 boundary")}, (),
     [gl(BW, "over_cap_reports is " + BR, "Phase boundaries")], ["· over_cap_reports 1000000000000000 ·"], "R0"),
    # A delta may be negative (a decrease); its magnitude is bounded all the same.
    ("rewrites-beyond-range", mk(boundary_changes={"rewrites": -E15}),
     {(B, "rewrites (deltas)"): ("unknown; known subtotal 0", "unknown", REW_COV % "1 boundary")}, (),
     [gl(BW, "rewrites is " + BR, "Phase boundaries")], ["· rewrites -1000000000000000 (cumulative 1) ·"], "R0"),
    ("rewrites-total-beyond-range", mk(boundary_changes={"rewrites_total": E15}), BS_UNK, (),
     [gl(BW, "rewrites_total is " + BR, "Phase boundaries: rewrites snapshots")],
     [BOUNDARY_SNAP + "invalid (rewrites_total is %s)" % BR], "R0"),
    ("head-fence-beyond-range", mk(boundary_changes={"head_denials": E15}), HEAD_UNK, (),
     [gl(BW, "head_denials is " + BR, "Refusals: head fence")], ["· head_denials 1000000000000000 (None) ·"], "R0"),
    ("summary-beyond-range", mk(boundary_changes={"denials": E15}), SUM_UNK, (),
     [gl(BW, "denials (the boundary's helper summary) is " + BR, "Refusals: boundary summary")], ["· denials 1000000000000000 ·"], "R0"),
    ("boundary-run-spend-beyond-range", mk(boundary_changes={"run_spend_usd": E15}), SS_UNK1, (),
     [gl(BW, "run_spend_usd is " + BR, SSP)], [BOUNDARY_SNAP + "invalid (run_spend_usd is %s)" % BR], "R0"),
    ("boundary-run-spend-beyond-places", mk(boundary_changes={"run_spend_usd": 1e-31}), SS_UNK1, (),
     [gl(BW, "run_spend_usd is " + BP, SSP)], [BOUNDARY_SNAP + "invalid (run_spend_usd is %s)" % BP], "R0"),
    ("beat-price-beyond-range", mk(extra=[dict(BEAT, total_cost_usd=E15)]),
     {SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 1, 0, GAPS0))}, (),
     [gl(BTW, "total_cost_usd is " + BR, "Priced spend: hold beats")],
     ["ROW:Priced spend|hold beats not priced|0|complete", "· cost_src result · total_cost_usd 1000000000000000"], "R0"),
    ("beat-price-beyond-places", mk(extra=[dict(BEAT, total_cost_usd=1e-31)]),
     {SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 1, 0, GAPS0))}, (),
     [gl(BTW, "total_cost_usd is " + BP, "Priced spend: hold beats")],
     ["ROW:Priced spend|hold beats not priced|0|complete", "· cost_src result · total_cost_usd 1E-31"], "R0"),
    ("run-close-spend-beyond-range", mk(extra=[dict(RUN_CLOSE, run_spend_usd=E15)]), SS_UNK2, (),
     [gl(RCW, "run_spend_usd is " + BR, SSP)], [SNAP + "invalid (run_spend_usd is %s)" % BR], "R0"),
    ("run-close-spend-beyond-places", mk(extra=[dict(RUN_CLOSE, run_spend_usd=1e-31)]), SS_UNK2, (),
     [gl(RCW, "run_spend_usd is " + BP, SSP)], [SNAP + "invalid (run_spend_usd is %s)" % BP], "R0"),
    ("plain-run-close-spend-beyond-range", mk(extra=[dict(PLAIN_CLOSE, spend_usd=E15)]), SS_UNK2, (),
     [gl(RCW, "spend_usd is " + BR, SSP)], [SNAP + "invalid (spend_usd is %s)" % BR], "R0"),
    ("plain-run-close-spend-beyond-places", mk(extra=[dict(PLAIN_CLOSE, spend_usd=1e-31)]), SS_UNK2, (),
     [gl(RCW, "spend_usd is " + BP, SSP)], [SNAP + "invalid (spend_usd is %s)" % BP], "R0"),
    ("head-exit-spent-beyond-range", mk(extra=[dict(HEAD_EXIT, spent_usd=E15)]), SS_UNK2, (),
     [gl(HXW, "spent_usd is " + BR, SSP)], [HEAD_SNAP + "invalid (spent_usd is %s)" % BR], "R0"),
    ("head-exit-spent-beyond-places", mk(extra=[dict(HEAD_EXIT, spent_usd=1e-31)]), SS_UNK2, (),
     [gl(HXW, "spent_usd is " + BP, SSP)], [HEAD_SNAP + "invalid (spent_usd is %s)" % BP], "R0"),
    # Route 1: a sum the decimal context cannot hold (Overflow past 10^999999): an idle time and a
    # beat's price of 1e999999999, each aborting the report in the B-WASTE12 version.
    ("idle-sum-overflow", mk(boundary_changes={"idle_min": Raw("1e999999999")}), IDLE_SRC_UNK, (),
     [gl(BW, "idle_min is " + BR, "Phase boundaries")],
     ["ROW:Phase boundaries|recorded idle, idle_src transcript|unknown; known subtotal 0 min|unknown",
      "· idle_min 1E+999999999 (transcript) ·"], "R1"),
    ("beat-price-sum-overflow", mk(extra=[dict(BEAT, total_cost_usd=Raw("1e999999999"))]),
     {SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 1, 0, GAPS0))}, (),
     [gl(BTW, "total_cost_usd is " + BR, "Priced spend: hold beats")],
     ["ROW:Priced spend|hold beats not priced|0|complete", "· cost_src result · total_cost_usd 1E+999999999"], "R1"),
    # Route 3: a recorded value rendered exactly whose exponent runs to 10^14 digits (MemoryError in
    # its fixed-point rendering): a duration and a zero price far below, a price with no basis far above.
    ("duration-exponent-far-below", mk(close_changes={"duration_s": Raw("1e-99999999999999")}), unk_duration(), (),
     [gl(CW, "duration_s is " + BP, "Helper time")], ["| invalid (duration_s is %s) |" % BP], "R3"),
    ("price-zero-exponent-far-below", mk(close_changes={"cost_src": "result", "total_cost_usd": Raw("0e-99999999999999")}),
     basis("invalid-price"), (), [gl(CW, "total_cost_usd is " + BP, "Priced spend: closes")],
     ["| invalid-price (total_cost_usd is %s) |" % BP], "R3"),
    ("undeclared-price-exponent-far-above", mk(close_changes={"total_cost_usd": Raw("1e99999999999999")}, close_drop=("cost_src",)),
     basis("invalid-basis"), (), [gl(CW, "total_cost_usd is %s with no cost_src" % BR, "Priced spend: closes")],
     ["| invalid-basis (total_cost_usd is %s with no cost_src) |" % BR], "R3"),
]

# CR-WASTE5 finding 2: a displayed figure is rounded once, from the exact value. A duration of
# 3.000000000000000000000000000006 s (31 digits, 30 places, within the range) is 0.0500000000000000000000000000001
# min exactly, more than half a tenth: 0.1 min. The B-WASTE14 version divided by 60 under the default
# context's 28 digits first, which made it exactly 0.05, a tie it rounded half-even to 0.0.
MINUTES_ONCE = "3.000000000000000000000000000006 s (0.1 min)"
T2_CASES += [
    ("minutes-rounded-once-from-the-exact-total", mk(close_changes={"duration_s": Raw("3.000000000000000000000000000006")}),
     dict([((H, "total"), (MINUTES_ONCE, "complete", ONE))] + list(views((MINUTES_ONCE, "complete", VIEW)).items())), (), [],
     ["+0100 | 3.000000000000000000000000000006 | completed |",
      "- (all): %s over 1 close (0 unknown or invalid; 0 named gaps (detail))" % MINUTES_ONCE], "C3"),
]


def t2_variant(ctx, name, events, changes, drop=(), gaps=(), needles=(), others=None):
    fx = Fx(ctx.root, "t2-" + name, script=ctx.script)
    fx.write("run-r.jsonl", events)
    for other, lines in (others or {}).items():
        fx.write(other, lines)
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d: %s" % (code, last_line(err)))
    got_rows = as_map(rows_of(main))
    for n in needles:
        if n.startswith("ROW:"):
            # A main-report row's value and status, its labels the same in earlier readers.
            fig_, part_, value_, status_ = n[4:].split("|")
            got = got_rows.get((fig_, part_), (None, None))[:2]
            expect(got == (value_, status_), "%s / %s: got %r, want %r" % (fig_, part_, got, (value_, status_)))
        elif n.startswith("COV:"):
            # A main-report row's coverage, its labels the same in earlier readers.
            fig_, part_, cov_ = n[4:].split("|", 2)
            got = got_rows.get((fig_, part_), (None, None, None))[2]
            expect(got == cov_, "%s / %s coverage: got %r, want %r" % (fig_, part_, got, cov_))
        else:
            expect(n in detail, "detail lacks: %s" % n)
    want = dict(BASE)
    for k in drop:
        want.pop(k)
    want.update(changes)
    e = compare_map(rows_of(main), want)
    expect(e is None, e)
    got_gaps = section(detail, "## Named gaps and the figures they affect")
    want_gaps = list(gaps) or ["- none"]
    expect(got_gaps == want_gaps, "named gaps:\n got  %s\n want %s" % ("\n      ".join(got_gaps), "\n      ".join(want_gaps)))


def _make_t2(spec):
    name, kw, ch, dr, gp, nd, tag = spec[:7]
    others = spec[7] if len(spec) > 7 else None
    # The tag: an int is a CR-WASTE1 finding; "F<n>" is CR-WASTE2's finding n; "G<n>" is CR-WASTE3's
    # finding n; "R<n>" is route n of B-WASTE13's fold (0: the reader's range, field by field); "C<n>" is
    # CR-WASTE5's finding n; a tuple holds several.
    tags = tag if isinstance(tag, tuple) else (tag,)
    cr1 = tuple(t for t in tags if isinstance(t, int))
    fold = tuple(int(t[1:]) for t in tags if isinstance(t, str) and t.startswith("F"))
    cr3 = tuple(int(t[1:]) for t in tags if isinstance(t, str) and t.startswith("G"))
    route = tuple(int(t[1:]) for t in tags if isinstance(t, str) and t.startswith("R"))
    cr5 = tuple(int(t[1:]) for t in tags if isinstance(t, str) and t.startswith("C"))

    @case(2, name, finding=fold, cr1=cr1, cr3=cr3, route=route, cr5=cr5)
    def _t(ctx):
        t2_variant(ctx, name, base_events(**kw), ch, dr, gp, nd, others)
    return _t


for _spec in T2_CASES:
    _make_t2(_spec)


# CR-WASTE3 finding 3: the explicit field and state matrix lives in FIELDS.md ("Field and state
# coverage"), one row per consumed field, one column per state; each cell names the cases that fix
# it, or says why the state does not arise. This case holds the matrix to the suite: the rows are
# exactly MATRIX_FIELDS, every cell is filled, every case it names exists, and every record field
# the reader reads (RECORD_FIELDS) has a row here or in the rendered-only table.
MATRIX_HEADING = "## Field and state coverage (test 2)"
MATRIX_COLUMNS = ["Field", "Zero", "Positive or a writer's value", "Absent", "Null or the writer's unknown", "Wrong type",
                  "Other invalid", "Not applicable"]
MATRIX_FIELDS = ["`lane-closed.duration_s`", "`lane-closed.exit_class`", "`class` (the close's, else the opening's)",
                 "`lane-closed.denials`", "`lane-closed.denials.tool`", "`lane-closed.denials.fence`",
                 "`lane-closed.denials.sandbox`", "`lane-closed.sandbox_denials`", "`lane-closed.fence_denials_transcript`",
                 "`lane-closed.cost_src`", "`lane-closed.total_cost_usd`", "`lane-closed.session_id`",
                 "`lane-closed.usage.modelUsage`", "`lane-closed.usage.modelUsage.*.costUSD`",
                 "`lane-closed.usage.modelUsage.*.inputTokens`", "`lane-closed.usage.modelUsage.*.outputTokens`",
                 "`lane-closed.usage.modelUsage.*.cacheReadInputTokens`",
                 "`lane-closed.usage.modelUsage.*.cacheCreationInputTokens`", "`lane-closed.usage`",
                 "`lane-closed.usage.input_tokens`", "`lane-closed.usage.output_tokens`", "`lane-closed.usage_state`",
                 "`lane-closed.usage_complete`", "`lane-closed.usage.calls`", "`gate.item`", "`gate.decision`",
                 "`gate.run_spend_usd`", "`phase-boundary.idle_min`", "`phase-boundary.idle_src`",
                 "`phase-boundary.over_cap_reports`", "`phase-boundary.rewrites`", "`phase-boundary.rewrites_total`",
                 "`phase-boundary.head_denials`", "`phase-boundary.denials`", "`phase-boundary.run_spend_usd`",
                 "`hold-beat.cost_src`", "`hold-beat.total_cost_usd`", "`hold-beat.session_id`", "`hold-beat.lane`",
                 "`hold-beat.usage.models`", "`hold-beat.usage.input_tokens`", "`hold-beat.usage.output_tokens`",
                 "`hold-beat.usage.cache_read_input_tokens`", "`hold-beat.usage.cache_creation_input_tokens`",
                 "`run-close.shape`", "`run-close.run_spend_usd`",
                 "`run-close.spend_usd`", "`head-exit.spent_usd`", "`event`", "`ts`", "`lane`"]
RENDERED_HEADING = "### Rendered as recorded, read into no figure"
# Every numeric field the reader sums, rounds or renders (FIELDS.md, "The reader's range"): each row's
# "Other invalid" cell must name a case of a value beyond the reader's range.
RANGE_FIELDS = ["`lane-closed.duration_s`", "`lane-closed.denials.tool`", "`lane-closed.denials.fence`",
                "`lane-closed.denials.sandbox`", "`lane-closed.sandbox_denials`", "`lane-closed.fence_denials_transcript`",
                "`lane-closed.total_cost_usd`", "`lane-closed.usage.modelUsage.*.costUSD`",
                "`lane-closed.usage.modelUsage.*.inputTokens`", "`lane-closed.usage.modelUsage.*.outputTokens`",
                "`lane-closed.usage.modelUsage.*.cacheReadInputTokens`",
                "`lane-closed.usage.modelUsage.*.cacheCreationInputTokens`",
                "`lane-closed.usage.input_tokens`", "`lane-closed.usage.output_tokens`",
                "`lane-closed.usage.calls`", "`gate.run_spend_usd`", "`phase-boundary.idle_min`",
                "`phase-boundary.over_cap_reports`", "`phase-boundary.rewrites`", "`phase-boundary.rewrites_total`",
                "`phase-boundary.head_denials`", "`phase-boundary.denials`", "`phase-boundary.run_spend_usd`",
                "`hold-beat.total_cost_usd`", "`hold-beat.usage.input_tokens`", "`hold-beat.usage.output_tokens`",
                "`hold-beat.usage.cache_read_input_tokens`", "`hold-beat.usage.cache_creation_input_tokens`",
                "`run-close.run_spend_usd`", "`run-close.spend_usd`", "`head-exit.spent_usd`"]


def md_table(text, heading):
    """The table under a heading: its header cells and its rows, as lists of stripped cells."""
    lines = text.split("\n")
    if heading not in lines:
        return None, []
    i = lines.index(heading) + 1
    while i < len(lines) and not lines[i].startswith("|"):
        i += 1
    rows = []
    while i < len(lines) and lines[i].startswith("|"):
        rows.append([c.strip() for c in lines[i].strip().strip("|").split(" | ")])
        i += 1
    return (rows[0], [r for r in rows[2:]]) if len(rows) >= 2 else (None, [])


@case(2, "field-state-matrix-complete", cr3=3)
def t2_matrix(ctx):
    fields = open(os.path.join(os.path.dirname(os.path.abspath(ctx.script)), "FIELDS.md"), encoding="utf-8").read()
    head, rows = md_table(fields, MATRIX_HEADING)
    expect(head == MATRIX_COLUMNS, "FIELDS.md has no field and state matrix with the columns %s (got %r)" % (MATRIX_COLUMNS, head))
    expect([r[0] for r in rows] == MATRIX_FIELDS, "matrix rows differ:\n%s" % first_difference([r[0] for r in rows], MATRIX_FIELDS))
    names = set(c[0] for c in CASES)
    cited = set()
    for r in rows:
        expect(len(r) == len(MATRIX_COLUMNS), "%s: %d cells" % (r[0], len(r)))
        for col, cell in zip(MATRIX_COLUMNS[1:], r[1:]):
            expect(cell, "%s / %s: an empty cell" % (r[0], col))
            if cell.startswith("does not arise: ") and len(cell) > len("does not arise: "):
                continue
            for c in cell.split(", "):
                expect(c in names, "%s / %s names no case of this suite: %r" % (r[0], col, c))
                cited.add(c)
    rhead, rrows = md_table(fields, RENDERED_HEADING)
    expect(rhead == ["Field", "Cases"] and rrows, "FIELDS.md has no rendered-only table")
    for r in rrows:
        for c in r[1].split(", "):
            expect(c in names, "%s names no case of this suite: %r" % (r[0], c))
    labels = [r[0] for r in rows + rrows]
    parts = set(p for l in labels for p in re.split(r"[`.,()\s]+", l) if p)
    expect(not [f for f in RECORD_FIELDS if f not in parts], "fields without a matrix row: %s" % [f for f in RECORD_FIELDS if f not in parts])
    # The reader's range covers every numeric field it consumes: each such row names a case beyond it.
    other = dict((r[0], r[MATRIX_COLUMNS.index("Other invalid")]) for r in rows)
    unranged = [f for f in RANGE_FIELDS if not [c for c in other.get(f, "").split(", ") if c.endswith("-beyond-range")]]
    # The previous 27 numeric fields plus the beat's four aggregate token counts.
    expect(len(RANGE_FIELDS) == 27 + 4 and not unranged, "numeric fields with no case beyond the reader's range: %s" % unranged)
    # Control: the cells name cases of every test that fixes a value (tests 1 to 4).
    expect(len(cited) >= 150 and set(c.split(".")[0] for c in cited) >= set(["T1", "T2", "T3", "T4"]),
           "PROBE FAILED: the matrix cites %d cases (control)" % len(cited))


@case(2, "interrupted-priced-plan-distinct")
def t2_distinct(ctx):
    # One priced close ($2.00), one unpriced watch close, one interrupted plan close
    # (incomplete 7/1) and one complete plan close (5/5): four bases, each on its own row.
    fx = Fx(ctx.root, "t2-distinct", script=ctx.script)
    base = {"exit_class": "completed", "duration_s": 10, "denials": {"tool": 0, "fence": 0, "sandbox": 0}, "sandbox_denials": 0, "class": "builder"}
    fx.write("run-r.jsonl", [
        {"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "A", "class": "builder"},
        dict(base, ts="2026-10-06T10:05:00+0100", event="lane-closed", lane="A", cost_src="result", total_cost_usd=2.0,
             session_id="s-A", usage=fixture_inventory(2.0)),
        {"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "W", "class": "builder"},
        dict(base, ts="2026-10-06T10:06:00+0100", event="lane-closed", lane="W", cost_src="transcript-estimate", total_cost_usd=None, exit_class="watch-closed"),
        {"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "I", "class": "builder", "harness": "codex"},
        dict(base, ts="2026-10-06T10:07:00+0100", event="lane-closed", lane="I", cost_src="codex-plan", total_cost_usd=None, exit_class="deadline",
             usage={"input_tokens": 7, "output_tokens": 1, "calls": 1}, usage_complete=False, usage_state="incomplete"),
        {"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "C", "class": "builder", "harness": "codex"},
        dict(base, ts="2026-10-06T10:08:00+0100", event="lane-closed", lane="C", cost_src="codex-plan", total_cost_usd=None,
             usage={"input_tokens": 5, "output_tokens": 5, "calls": 1}, usage_complete=True, usage_state="complete"),
    ])
    code, out, err, main, detail = fx.report()
    m = as_map(rows_of(main))
    expect(m[SP_T][0] == "$2.00", "priced %r" % (m[SP_T],))
    expect(m[SP_UN][0] == "1", "unpriced")
    expect(m[SP_TCI][:2] == ("5", "complete") and m[SP_TCO][:2] == ("5", "complete"), "complete tokens")
    expect(m[SP_TII][:2] == ("7", "incomplete") and m[SP_TIO][:2] == ("1", "incomplete"), "incomplete")


# The class "record content stops the report" (B-WASTE13's fold). Each route's fixture: the control
# episode K in run-ok.jsonl beside the planted record. K and every planted episode are completed
# builder closes of 60 s at 10:01 or later, opened at 10:00, priced $0.50 on the result basis, every
# refusal channel a measured zero, as in B-WASTE12's demonstration (evidence-B-WASTE12/proposed-range-
# demo.py), unless a case changes a field.

def priced_episode(lane, close_ts, **changes):
    close = {"ts": close_ts, "event": "lane-closed", "lane": lane, "class": "builder", "exit_class": "completed",
             "duration_s": 60, "cost_src": "result", "total_cost_usd": 0.5, "session_id": "s-%s" % (lane,),
             "denials": {"tool": 0, "fence": 0, "sandbox": 0}}
    close.update(changes)
    if "usage" not in changes:
        close["usage"] = fixture_inventory(close.get("total_cost_usd"))
    return [{"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": lane, "class": "builder"}, close]


def priced_rows(eps):
    """The full table for such closes and nothing else (no boundary, gate, beat, snapshot or plan
    close), fixed from the definitions: EPS lists each close's (run, lane), at most three, so every
    view row is shown. Each close adds 60 s and $0.50; nothing is unknown."""
    expect(len(eps) <= 3, "PROBE FAILED: priced_rows takes at most three closes")
    n = len(eps)
    secs = lambda k: "%d s (%d.0 min)" % (60 * k, k)
    cov = lambda k: "%s: 0 not applicable, 0 unknown or invalid; %s" % (pl(k, "close"), GAPS0)
    runs = {}
    for run, lane in eps:
        runs[run] = runs.get(run, 0) + 1
    ch = "%s: %d known, 0 not applicable, 0 unknown or invalid; %s" % (pl(n, "close"), n, GAPS0)
    out = {
        (H, "total"): (secs(n), "complete", "%s: %d timed, 0 not applicable, 0 unknown or invalid; %s" % (pl(n, "close"), n, GAPS0)),
        (H, "class builder"): (secs(n), "complete", cov(n)),
        (F, "closes"): (str(n), "complete", GAPS0),
        (F, "completed"): (str(n), "complete", "exit_class completed"),
        (F, "non-completed"): ("0", "complete", NONCOMP % (0, 0, GAPS0)),
        (F, "status unknown or invalid"): ("0", "complete", "no usable exit_class"),
        (F, "non-completed, later resumed"): ("0", "complete", LATER),
        (RV, "reviewing-class episodes"): ("0", "complete", RVC_COV % ("0 closes", GAPS0)),
        (RV, "evidenced item associations"): EVID[2:],
        (RV, "positional candidate groups"): ("0", "complete", GROUPS_COV % GAPS0),
        (RV, "reviewing-class episodes with no positional group"): ("0", "complete", NOGROUP_COV),
        (RV, "candidate groups with two or more reviewing-class episodes"): ("0", "complete", MULTI_COV),
        (RV, "rounds"): ROUNDS[2:],
        (B, "boundary events"): ("0", "complete", "counted at their own timestamps; " + GAPS0),
        (B, "recorded idle unknown"): ("0", "complete", IDLEU_COV),
        (B, "over-cap reports"): ("0", "complete", OVER_COV % "0 boundaries"),
        (B, "rewrites (deltas)"): ("0", "complete", REW_COV % "0 boundaries"),
        (B, "cumulative rewrites snapshots"): ("0", "complete", BS_COV % 0),
        (RF, "helper tool"): ("0", "complete", ch), (RF, "helper fence"): ("0", "complete", ch),
        (RF, "helper sandbox"): ("0", "complete", ch),
        (RF, "head fence (boundaries)"): ("0", "complete", HF_COV % ("0 boundaries", 0, GAPS0)),
        (RF, "boundary summary of helper tool refusals"): ("0", "complete", HS_COV % ("0 boundaries", GAPS0)),
        SP_T: ("$%d.%02d" % (n // 2, 50 * (n % 2)), "complete", PRICED_COV % (pl(n, "priced close"), "0 priced hold beats", 0, 0, 0, 0, GAPS0)),
        SP_PC: ("0", "complete", PLAN_COV % (0, 0, 0, 0, 0, 0)),
        SP_TCI: tok(0, 0, 0, tc(0)), SP_TCO: tok(0, 0, 0, tc(0)), SP_TII: tok(0, 0, 0, ti(0)), SP_TIO: tok(0, 0, 0, ti(0)),
        SP_UN: ("0", "complete", "token totals only; no dollar figure"),
        SP_NA: ("0", "complete", "exit_class spawn-failed"),
        SP_HB: ("0", "complete", "plan usage or no process"),
        SP_SS: ("0", "complete", SS_COV % 0),
    }
    for run, k in runs.items():
        out[(H, "run " + run)] = (secs(k), "complete", cov(k))
    for run, lane in eps:
        out[(H, "helper %s/%s" % (run, lane))] = (secs(1), "complete", VIEW)
    return out


def route_run(ctx, name, planted, store_lines=()):
    """Write the control and the planted records (and any store lines after init's), run the report,
    and require it to complete: both files written, never an abort."""
    fx = Fx(ctx.root, name, script=ctx.script)
    fx.write("run-ok.jsonl", priced_episode("K", "2026-10-06T10:01:00+0100"))
    for rec, lines in planted:
        fx.write(rec, lines)
    if store_lines:
        with open(os.path.join(fx.tools, "dispositions.jsonl"), "a", encoding="utf-8") as h:
            for line in store_lines:
                h.write(line + "\n")
    code, out, err, main, detail = fx.report()
    expect(main is not None and detail is not None,
           "exit %d, report written %s, detail written %s: %s" % (code, main is not None, detail is not None, last_line(err)))
    return code, main, detail


def expect_table_and_gaps(main, detail, want, gaps):
    e = compare_map(rows_of(main), want)
    expect(e is None, e)
    got = section(detail, "## Named gaps and the figures they affect")
    expect(got == (list(gaps) or ["- none"]), "named gaps:\n got  %s\n want %s" % ("\n      ".join(got), "\n      ".join(gaps)))


def demo_case(ctx, name, rec, changes, figure_rows, gap, cell):
    # B-WASTE12's demonstration as a case: one value planted on the episode X of REC beside the control.
    code, main, detail = route_run(ctx, name, [(rec, priced_episode("X", "2026-10-06T10:30:00+0100", **changes))])
    expect(code == 0, "exit %d" % code)
    want = priced_rows([("run-ok", "K"), (rec[:-len(".jsonl")], "X")])
    want.update(figure_rows)
    expect_table_and_gaps(main, detail, want, [gap])
    expect(cell in detail, "detail lacks: %s" % cell)
    expect("- Records holding invalid or undated lines: 0, each named in the detail in every report until mended." in main,
           "a value beyond the range is a value, not a bad line")


def helper_unknown(run):
    """Helper time when the planted close's duration is invalid: K's 60 s known, X's unknown."""
    one = "1 close: 0 not applicable, 1 unknown or invalid; " + GAPS0
    return {(H, "total"): ("unknown; known subtotal 60 s (1.0 min)", "unknown", "2 closes: 1 timed, 0 not applicable, 1 unknown or invalid; " + GAPS0),
            (H, "run " + run): ("unknown; known subtotal 0 s (0.0 min)", "unknown", one),
            (H, "class builder"): ("unknown; known subtotal 60 s (1.0 min)", "unknown", "2 closes: 0 not applicable, 1 unknown or invalid; " + GAPS0),
            (H, "helper %s/X" % run): ("unknown; known subtotal 0 s (0.0 min)", "unknown", one)}


@case(2, "demo-duration-1e30-rounding", route=2)
def t2_demo_a(ctx):
    # Demonstration (a): a duration of 1e30 s. Its minutes, 1.67e28, cannot round to 0.1 within the
    # context's 28 digits (InvalidOperation in the B-WASTE12 version, no report written). Now invalid
    # and named: helper time unknown with K's 60 s kept; the priced total ($1.00) complete.
    demo_case(ctx, "demo-a", "run-x.jsonl", {"duration_s": Raw("1e30")}, helper_unknown("run-x"),
              '- run-x.jsonl:2 "X" · 2026-10-06 10:30:00 +0100 · duration_s is %s · affects: Helper time' % BR,
              "| invalid (duration_s is %s) |" % BR)


@case(2, "demo-price-1e27-rounding", route=2)
def t2_demo_b(ctx):
    # Demonstration (b): a result price of $1e27, which cannot round to the cent within 28 digits.
    # Now invalid and named: the priced total unknown with K's $0.50 kept; helper time complete.
    demo_case(ctx, "demo-b", "run-y.jsonl", {"total_cost_usd": Raw("1e27")},
              {SP_T: ("unknown; known subtotal $0.50", "unknown", PRICED_COV % ("1 priced close", "0 priced hold beats", 0, 0, 1, 0, GAPS0))},
              '- run-y.jsonl:2 "X" · 2026-10-06 10:30:00 +0100 · total_cost_usd is %s · affects: Priced spend: closes' % BR,
              "| invalid-price (total_cost_usd is %s) |" % BR)


@case(2, "demo-duration-1e999999999-overflow", route=1)
def t2_demo_c(ctx):
    # Demonstration (c): a duration of 1e999999999 s, whose sum overflows the context (Overflow past
    # 10^999999 in the B-WASTE12 version). Now invalid and named, as (a).
    demo_case(ctx, "demo-c", "run-z.jsonl", {"duration_s": Raw("1e999999999")}, helper_unknown("run-z"),
              '- run-z.jsonl:2 "X" · 2026-10-06 10:30:00 +0100 · duration_s is %s · affects: Helper time' % BR,
              "| invalid (duration_s is %s) |" % BR)


@case(2, "summed-counts-past-the-string-limit", route=4)
def t2_int_limit(ctx):
    # Route 4: two closes, X and Y in run-x, each recording 4,300 nines as its tool refusals. Their sum
    # has 4,301 digits, which Python 3.11 and later refuse to turn into text (ValueError in the
    # B-WASTE12 version, no report). Now each value is beyond the range, named on its own close: the
    # tool channel unknown with K's 0 kept; fence and sandbox complete over 3 closes.
    big = int("9" * 4300)
    code, main, detail = route_run(ctx, "int-limit", [("run-x.jsonl",
        priced_episode("X", "2026-10-06T10:30:00+0100", denials={"tool": big, "fence": 0, "sandbox": 0})
        + priced_episode("Y", "2026-10-06T10:31:00+0100", denials={"tool": big, "fence": 0, "sandbox": 0}))])
    expect(code == 0, "exit %d" % code)
    want = priced_rows([("run-ok", "K"), ("run-x", "X"), ("run-x", "Y")])
    want[(RF, "helper tool")] = ("unknown; known subtotal 0", "unknown", "3 closes: 1 known, 0 not applicable, 2 unknown or invalid; " + GAPS0)
    expect_table_and_gaps(main, detail, want, [
        '- run-x.jsonl:2 "X" · 2026-10-06 10:30:00 +0100 · denials.tool is %s · affects: Refusals: helper tool' % BR,
        '- run-x.jsonl:4 "Y" · 2026-10-06 10:31:00 +0100 · denials.tool is %s · affects: Refusals: helper tool' % BR])


# CR-WASTE5 finding 1 (B-WASTE15's fold): no recorded string is read as one of the reader's labels. The
# review's own two lines: an otherwise ordinary episode L whose class is "(builder)" (a non-blank string,
# so a usable class), priced $0 on the result basis. The B-WASTE14 version read every class beginning
# with "(" as one of its labels for an unusable class and named a gap with no reason, whose grouping
# raised AttributeError before either report was written.
REVIEW_EXAMPLE = [
    '{"ts":"2026-10-06T10:00:00+0100","event":"lane-open","lane":"L","class":"(builder)"}',
    '{"ts":"2026-10-06T10:01:00+0100","event":"lane-closed","lane":"L","class":"(builder)","duration_s":60,'
    '"exit_class":"completed","cost_src":"result","total_cost_usd":0,"session_id":"s-L",'
    '"usage":{"modelUsage":{"opus":{"costUSD":0,"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0}}},'
    '"denials":{"tool":0,"fence":0,"sandbox":0}}']


@case(2, "priced-closes-summed-exactly", cr5=3)
def t2_priced_exact(ctx):
    # CR-WASTE5 finding 2's counterexample: result-priced closes A at $0.025 and B at $1e-30, each within the
    # range. Their exact sum is 0.025000000000000000000000000001 (30 places), strictly above $0.025, so half-even
    # to the cent it is $0.03; the detail keeps the exact sum. The B-WASTE14 version summed under the default
    # 28-digit context, lost the second price and printed $0.02 and an "exact" $0.025. A second fixture puts
    # the $1e-30 on a priced hold beat instead: the closes' and beats' totals add exactly too, $0.03, while the
    # detail's exact sum of the closes alone is $0.025.
    code, main, detail = route_run(ctx, "priced-exact", [("run-p.jsonl", priced_episode("A", "2026-10-06T10:30:00+0100", total_cost_usd=Raw("0.025"))
                                                           + priced_episode("B", "2026-10-06T10:31:00+0100", total_cost_usd=Raw("1e-30")))])
    expect(code == 0, "exit %d" % code)
    want = priced_rows([("run-ok", "K"), ("run-p", "A"), ("run-p", "B")])
    # K's $0.50 + $0.025 + $1e-30 = $0.525000000000000000000000000001: half-even to the cent, $0.53.
    want[SP_T] = ("$0.53", "complete", PRICED_COV % ("3 priced closes", "0 priced hold beats", 0, 0, 0, 0, GAPS0))
    expect_table_and_gaps(main, detail, want, [])
    for needle in ("| priced $0.025 |", "| priced $0.000000000000000000000000000001 |",
                   "- priced closes, sum of the recorded values: $0.525000000000000000000000000001 (the main report rounds to the cent)"):
        expect(needle in detail, "detail lacks: %s" % needle)
    fx = Fx(ctx.root, "priced-exact-alone", script=ctx.script)
    fx.write("run-p.jsonl", priced_episode("A", "2026-10-06T10:30:00+0100", total_cost_usd=Raw("0.025"))
             + priced_episode("B", "2026-10-06T10:31:00+0100", total_cost_usd=Raw("1e-30")))
    code, out, err, main, detail = fx.report()
    expect(code == 0, "the two closes alone: exit %d" % code)
    want = priced_rows([("run-p", "A"), ("run-p", "B")])
    want[SP_T] = ("$0.03", "complete", PRICED_COV % ("2 priced closes", "0 priced hold beats", 0, 0, 0, 0, GAPS0))
    expect_table_and_gaps(main, detail, want, [])
    expect("- priced closes, sum of the recorded values: $0.025000000000000000000000000001 (the main report rounds to the cent)"
           in detail, "the two closes' exact sum")
    fx = Fx(ctx.root, "priced-exact-beat", script=ctx.script)
    fx.write("run-q.jsonl", priced_episode("A", "2026-10-06T10:30:00+0100", total_cost_usd=Raw("0.025"))
             + [{"ts": "2026-10-06T10:35:00+0100", "event": "hold-beat", "lane": "A", "session_id": "s-A-hold", "cost_src": "result",
                 "total_cost_usd": Raw("1e-30"), "usage": fixture_beat_usage()}])
    code, out, err, main, detail = fx.report()
    expect(code == 0, "the beat: exit %d" % code)
    want = priced_rows([("run-q", "A")])
    want[SP_T] = ("$0.03", "complete", PRICED_COV % ("1 priced close", "1 priced hold beat", 0, 0, 0, 0, GAPS0))
    expect_table_and_gaps(main, detail, want, [])
    for needle in ("- priced closes, sum of the recorded values: $0.025 (the main report rounds to the cent)",
                   "- run-q.jsonl:3 · 2026-10-06 10:35:00 +0100 · cost_src result · total_cost_usd 1E-30"):
        expect(needle in detail, "detail lacks: %s" % needle)


# ------------------------------------------------------------------------ priced spend by session ----
# A result-basis line's total_cost_usd is what the harness that wrote it reported, and the records show two
# readings (FIELDS.md, "Priced spend"): from 19 September 2026 a running total of the helper's session (a resumed
# session's later close repeats each earlier pass's cost, a one-off model's entry in usage.modelUsage carried over
# unchanged), before then each pass's own cost (a one-off model's entry dropped from the next close). Each session
# (a record, a helper and a session id) is read from its own lines: as running totals it counts its last total
# before the interval's end less its last before the start (none: zero), as per-pass costs the sum of its costs in
# the interval, and as neither its spend is unknown, named, never guessed. A session of one line counts its total,
# which either reading gives. A line naming no session is unknown (CR-WW1 finding 3). Every value below is fixed by
# hand from those rules, its arithmetic beside it; the interval is [2026-10-05, 2026-10-12), local time, half-open.
SESSION_ABSENT = object()       # a field a session fixture line leaves out
SESSION_DENIALS = {"tool": 0, "fence": 0, "sandbox": 0}
SESSION_ROW = ("- priced spend as the main report counts it, by session: %s over %s: a session read as running totals "
               "counts its last total before the interval's end less its last before the start, a per-pass session the "
               "sum of its costs in the interval, a session of one line its total (the main report rounds to the cent)")
SESSION_READ = ("- sessions with a line in the interval, by how their totals read: %d as running totals, %d as per-pass "
                "costs, %d as neither, %d of one result-basis line before the interval's end")
SESSION_LISTED = "- sessions with a line in the interval and more than one session line before its end, each below: %d"
NEITHER = ": its totals read neither as running totals nor as per-pass costs, so its spend in the interval is unknown"
NEITHER_NONE = "no model's entry is carried over unchanged to a later close and none is dropped from a close or beat" + NEITHER
NO_DROP = ", and no model's cost is dropped from a later close or beat"
LOST_TAIL = (" could be one of the session's lines before the interval's end and cannot be read into it, so its "
             "spend in the interval is unknown")
LOST_GROUP = "a session line before the interval's end cannot be read into it, so its spend is unknown"
NO_SESSION = "%s is %s: the line names no session, so its spend in the interval is unknown"
CARRY = "running totals (model %s's entry is carried over unchanged from line %d to line %d)"
DROP = "per-pass costs (model %s, at $%s on line %d, is dropped from usage.modelUsage at line %d)"
COUNT_FIELDS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")


def entry(cost, **counts):
    """One model's entry in usage.modelUsage as the harness writes it: its four token counts (10, 20, 30 and 40
    unless given; SESSION_ABSENT leaves one out) and its costUSD as written (SESSION_ABSENT leaves it out)."""
    out = {}
    for field, n in zip(COUNT_FIELDS, (10, 20, 30, 40)):
        v = counts.get(field, n)
        if v is not SESSION_ABSENT:
            out[field] = v
    if cost is not SESSION_ABSENT:
        out["costUSD"] = cost
    return out


def mu(**costs):
    """A close's usage.modelUsage: each model's entry (entry) with its costUSD as written; a dict replaces the entry
    whole. An entry repeated with the same cost repeats every count too, so it is carried over unchanged."""
    return dict((model, cost if isinstance(cost, dict) else entry(cost)) for model, cost in costs.items())


def claude_pass(lane, open_ts, close_ts, total, sid="s", opening="lane-open", models=SESSION_ABSENT, usage=SESSION_ABSENT, **close):
    """One pass of a Claude helper as lane.py writes it: its opening and its result-priced close, each naming
    SID (SESSION_ABSENT leaves session_id out), the close carrying MODELS as usage.modelUsage (or USAGE whole),
    and CLOSE's fields over the ordinary ones (SESSION_ABSENT leaves one out)."""
    op = {"ts": open_ts, "event": opening, "lane": lane, "class": "builder"}
    cl = {"ts": close_ts, "event": "lane-closed", "lane": lane, "class": "builder", "exit_class": "completed",
          "duration_s": 60, "cost_src": "result", "total_cost_usd": total, "denials": dict(SESSION_DENIALS)}
    if sid is not SESSION_ABSENT:
        op["session_id"] = cl["session_id"] = sid
    if models is SESSION_ABSENT:
        cl["usage"] = fixture_inventory(total)
    elif models is not None:
        cl["usage"] = {"modelUsage": models, "calls": 1}
    if usage is not SESSION_ABSENT:
        cl["usage"] = usage
    for key, value in close.items():
        if value is SESSION_ABSENT:
            cl.pop(key, None)
        else:
            cl[key] = value
    return [op, cl]


def session_beat(ts, total, lane="R", sid="s-r"):
    """A held-lane beat as lane.py writes it (its usage and keep-awake fields aside): SESSION_ABSENT leaves the
    lane or the session id out."""
    beat = {"ts": ts, "event": "hold-beat", "harness": "claude", "cost_src": "result", "total_cost_usd": total,
            "usage": fixture_beat_usage()}
    if lane is not SESSION_ABSENT:
        beat["lane"] = lane
    if sid is not SESSION_ABSENT:
        beat["session_id"] = sid
    return beat


def session_run(ctx, name, lines, want, gaps=(), detail_lines=(), main_lines=(), since=SINCE, until=UNTIL, fx=None):
    """Write run-s.jsonl (unless FX is given, already written), run the report, and hold the priced total's row to
    the hand-fixed value and status first, then its coverage, the named gaps (in the detail's order) and the given
    whole lines of the detail and the main report."""
    if fx is None:
        fx = Fx(ctx.root, "session-" + name, script=ctx.script)
        fx.write("run-s.jsonl", lines)
    code, out, err, main, detail = fx.report(since=since, until=until)
    expect(code == 0 and main is not None and detail is not None, "exit %d: %s" % (code, last_line(err)))
    got = as_map(rows_of(main)).get(SP_T)
    expect(got is not None and got[:2] == want[:2], "priced total's value and status:\n got  %r\n want %r" % (
        got and got[:2], want[:2]))
    expect(got == want, "priced total:\n got  %r\n want %r" % (got, want))
    got_gaps = section(detail, "## Named gaps and the figures they affect")
    want_gaps = list(gaps) or ["- none"]
    expect(got_gaps == want_gaps, "named gaps:\n got  %s\n want %s" % ("\n      ".join(got_gaps), "\n      ".join(want_gaps)))
    for line in detail_lines:
        expect(line in detail.split("\n"), "detail lacks: %s" % line)
    for line in main_lines:
        expect(line in main.split("\n"), "main report lacks: %s" % line)
    return main, detail


def session_line(lane, sid, totals, read, before, counted):
    return "- run-s.jsonl · helper %s · session %s · totals: %s · read as %s · before the start: %s · counted: %s" % (
        json.dumps(lane), json.dumps(sid), ", ".join("line %d %s" % t for t in totals), read, before, counted)


def carry(model, a, b):
    return CARRY % (json.dumps(model), a, b)


@case(2, "session-running-totals")
def t2_session_running_totals(ctx):
    # run-s.jsonl, its lines numbered as written; haiku's one-off $0.10 entry is carried over unchanged in each
    # resumed session (entry: the same cost and counts), and opus rises, so each reads as running totals:
    #   S, session s-s, straddles the start: line 2 closes at 2026-10-04 23:00 with $3.00 (before the interval),
    #     resumed, line 4 closes inside with $5.50: counted 5.50 - 3.00 = $2.50.
    #   R, session s-r, three passes inside, each close a running total that rises: lines 6, 8, 11 at $1.00,
    #     $2.50, $4.25 (opus 0.90, 2.40, 4.15; haiku 0.10), and a priced beat on the resumed session at line 9,
    #     $2.60, joining the same sequence: counted its last total, $4.25.
    #   T, two session ids: t-1 closes once at line 13 ($1.20), a session of one line; a fresh spawn under t-2
    #     closes at line 15 ($0.80) and, resumed, at line 17 ($2.00): counted 1.20 + 2.00 = $3.20.
    #   U, session s-u: line 19, $0.50, one line.
    # Total 2.50 + 4.25 + 3.20 + 0.50 = $10.45 over 5 sessions (S, R, t-1, t-2, U): 3 read as running totals, 2
    # of one line; 8 priced closes inside (S's line 4, R's 6, 8, 11, T's 13, 15, 17, U's 19) and 1 priced beat.
    # Summing every priced line instead gives 5.50 + 1.00 + 2.50 + 4.25 + 1.20 + 0.80 + 2.00 + 0.50 = 17.75 for
    # the closes (the detail's sum of the recorded values, kept) and $20.35 with the beat.
    lines = (claude_pass("S", "2026-10-04T22:00:00+0100", "2026-10-04T23:00:00+0100", Raw("3.00"), sid="s-s",
                         models=mu(opus=Raw("2.90"), haiku=Raw("0.10")))
             + claude_pass("S", "2026-10-05T09:00:00+0100", "2026-10-05T10:00:00+0100", Raw("5.50"), sid="s-s", opening="lane-resumed",
                           models=mu(opus=Raw("5.40"), haiku=Raw("0.10")))
             + claude_pass("R", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("1.00"), sid="s-r",
                           models=mu(opus=Raw("0.90"), haiku=Raw("0.10")))
             + claude_pass("R", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", Raw("2.50"), sid="s-r", opening="lane-resumed",
                           models=mu(opus=Raw("2.40"), haiku=Raw("0.10")))
             + [session_beat("2026-10-06T10:35:00+0100", Raw("2.60"))]
             + claude_pass("R", "2026-10-06T10:40:00+0100", "2026-10-06T10:50:00+0100", Raw("4.25"), sid="s-r", opening="lane-resumed",
                           models=mu(opus=Raw("4.15"), haiku=Raw("0.10")))
             + claude_pass("T", "2026-10-07T10:00:00+0100", "2026-10-07T10:30:00+0100", Raw("1.20"), sid="t-1")
             + claude_pass("T", "2026-10-07T11:00:00+0100", "2026-10-07T11:30:00+0100", Raw("0.80"), sid="t-2",
                           models=mu(opus=Raw("0.70"), haiku=Raw("0.10")))
             + claude_pass("T", "2026-10-07T12:00:00+0100", "2026-10-07T12:30:00+0100", Raw("2.00"), sid="t-2", opening="lane-resumed",
                           models=mu(opus=Raw("1.90"), haiku=Raw("0.10")))
             + claude_pass("U", "2026-10-08T10:00:00+0100", "2026-10-08T10:10:00+0100", Raw("0.50"), sid="s-u"))
    session_run(ctx, "running-totals", lines,
                ("$10.45", "complete", PRICED_COV % ("8 priced closes", "1 priced hold beat", 0, 0, 0, 0, GAPS0)),
                detail_lines=[
                    "- priced closes, sum of the recorded values: $17.75 (the main report rounds to the cent)",
                    SESSION_ROW % ("$10.45", "5 sessions"), SESSION_READ % (3, 0, 0, 2), SESSION_LISTED % 3,
                    session_line("S", "s-s", [(2, "$3.00"), (4, "$5.50")], carry("haiku", 2, 4), "line 2", "$2.50"),
                    session_line("R", "s-r", [(6, "$1.00"), (8, "$2.50"), (9, "$2.60"), (11, "$4.25")], carry("haiku", 6, 8),
                                 "none", "$4.25"),
                    session_line("T", "t-2", [(15, "$0.80"), (17, "$2.00")], carry("haiku", 15, 17), "none", "$2.00")])


def session_case(name, lines, want, gaps=(), detail_lines=(), main_lines=()):
    @case(2, name)
    def _t(ctx):
        session_run(ctx, name, lines, want, gaps, detail_lines, main_lines)
    return _t


def session_integrity_case(name, lines, reason):
    """Loss or unusable evidence makes the entire session unknown; U remains an independent control."""
    @case(2, name)
    def _t(ctx):
        planted = [line for line in lines if not isinstance(line, dict) or line.get("lane") != "U"]
        ww2_probe(ctx, name, planted, "unknown; known subtotal $0.50", "unknown", gap_fragment=reason)
    return _t


# A control beside each defect: U's own $0.50 (session s-u, one line), counted whatever happens to the other session.
U_CONTROL = claude_pass("U", "2026-10-08T10:00:00+0100", "2026-10-08T10:10:00+0100", Raw("0.50"), sid="s-u")


def session_priced(n_closes, n_beats=0, missing=0, invalid=0, unclassified=0):
    return PRICED_COV % (pl(n_closes, "priced close"), pl(n_beats, "priced hold beat"), missing, 0, invalid, unclassified, GAPS0)


def sgl(line, lane, at, reason, part="Priced spend: closes"):
    """A named gap of run-s.jsonl at LINE (a close of LANE, or a beat when LANE is None), timed AT."""
    return gl("run-s.jsonl:%d%s · %s" % (line, "" if lane is None else " " + json.dumps(lane), at), reason, part)


# A total that falls is no running total, and with no model dropped it is not shown to be per-pass costs either
# (a record damaged, or a session that spans the harness's change, would read the same): P closes at $6.33, $7.77
# and $1.84 (lines 2, 4, 6), no usage.modelUsage. Its spend is unknown, named, counted unclassified; known
# subtotal U's $0.50; 4 priced closes.
FALL_REASON = "its total falls from $7.77 at line 4 to $1.84 at line 6" + NO_DROP + NEITHER
session_case("session-total-falls",
             claude_pass("P", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("6.33"), sid="p")
             + claude_pass("P", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", Raw("7.77"), sid="p", opening="lane-resumed")
             + claude_pass("P", "2026-10-06T10:40:00+0100", "2026-10-06T10:50:00+0100", Raw("1.84"), sid="p", opening="lane-resumed")
             + U_CONTROL,
             ("unknown; known subtotal $0.50", "unknown", session_priced(4, unclassified=1)),
             [sgl(6, "P", "2026-10-06 10:50:00 +0100", FALL_REASON)],
             [session_line("P", "p", [(2, "$6.33"), (4, "$7.77"), (6, "$1.84")], "neither", "none", "unknown (%s)" % FALL_REASON)],
             ["  - its total falls from $… at line N to $… at line N" + NO_DROP + NEITHER + ": 1 (affects Priced spend)"])
# A total that rises while a model's cost falls reads as neither too: M's totals $7.80 then $9.06, opus $7.00 then
# $6.00 (haiku $0.80 then $3.06). Known subtotal $0.50; 3 priced closes, 1 unclassified.
MODEL_FALL = "model \"opus\"'s costUSD falls from $7.00 at line 2 to $6.00 at line 4" + NO_DROP + NEITHER
session_case("session-model-cost-falls",
             claude_pass("M", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("7.80"), sid="m",
                         models=mu(opus=Raw("7.00"), haiku=Raw("0.80")))
             + claude_pass("M", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", Raw("9.06"), sid="m", opening="lane-resumed",
                           models=mu(opus=Raw("6.00"), haiku=Raw("3.06")))
             + U_CONTROL,
             ("unknown; known subtotal $0.50", "unknown", session_priced(3, unclassified=1)),
             [sgl(4, "M", "2026-10-06 10:30:00 +0100", MODEL_FALL)])
# CR-WW1 finding 1: a model dropped from a later close is the per-pass records' own mark (each pass lists only the
# models it used; a running total carries every entry over), so the session's costs are summed: M $2.00 (opus
# 1.50, haiku 0.50) then $3.00 (opus 3.00, haiku gone): 2.00 + 3.00 = $5.00, with U's $0.50, $5.50, complete. The
# fold before this one named it unknown, and subtracting would give $3.00.
session_case("session-per-pass-summed",
             claude_pass("M", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("2.00"), sid="m",
                         models=mu(opus=Raw("1.50"), haiku=Raw("0.50")))
             + claude_pass("M", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", Raw("3.00"), sid="m", opening="lane-resumed",
                           models=mu(opus=Raw("3.00")))
             + U_CONTROL,
             ("$5.50", "complete", session_priced(3)), (),
             [SESSION_ROW % ("$5.50", "2 sessions"), SESSION_READ % (0, 1, 0, 1),
              session_line("M", "m", [(2, "$2.00"), (4, "$3.00")], DROP % ('"haiku"', "0.50", 2, 4), "none", "$5.00")])
# A per-pass session that straddles the start counts only its costs inside: M closes at 2026-10-04 23:00 with $6.00
# (opus 5.90, haiku 0.10), then, resumed, inside with $2.00 (opus alone): $2.00, never 2.00 - 6.00 and never 8.00;
# with U, $2.50, complete.
session_case("session-per-pass-straddles-the-start",
             claude_pass("M", "2026-10-04T22:00:00+0100", "2026-10-04T23:00:00+0100", Raw("6.00"), sid="m",
                         models=mu(opus=Raw("5.90"), haiku=Raw("0.10")))
             + claude_pass("M", "2026-10-05T09:00:00+0100", "2026-10-05T10:00:00+0100", Raw("2.00"), sid="m", opening="lane-resumed",
                           models=mu(opus=Raw("2.00")))
             + U_CONTROL,
             ("$2.50", "complete", session_priced(2)), (),
             [session_line("M", "m", [(2, "$6.00"), (4, "$2.00")], DROP % ('"haiku"', "0.10", 2, 4), "line 2", "$2.00")])
# CR-WW1 finding 1, the records' own case (12 September 2026, its numbers kept, its times moved to this interval): a
# session of one model whose every measure rises and none repeats, beside a close with no price and no
# usage.modelUsage. Both readings fit it: as running totals it spent 1.392443 - 0.58968125 = $0.80 inside, as
# per-pass costs $1.39 (the transcript's own counts, which no reader can tell the meaning of, side with the second).
# Its spend is unknown, named, counted unclassified: known subtotal U's $0.50. The fold before this one counted
# $0.80, complete.
C_FIRST = {"costUSD": Raw("0.58968125"), "inputTokens": 2, "outputTokens": 8827, "cacheReadInputTokens": 147245,
           "cacheCreationInputTokens": 5575}
C_SECOND = {"costUSD": Raw("1.392443"), "inputTokens": 98, "outputTokens": 12032, "cacheReadInputTokens": 671612,
            "cacheCreationInputTokens": 31098}
session_integrity_case("session-neither-reading-unknown", claude_pass("C", "2026-10-04T22:00:00+0100", "2026-10-04T22:20:00+0100", None, sid="c",
                         usage={"modelUsage": None, "calls": 6}, exit_class="deadline")
             + claude_pass("C", "2026-10-04T22:24:00+0100", "2026-10-04T22:26:00+0100", Raw("0.58968125"), sid="c",
                           opening="lane-resumed", models={"fable": C_FIRST})
             + claude_pass("C", "2026-10-05T00:31:00+0100", "2026-10-05T00:33:00+0100", Raw("1.392443"), sid="c",
                           opening="lane-resumed", models={"fable": C_SECOND})
             + U_CONTROL, 'no usable result price')
# A model carried over unchanged beside one dropped: no single reading fits, so neither. M $1.20 (opus 1.00, haiku
# 0.10, k 0.10) then $2.10 (opus 2.00, haiku 0.10; k gone).
CARRY_DROP = ("model \"haiku\"'s entry is carried over unchanged from line 2 to line 4, but model \"k\", at $0.10 on "
              "line 2, is dropped from usage.modelUsage at line 4" + NEITHER)
session_case("session-carried-beside-dropped",
             claude_pass("M", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("1.20"), sid="m",
                         models=mu(opus=Raw("1.00"), haiku=Raw("0.10"), k=Raw("0.10")))
             + claude_pass("M", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", Raw("2.10"), sid="m", opening="lane-resumed",
                           models=mu(opus=Raw("2.00"), haiku=Raw("0.10")))
             + U_CONTROL,
             ("unknown; known subtotal $0.50", "unknown", session_priced(3, unclassified=1)),
             [sgl(4, "M", "2026-10-06 10:30:00 +0100", CARRY_DROP)])
# A session read as running totals whose last line before the start has no price: what it spent inside cannot be
# told from its $4.00, so it is unknown, counted missing. B's line 2 ($1.00) and line 6 ($4.00) carry haiku over,
# line 4 (2026-10-04 23:00) has a null price. Known subtotal $0.50.
BASE_REASON = ("line 4 has no usable result price (total_cost_usd is null on a result-priced close), "
               "so its session's spend is unknown")
session_case("session-baseline-unknown",
             claude_pass("B", "2026-10-04T20:00:00+0100", "2026-10-04T21:00:00+0100", Raw("1.00"), sid="b",
                         models=mu(opus=Raw("0.90"), haiku=Raw("0.10")))
             + claude_pass("B", "2026-10-04T22:00:00+0100", "2026-10-04T23:00:00+0100", None, sid="b", opening="lane-resumed")
             + claude_pass("B", "2026-10-05T09:00:00+0100", "2026-10-05T10:00:00+0100", Raw("4.00"), sid="b", opening="lane-resumed",
                           models=mu(opus=Raw("3.90"), haiku=Raw("0.10")))
             + U_CONTROL,
             ("unknown; known subtotal $0.50", "unknown", session_priced(2, missing=1)),
             [sgl(6, "B", "2026-10-05 10:00:00 +0100", BASE_REASON)],
             [session_line("B", "b", [(2, "$1.00"), (4, "missing"), (6, "$4.00")], "neither", "line 4",
                           "unknown (%s)" % BASE_REASON)])
# The session id: of the wrong kind or blank, a close cannot be placed in a session (named, invalid).
for _name, _sid, _why in (("session-id-wrong-type", 5, "a number"), ("session-id-blank", " ", "blank")):
    session_case(_name,
                 claude_pass("W", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("1.00"), sid=_sid) + U_CONTROL,
                 ("unknown; known subtotal $0.50", "unknown", session_priced(2, invalid=1)),
                 [sgl(2, "W", "2026-10-06 10:10:00 +0100", "session_id is %s: its running total cannot be placed in a session" % _why)])
# CR-WW1 finding 3: absent or null, a session id names no session, and that is no proof the line is a session of its
# own: A's two resumed passes at $2.00 then $3.00 could be one session that cost $3.00 or two that cost $5.00. Each
# is unknown, named, counted missing; known subtotal U's $0.50. The fold before this one counted $5.50, complete.
for _name, _sid, _state in (("session-id-absent-unknown", SESSION_ABSENT, "absent"), ("session-id-null-unknown", None, "recorded as null")):
    session_case(_name,
                 claude_pass("A", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("2.00"), sid=_sid)
                 + claude_pass("A", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", Raw("3.00"), sid=_sid, opening="lane-resumed")
                 + U_CONTROL,
                 ("unknown; known subtotal $0.50", "unknown", session_priced(3, missing=2)),
                 [sgl(2, "A", "2026-10-06 10:10:00 +0100", NO_SESSION % ("session_id", _state)),
                  sgl(4, "A", "2026-10-06 10:30:00 +0100", NO_SESSION % ("session_id", _state))],
                 [SESSION_ROW % ("unknown; known subtotal $0.50", "1 session"), SESSION_LISTED % 0])
# An unidentified beat can belong to the earlier close's session, so neither its amount nor the
# close's amount can establish a complete session figure. The independent control still contributes $0.50.
R_CLOSE = claude_pass("R", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("1.00"), sid="s-r")
for _name, _lane, _sid, _what, _state in (
        ("beat-session-id-absent-unknown", "R", SESSION_ABSENT, "session_id", "absent"),
        ("beat-session-id-null-unknown", "R", None, "session_id", "recorded as null"),
        ("beat-lane-absent-unknown", SESSION_ABSENT, "s-r", "lane", "absent"),
        ("beat-lane-null-unknown", None, "s-r", "lane", "recorded as null")):
    session_integrity_case(_name, R_CLOSE + [session_beat("2026-10-06T10:20:00+0100", Raw("1.10"), lane=_lane, sid=_sid)], 'session')
for _name, _lane, _sid, _why in (("beat-session-id-wrong-type", "R", 5, "session_id is a number"),
                                 ("beat-session-id-blank", "R", "", "session_id is blank"),
                                 ("beat-lane-wrong-type", 5, "s-r", "lane is a number"),
                                 ("beat-lane-blank", " ", "s-r", "lane is blank")):
    session_integrity_case(_name, R_CLOSE + [session_beat("2026-10-06T10:20:00+0100", Raw("1.10"), lane=_lane, sid=_sid)], 'session')
# Every model inventory must be usable, including an intervening one. A carried valid model
# cannot excuse another model's absent or invalid measure. A model name disappearing also
# contradicts running totals; without a positive earlier cost it supplies no per-pass evidence.
K = entry(Raw("0.10"))
for _name, _second in (("session-model-usage-absent", {"models": None}),
                       ("session-model-usage-null", {"usage": {"modelUsage": None, "calls": 1}}),
                       ("session-model-usage-wrong-type", {"usage": {"modelUsage": ["opus"], "calls": 1}})):
    session_integrity_case(_name, claude_pass("M", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("1.00"), sid="m",
                             models=mu(opus=Raw("0.90"), k=K))
                 + claude_pass("M", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", Raw("2.00"), sid="m",
                               opening="lane-resumed", **_second)
                 + claude_pass("M", "2026-10-06T10:40:00+0100", "2026-10-06T10:50:00+0100", Raw("3.00"), sid="m",
                               opening="lane-resumed", models=mu(opus=Raw("2.90"), k=K)), 'unknown')
for _name, _first, _second in (
        ("session-model-cost-absent", mu(opus=Raw("0.90"), k=K), mu(opus=SESSION_ABSENT, k=K)),
        ("session-model-cost-null", mu(opus=Raw("0.90"), k=K), mu(opus=None, k=K)),
        ("session-model-cost-wrong-type", mu(opus=Raw("0.90"), k=K), mu(opus="0.10", k=K)),
        ("session-model-entry-wrong-type", mu(opus=Raw("0.90"), k=K), {"opus": 5, "k": K}),
        ("session-model-cost-negative", mu(opus=Raw("0.90"), k=K), mu(opus=-1, k=K)),
        ("session-model-cost-zero", mu(opus=0, k=K), mu(k=K)),
        ("session-model-cost-beyond-range", mu(opus=E15, k=K), mu(opus=Raw("1.90"), k=K))):
    session_integrity_case(_name, claude_pass("M", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("1.00"), sid="m", models=_first)
                 + claude_pass("M", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", Raw("2.00"), sid="m",
                               opening="lane-resumed", models=_second), 'unknown')


# The four token counts of a model's entry, each read like its cost (CR-WW1 finding 4's rule: each keeps its last
# usable value): four sessions, one per count, N0 to N3 (lines 1-4, 5-8, 9-12, 13-16), each M-shaped: $1.00 then
# $2.00, k's entry carried over, opus's count FIELD at FIRST then SECOND, every other count as entry writes it.
def counts_lines(first, second):
    out = []
    for i, field in enumerate(COUNT_FIELDS):
        lane, hour = "N%d" % i, 10 + i
        a = entry(Raw("0.90"), **{field: first})
        b = entry(Raw("1.90"), **{field: second})
        out += claude_pass(lane, "2026-10-06T%02d:00:00+0100" % hour, "2026-10-06T%02d:10:00+0100" % hour, Raw("1.00"),
                           sid="n%d" % i, models={"opus": a, "k": K})
        out += claude_pass(lane, "2026-10-06T%02d:20:00+0100" % hour, "2026-10-06T%02d:30:00+0100" % hour, Raw("2.00"),
                           sid="n%d" % i, opening="lane-resumed", models={"opus": b, "k": K})
    return out


# Measured zero counts remain usable: four sessions each count $2.00, giving $8.00. Every unusable
# count instead makes its session unknown, with the separate $0.50 control still counted.
for _name, _first, _second in (("session-model-counts-zero", 0, 0), ("session-model-counts-absent", 10, SESSION_ABSENT),
                               ("session-model-counts-null", 10, None), ("session-model-counts-wrong-type", 10, "10"),
                               ("session-model-counts-negative", 10, -1), ("session-model-counts-fraction", 10, Raw("10.5")),
                               ("session-model-counts-beyond-range", 10, E15)):
    session_case(_name, counts_lines(_first, _second), ("$8.00", "complete", session_priced(8)), (),
                 [SESSION_READ % (4, 0, 0, 0)]
                 + [session_line("N%d" % i, "n%d" % i, [(4 * i + 2, "$1.00"), (4 * i + 4, "$2.00")],
                                 carry("k", 4 * i + 2, 4 * i + 4), "none", "$2.00") for i in range(4)]) if _name == "session-model-counts-zero" else session_integrity_case(_name, counts_lines(_first, _second), 'unusable model evidence')
# A count that falls (10 then 5) is what no running total does, beside k carried over: each session reads as
# neither, unknown, named; known subtotal $0.00, 4 unclassified. The gaps sort by place: lines 12, 16, 4, 8.
COUNT_FALLS = [("model \"k\"'s entry is carried over unchanged from line %d to line %d, but aggregate %s falls from "
                "%d at line %d to %d at line %d" % (4 * i + 2, 4 * i + 4, field, 20 + 10 * i,
                                                   4 * i + 2, 15 + 10 * i, 4 * i + 4)) + NEITHER
               for i, field in enumerate(("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))]
session_case("session-model-counts-falls", counts_lines(10, 5),
             ("unknown; known subtotal $0.00", "unknown", session_priced(8, unclassified=4)),
             [sgl(4 * i + 4, "N%d" % i, "2026-10-06 %02d:30:00 +0100" % (10 + i), COUNT_FALLS[i]) for i in (2, 3, 0, 1)])


# CR-WW1 finding 2: a session whose history lost a line. X's totals are $1.00 (line 2, 2026-10-03) and $3.00
# (2026-10-04) before the start and $5.00 inside (haiku's entry carried over each time). Read as running totals, it
# spent 5.00 - 3.00 = $2.00 inside; if the $3.00 line cannot be read into the session, the reader cannot tell its
# total at the start from the line before, and the fold before this one counted 5.00 - 1.00 = $4.00, complete.
# Each such loss makes the session's spend unknown, named, counted missing; known subtotal U's $0.50.
X1 = claude_pass("X", "2026-10-03T10:00:00+0100", "2026-10-03T10:10:00+0100", Raw("1.00"), sid="x",
                 models=mu(opus=Raw("0.90"), haiku=Raw("0.10")))
X3 = claude_pass("X", "2026-10-05T09:00:00+0100", "2026-10-05T10:00:00+0100", Raw("5.00"), sid="x", opening="lane-resumed",
                 models=mu(opus=Raw("4.90"), haiku=Raw("0.10")))
X_MIDDLE = mu(opus=Raw("2.90"), haiku=Raw("0.10"))


def lost(n, what):
    return "line %d (%s)" % (n, what) + LOST_TAIL


# The $3.00 close pairs with no opening (the review's first case): line 3, a close with no opening before it.
session_case("session-lost-unpaired-close",
             X1 + [claude_pass("X", "2026-10-04T10:00:00+0100", "2026-10-04T10:10:00+0100", Raw("3.00"), sid="x",
                               models=X_MIDDLE)[1]] + X3 + U_CONTROL,
             ("unknown; known subtotal $0.50", "unknown", session_priced(2, missing=1)),
             [sgl(5, "X", "2026-10-05 10:00:00 +0100", lost(3, "a close with no opening before it on the record"))],
             [session_line("X", "x", [(2, "$1.00"), (3, "$3.00"), (5, "$5.00")], "neither", "line 3",
                           "unknown (%s)" % lost(3, "a close with no opening before it on the record"))],
             ["  - " + LOST_GROUP + ": 1 (affects Priced spend)"])
# The $3.00 close on another basis (the review's second case: neither cost_src nor a price), and Y's middle close a
# watch close's transcript estimate: X's line 4 and Y's line 10, each between the session's last priced line
# before the start and the start. Y: $2.00 (line 8), the estimate (line 10), $6.00 inside (line 12).
session_case("session-lost-other-basis",
             X1 + claude_pass("X", "2026-10-04T10:00:00+0100", "2026-10-04T10:10:00+0100", None, sid="x", opening="lane-resumed",
                              cost_src=SESSION_ABSENT, total_cost_usd=SESSION_ABSENT) + X3
             + claude_pass("Y", "2026-10-03T11:00:00+0100", "2026-10-03T11:10:00+0100", Raw("2.00"), sid="y",
                           models=mu(opus=Raw("1.90"), haiku=Raw("0.10")))
             + claude_pass("Y", "2026-10-04T11:00:00+0100", "2026-10-04T11:10:00+0100", None, sid="y", opening="lane-resumed",
                           cost_src="transcript-estimate", exit_class="watch-closed")
             + claude_pass("Y", "2026-10-05T11:00:00+0100", "2026-10-05T11:10:00+0100", Raw("6.00"), sid="y", opening="lane-resumed",
                           models=mu(opus=Raw("5.90"), haiku=Raw("0.10")))
             + U_CONTROL,
             ("unknown; known subtotal $0.50", "unknown", session_priced(3, missing=2)),
             [sgl(12, "Y", "2026-10-05 11:10:00 +0100",
                  lost(10, "a close on another basis than the result's (a transcript estimate carries no dollar figure)")),
              sgl(6, "X", "2026-10-05 10:00:00 +0100",
                  lost(4, "a close on another basis than the result's (no cost_src and no price on the close)"))])
# A line before the start whose session cannot be read (the review's pre-interval identity error): X's middle close
# names session_id 5, Y's names none (absent). Y: $2.00 (line 8), the close naming none (line 10), $6.00 (line 12).
session_case("session-lost-identity-before-the-start",
             X1 + claude_pass("X", "2026-10-04T10:00:00+0100", "2026-10-04T10:10:00+0100", Raw("3.00"), sid=5, opening="lane-resumed",
                              models=X_MIDDLE) + X3
             + claude_pass("Y", "2026-10-03T11:00:00+0100", "2026-10-03T11:10:00+0100", Raw("2.00"), sid="y",
                           models=mu(opus=Raw("1.90"), haiku=Raw("0.10")))
             + claude_pass("Y", "2026-10-04T11:00:00+0100", "2026-10-04T11:10:00+0100", Raw("4.00"), sid=SESSION_ABSENT,
                           opening="lane-resumed", models=mu(opus=Raw("3.90"), haiku=Raw("0.10")))
             + claude_pass("Y", "2026-10-05T11:00:00+0100", "2026-10-05T11:10:00+0100", Raw("6.00"), sid="y", opening="lane-resumed",
                           models=mu(opus=Raw("5.90"), haiku=Raw("0.10")))
             + U_CONTROL,
             ("unknown; known subtotal $0.50", "unknown", session_priced(3, missing=2)),
             [sgl(12, "Y", "2026-10-05 11:10:00 +0100", lost(10, "a close that names no session")),
              sgl(6, "X", "2026-10-05 10:00:00 +0100", lost(4, "a close that cannot be placed in a session"))])
# An invalid line that could be one of the session's: after X's $1.00 (line 2), Z's close with no usable timestamp
# (line 3) and a line that is not JSON (line 4), both undated before X's resumed opening of 2026-10-04 12:00 (line
# 5), so before the start and reaching no figure of this interval themselves. The line that is not JSON could be
# anyone's on its record, X's included; Z's close names Z, whose one line inside (line 8, $2.00) could follow it.
# Each unknown. U's control is in a record of its own (run-u.jsonl), which no line of run-s.jsonl can reach.
@case(2, "session-lost-invalid-line")
def t2_session_lost_invalid(ctx):
    fx = Fx(ctx.root, "session-lost-invalid-line", script=ctx.script)
    fx.write("run-s.jsonl",
             X1 + [{"ts": "2026-10-04T25:00:00+0100", "event": "lane-closed", "lane": "Z", "session_id": "z", "cost_src": "result",
                    "total_cost_usd": 1.0},
                   '{"ts": "2026-10-04T10:10:00+0100", "event": "lane-cl']
             + claude_pass("X", "2026-10-04T12:00:00+0100", "2026-10-05T10:00:00+0100", Raw("5.00"), sid="x", opening="lane-resumed",
                           models=mu(opus=Raw("4.90"), haiku=Raw("0.10")))
             + claude_pass("Z", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("2.00"), sid="z"))
    fx.write("run-u.jsonl", U_CONTROL)
    session_run(ctx, "lost-invalid-line", None, ("unknown; known subtotal $0.50", "unknown", session_priced(3, missing=2)),
                [sgl(6, "X", "2026-10-05 10:00:00 +0100", lost(4, "an invalid line: not JSON")),
                 sgl(8, "Z", "2026-10-06 10:10:00 +0100",
                     lost(3, "an invalid line: no usable timestamp ('2026-10-04T25:00:00+0100')"))], fx=fx)


# The retained case name describes the superseded exception it now rejects. An unpaired close
# before the chosen baseline and an unusable close inside the interval each invalidate their
# entire session. Only the independent $0.50 control is counted.
session_integrity_case("session-lost-line-that-cannot-change-the-figure", claude_pass("X", "2026-10-02T10:00:00+0100", "2026-10-02T10:10:00+0100", Raw("1.00"), sid="x",
                         models=mu(opus=Raw("0.90"), haiku=Raw("0.10")))
             + [claude_pass("X", "2026-10-03T10:00:00+0100", "2026-10-03T10:10:00+0100", Raw("2.00"), sid="x", models=X_MIDDLE)[1]]
             + claude_pass("X", "2026-10-04T10:00:00+0100", "2026-10-04T10:10:00+0100", Raw("3.00"), sid="x", opening="lane-resumed",
                           models=X_MIDDLE)
             + claude_pass("X", "2026-10-04T11:00:00+0100", "2026-10-04T11:10:00+0100", None, sid="x-2", opening="lane-resumed",
                           cost_src="transcript-estimate", exit_class="watch-closed")
             + claude_pass("X", "2026-10-05T09:00:00+0100", "2026-10-05T10:00:00+0100", Raw("5.00"), sid="x", opening="lane-resumed",
                           models=mu(opus=Raw("4.90"), haiku=Raw("0.10")))
             + claude_pass("Y", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("1.00"), sid="y",
                           models=mu(opus=Raw("0.90"), haiku=Raw("0.10")))
             + claude_pass("Y", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", None, sid="y", opening="lane-resumed",
                           cost_src=SESSION_ABSENT, total_cost_usd=SESSION_ABSENT)
             + claude_pass("Y", "2026-10-06T10:40:00+0100", "2026-10-06T10:50:00+0100", Raw("2.00"), sid="y", opening="lane-resumed",
                           models=mu(opus=Raw("1.90"), haiku=Raw("0.10")))
             + U_CONTROL, 'line 3')


# CR-WW1 finding 4's sequence remains unknown: totals $7, $8, $10; A's cost 7, null, 6;
# B absent, 1, 4. The stricter integrity gate now rejects the null inventory before classification.
A_FALL = "model \"A\"'s costUSD falls from $7.00 at line 2 to $6.00 at line 6"
UNUSABLE = [mu(A=Raw("7")), mu(A=None, B=Raw("1")), mu(A=Raw("6"), B=Raw("4"))]
session_integrity_case("session-unusable-cost-hides-no-fall", sum((claude_pass("Q", "2026-10-06T10:%d0:00+0100" % (2 * k), "2026-10-06T10:%d0:00+0100" % (2 * k + 1), Raw(t), sid="q",
                              opening="lane-open" if k == 0 else "lane-resumed", models=m)
                  for k, (t, m) in enumerate(zip(("7", "8", "10"), UNUSABLE))), []) + U_CONTROL, 'unusable model evidence')
# The same with C's $0.25 entry carried over unchanged at every close: the carry alone would read it as running
# totals ($10.00), so only A's kept 7 shows the fall; carried over beside a fall, it reads as neither.
CARRIED = [dict(m, C=entry(Raw("0.25"))) for m in UNUSABLE]
session_integrity_case("session-unusable-cost-hides-no-fall-beside-a-carry", sum((claude_pass("Q", "2026-10-06T10:%d0:00+0100" % (2 * k), "2026-10-06T10:%d0:00+0100" % (2 * k + 1), Raw(t), sid="q",
                              opening="lane-open" if k == 0 else "lane-resumed", models=m)
                  for k, (t, m) in enumerate(zip(("7", "8", "10"), CARRIED))), []) + U_CONTROL, 'unusable model evidence')


# CR-WW1 finding 5: two closes establish running totals; a later beat sets the terminal amount.
# $0.40, $1.00, beat $1.10 counts $1.10 plus U's $0.50, giving $1.60. The bare close/beat
# companion has valid evidence but no carry or model disappearance, so remains unknown.
@case(2, "session-later-beat-sets-the-terminal")
def t2_session_terminal_beat(ctx):
    session_run(ctx, "terminal-beat",
                claude_pass("R", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("0.40"), sid="s-r",
                            models=mu(opus=Raw("0.30"), haiku=Raw("0.10")))
                + claude_pass("R", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", Raw("1.00"), sid="s-r",
                              opening="lane-resumed", models=mu(opus=Raw("0.90"), haiku=Raw("0.10")))
                + [session_beat("2026-10-06T10:35:00+0100", Raw("1.10"))] + U_CONTROL,
                ("$1.60", "complete", session_priced(3, 1)), (),
                [session_line("R", "s-r", [(2, "$0.40"), (4, "$1.00"), (5, "$1.10")], carry("haiku", 2, 4), "none", "$1.10")])
    session_run(ctx, "terminal-beat-pair",
                R_CLOSE + [session_beat("2026-10-06T10:35:00+0100", Raw("1.10"))] + U_CONTROL,
                ("unknown; known subtotal $0.50", "unknown", session_priced(2, 1, unclassified=1)),
                [sgl(3, None, "2026-10-06 10:35:00 +0100", NEITHER_NONE, "Priced spend: closes; Priced spend: hold beats")])


# The same at the start (the review checked it by its own probe; this pins it): a beat before the start, after the
# session's last close there, is its total at the start. R closes at $1.00 (2026-10-04 20:10), beats at $1.50 (23:00)
# and, resumed, closes inside at $4.00 (haiku carried over): 4.00 - 1.50 = $2.50, with U $3.00, complete; the last
# close before the start would give 4.00 - 1.00 = $3.00 and $3.50.
session_case("session-earlier-beat-sets-the-baseline",
             claude_pass("R", "2026-10-04T20:00:00+0100", "2026-10-04T20:10:00+0100", Raw("1.00"), sid="s-r",
                         models=mu(opus=Raw("0.90"), haiku=Raw("0.10")))
             + [session_beat("2026-10-04T23:00:00+0100", Raw("1.50"))]
             + claude_pass("R", "2026-10-05T09:00:00+0100", "2026-10-05T10:00:00+0100", Raw("4.00"), sid="s-r",
                           opening="lane-resumed", models=mu(opus=Raw("3.90"), haiku=Raw("0.10")))
             + U_CONTROL,
             ("$3.00", "complete", session_priced(2)), (),
             [session_line("R", "s-r", [(2, "$1.00"), (3, "$1.50"), (5, "$4.00")], carry("haiku", 2, 5), "line 3", "$2.50")])


# CR-WW1 finding 7: the interval is half-open, [start, end), for sessions as for every figure, and FIELDS.md says so.
# H closes at 2026-10-11 23:00 with $3.00 and, resumed, at the end's own instant, 2026-10-12 00:00, with $7.00
# (haiku carried over). In [2026-10-05, 2026-10-12) the second close is the next interval's, so H holds one line
# before the end and counts $3.00; in [2026-10-12, 2026-10-19) it reads as running totals: 7.00 - 3.00 = $4.00.
HALF_OPEN = ("The interval is half-open, [start, end): a line at the end's own instant belongs to the next interval")


@case(2, "session-interval-half-open")
def t2_session_half_open(ctx):
    fields = open(os.path.join(os.path.dirname(os.path.abspath(ctx.script)), "FIELDS.md"), encoding="utf-8").read()
    expect(HALF_OPEN in "\n".join(section(fields, "## Priced spend")),
           "FIELDS.md's Priced spend does not state the half-open interval: %r" % HALF_OPEN)
    fx = Fx(ctx.root, "session-half-open", script=ctx.script)
    fx.write("run-s.jsonl",
             claude_pass("H", "2026-10-11T22:00:00+0100", "2026-10-11T23:00:00+0100", Raw("3.00"), sid="h",
                         models=mu(opus=Raw("2.90"), haiku=Raw("0.10")))
             + claude_pass("H", "2026-10-12T00:00:00+0100", "2026-10-12T00:00:00+0100", Raw("7.00"), sid="h", opening="lane-resumed",
                           models=mu(opus=Raw("6.90"), haiku=Raw("0.10"))))
    session_run(ctx, "half-open", None, ("$3.00", "complete", session_priced(1)), (),
                [SESSION_ROW % ("$3.00", "1 session"), SESSION_READ % (0, 0, 0, 1)], fx=fx)
    session_run(ctx, "half-open-next", None, ("$4.00", "complete", session_priced(1)), (),
                [session_line("H", "h", [(2, "$3.00"), (4, "$7.00")], carry("haiku", 2, 4), "line 2", "$4.00")],
                since="2026-10-12", until="2026-10-19", fx=fx)


# The detail's sum of the priced closes' recorded values, when a gap reaches the priced closes: "unknown; known
# subtotal $1.00", never "$unknown; ..." (B-WW1's proposed second hunk). A's $1.00 beside Z's close with no opening
# before it (line 3, inside: a gap of the episode figures, the priced closes among them).
@case(2, "exact-closes-line-states-its-subtotal")
def t2_exact_subtotal(ctx):
    fx = Fx(ctx.root, "session-exact-subtotal", script=ctx.script)
    fx.write("run-s.jsonl", claude_pass("A", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("1.00"), sid="a")
             + [claude_pass("Z", "2026-10-06T10:10:00+0100", "2026-10-06T10:20:00+0100", Raw("2.00"), sid="z")[1]])
    code, out, err, main, detail = fx.report()
    expect(code == 0 and detail is not None, "exit %d: %s" % (code, last_line(err)))
    exact = [l for l in detail.split("\n") if l.startswith("- priced closes, sum of the recorded values: ")]
    expect(exact == ["- priced closes, sum of the recorded values: unknown; known subtotal $1.00 (the main report rounds to the cent)"],
           "the exact line: %r" % exact)
    session_run(ctx, "exact-subtotal", None,
                ("unknown; known subtotal $1.00", "unknown",
                 PRICED_COV % ("1 priced close", "0 priced hold beats", 1, 0, 0, 0, G1)),
                ['- run-s.jsonl:3 "Z" · 2026-10-06 10:20:00 +0100 · a close with no opening before it on the record · affects: '
                 + EPISODE_PARTS,
                 sgl(3, "Z", "2026-10-06 10:20:00 +0100", lost(3, "a close with no opening before it on the record"))], fx=fx)


# CR-WW2: accounting acceptance checks the amount and completeness before explanatory wording.
# Every reproduction has a valid independent $0.50 control; its records are read-only while the
# report runs, and the byte manifest must stay identical. These helpers only create fixtures.
def ww2_probe(ctx, name, lines, amount, status, reading=None, gap_fragment=None):
    fx = Fx(ctx.root, "review-" + name, script=ctx.script)
    fx.write("run-s.jsonl", lines)
    fx.write("run-control.jsonl", U_CONTROL)
    before = tree_manifest(fx.records)
    for path in before:
        if os.path.isfile(path):
            os.chmod(path, 0o444)
    os.chmod(fx.records, 0o555)
    before = tree_manifest(fx.records)
    try:
        code, out, err, main, detail = fx.report()
        expect(code == 0 and main is not None and detail is not None,
               "report failed: %d %s" % (code, err[-300:]))
        got = as_map(rows_of(main)).get(SP_T)
        expect(got is not None and got[:2] == (amount, status),
               "priced total's value and status: got %r; want %r" % (got and got[:2], (amount, status)))
        named = section(detail, "## Named gaps and the figures they affect")
        if status == "unknown":
            expect(any("Priced spend" in line for line in named), "uncertainty has no dependent priced-spend gap")
        else:
            expect(named == ["- none"], "clean control has named gaps: %r" % named)
        if reading:
            expect("read as " + reading in detail, "session reading absent: " + reading)
        if gap_fragment:
            expect(any(gap_fragment in line for line in named), "named gap lacks " + gap_fragment)
        expect(tree_manifest(fx.records) == before, "report modified its read-only record fixtures")
        return main, detail
    finally:
        os.chmod(fx.records, 0o755)


def ww2_close(total, hour, models, day="06", opening="lane-resumed"):
    return claude_pass("R", "2026-10-%sT%s:00:00+0100" % (day, hour),
                       "2026-10-%sT%s:10:00+0100" % (day, hour), Raw(total),
                       sid="s-r", opening=opening, models=models)


def ww2_beat(total="2.10", models=("opus", "haiku"), counts=(20, 40, 60, 80)):
    out = session_beat("2026-10-06T12:10:00+0100", Raw(total))
    out["usage"] = dict(zip(("input_tokens", "output_tokens", "cache_read_input_tokens",
                             "cache_creation_input_tokens"), counts), models=list(models))
    return out


WW2_CARRY = (ww2_close("1", "10", mu(opus=Raw("0.5"), haiku=Raw("0.5")), opening="lane-open")
             + ww2_close("2", "11", mu(opus=Raw("1.5"), haiku=Raw("0.5"))))


@case(2, "review-n1-empty-inventory-unknown")
def t2_review_n1_empty(ctx):
    first = ww2_close("2", "10", mu(opus=Raw("1.5"), haiku=Raw("0.5")), opening="lane-open")
    # $2 -> $3 with a complete carried model costs $3; empty evidence must never make it $5.
    ww2_probe(ctx, "n1-clean", first + ww2_close("3", "11", mu(opus=Raw("2.5"), haiku=Raw("0.5"))),
              "$3.50", "complete", "running totals")
    ww2_probe(ctx, "n1-empty", first + ww2_close("3", "11", {}),
              "unknown; known subtotal $0.50", "unknown")


@case(2, "review-n1-whole-model-entry-omitted-unknown")
def t2_review_n1_whole_entry(ctx):
    # The second close declares $3 but lists only $2.50: the omitted $0.50 model
    # must not turn incomplete evidence into per-pass accounting. U contributes $0.50.
    first = ww2_close("2", "10", mu(opus=Raw("1.5"), haiku=Raw("0.5")), opening="lane-open")
    ww2_probe(ctx, "n1-whole-entry-omitted", first + ww2_close("3", "11", mu(opus=Raw("2.5"))),
              "unknown; known subtotal $0.50", "unknown")


# B-WW4's fold: the reconciliation rule (the head's decision of 27 October 2026, which the owner may undo; FIELDS.md,
# "Priced spend"). A priced close's model costs, summed exactly as written, must lie within 1E-9 USD of its
# total_cost_usd, or its inventory is inconsistent and its session's spend unknown. Each edge is fixed by hand: R
# closes at $2 (opus 1.5, haiku 0.5), then at the edge's total with opus at the edge's cost and haiku's entry carried
# over unchanged (running totals); U adds $0.50 in a record of its own. Consistent, R counts its last total, $3 plus
# at most 1E-9, and the main report shows $3.50, complete; inconsistent, R is unknown, named at its line, and only U's
# $0.50 is known. The second close alone, a session of one line, reads the same way: $3.50, or unknown.
RECONCILE_EDGES = (
    ("6.4e-14-total-above-costs", "3.000000000000064", "2.5", True),   # costs 2.5 + 0.5 = 3: |3 - 3.000000000000064| = 6.4E-14
    ("6.4e-14-costs-above-total", "3", "2.500000000000064", True),     # costs 3.000000000000064 against 3: 6.4E-14
    ("tolerance-exactly", "3.000000001", "2.5", True),                 # |3 - 3.000000001| = 1E-9: at most the tolerance
    ("1e-7-total-above-costs", "3.0000001", "2.5", False),             # 1E-7, one token at the cheapest list rate
    ("1e-7-costs-above-total", "3", "2.5000001", False))               # costs 3.0000001 against 3: 1E-7
RECONCILE_GAP = ("has unusable model evidence (usage.modelUsage costs sum to $%s, not total_cost_usd $%s: they differ "
                 "by $0.0000001, more than the reconciliation tolerance of $0.000000001)")
for _edge, _total, _opus, _consistent in RECONCILE_EDGES:
    def _reconcile(ctx, edge=_edge, total=_total, opus=_opus, consistent=_consistent):
        first = ww2_close("2", "10", mu(opus=Raw("1.5"), haiku=Raw("0.5")), opening="lane-open")
        second = ww2_close(total, "11", mu(opus=Raw(opus), haiku=Raw("0.5")))
        alone = ww2_close(total, "11", mu(opus=Raw(opus), haiku=Raw("0.5")), opening="lane-open")
        if consistent:
            ww2_probe(ctx, "reconcile-" + edge, first + second, "$3.50", "complete", "running totals")
            ww2_probe(ctx, "reconcile-" + edge + "-alone", alone, "$3.50", "complete")
            return
        # The costs' sum and the total as the reader prints them, each exactly as written: 2.5 + 0.5 is 3.
        sums = ("3", "3.0000001") if total != "3" else ("3.0000001", "3")
        ww2_probe(ctx, "reconcile-" + edge, first + second, "unknown; known subtotal $0.50", "unknown",
                  gap_fragment="line 4 " + RECONCILE_GAP % sums)
        ww2_probe(ctx, "reconcile-" + edge + "-alone", alone, "unknown; known subtotal $0.50", "unknown",
                  gap_fragment="line 2 " + RECONCILE_GAP % sums)
    case(2, "review-n1-reconciliation-" + _edge)(_reconcile)


@case(2, "review-n1-empty-inventory-at-zero-total-unknown")
def t2_review_n1_empty_zero(ctx):
    # An empty inventory on a $0 close reconciles ($0 of costs against $0), so the inventory rule alone names it: empty
    # evidence is never a model dropped. Read as one, opus and haiku would be dropped and R per-pass: $2 + $0, $2.50
    # with U. Unknown; known subtotal U's $0.50. (On a priced close the reconciliation also catches an empty
    # inventory, so this is the case that holds the empty-inventory rule to its own mutant.)
    first = ww2_close("2", "10", mu(opus=Raw("1.5"), haiku=Raw("0.5")), opening="lane-open")
    ww2_probe(ctx, "n1-empty-zero", first + ww2_close("0", "11", {}), "unknown; known subtotal $0.50", "unknown",
              gap_fragment="line 4 has unusable model evidence (usage.modelUsage is not a non-empty model inventory)")


# Two held cases whose inventories do not reconcile with their totals now read unknown at the reconciliation, before
# the evidence they were written for is weighed: T2.session-model-cost-zero ($0 + $0.10 against $1.00, then $0.10
# against $2.00) and T2.session-unusable-cost-hides-no-fall-beside-a-carry (C's $0.25 left out of $7 and $10). Each
# stays as it was; its companion below carries the same evidence on totals that reconcile, so that evidence's own
# path stays held. M: $0.10 (opus at $0, k $0.10), then $2.00 (k carried over, sonnet $1.90): opus, at no cost, gone
# from the later inventory contradicts running totals and is no per-pass evidence, so unknown.
session_integrity_case("session-model-cost-zero-reconciled",
                       claude_pass("M", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", Raw("0.10"), sid="m",
                                   models=mu(opus=0, k=K))
                       + claude_pass("M", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", Raw("2.00"), sid="m",
                                     opening="lane-resumed", models=mu(k=K, sonnet=Raw("1.90"))),
                       "model \"k\"'s entry is carried over unchanged from line 2 to line 4, but a model named at line 2 "
                       "is absent from the inventory at line 4")
# Q's totals carry C's $0.25 ($7.25, $8.25, $10.25): A's null cost at line 4 is what makes the session unknown.
session_integrity_case("session-unusable-cost-hides-no-fall-beside-a-carry-reconciled",
                       sum((claude_pass("Q", "2026-10-06T10:%d0:00+0100" % (2 * k), "2026-10-06T10:%d0:00+0100" % (2 * k + 1),
                                        Raw(t), sid="q", opening="lane-open" if k == 0 else "lane-resumed", models=m)
                            for k, (t, m) in enumerate(zip(("7.25", "8.25", "10.25"), CARRIED))), []) + U_CONTROL,
                       "line 4 has unusable model evidence (a model cost or token count is absent or unusable)")


# FIELDS.md states the rule and its decision, and the reader keeps the tolerance's derivation beside the constant.
RECONCILE_DOC = ("A priced close's model costs, summed exactly as written, must lie within 1E-9 USD of its "
                 "`total_cost_usd`")


@case(2, "review-n1-reconciliation-documented")
def t2_reconciliation_documented(ctx):
    fields = open(os.path.join(os.path.dirname(os.path.abspath(ctx.script)), "FIELDS.md"), encoding="utf-8").read()
    priced = "\n".join(section(fields, "## Priced spend"))
    for needle in (RECONCILE_DOC, "Head decision of 27 October 2026", "6.4E-14", "1E-7"):
        expect(needle in priced, "FIELDS.md's Priced spend lacks: %r" % needle)
    lines = open(ctx.script, encoding="utf-8").read().split("\n")
    at = [i for i, l in enumerate(lines) if l.startswith("RECONCILE_TAU = ")]
    expect(len(at) == 1 and lines[at[0]] == 'RECONCILE_TAU = Decimal("1E-9")', "the reader's tolerance: %r"
           % [lines[i] for i in at])
    beside = "\n".join(lines[max(0, at[0] - 15):at[0]])
    for needle in ("6.4E-14", "1E-7", "prices.json", "Derivation"):
        expect(needle in beside, "the derivation beside the tolerance lacks: %r" % needle)


for _inventory_name, _inventory in (
        ("null-entry", {"opus": None}),
        ("missing-cost", {"opus": entry(SESSION_ABSENT)}),
        ("missing-count", {"opus": entry(Raw("3"), outputTokens=SESSION_ABSENT)}),
        ("null-count", {"opus": entry(Raw("3"), outputTokens=None)}),
        ("invalid-count", {"opus": entry(Raw("3"), outputTokens=True)}),
        ("blank-model", {" ": entry(Raw("3"))})):
    def _n1_incomplete(ctx, inventory=_inventory, suffix=_inventory_name):
        ww2_probe(ctx, "n1-" + suffix,
                  ww2_close("2", "10", mu(opus=Raw("1.5"), haiku=Raw("0.5")), opening="lane-open")
                  + ww2_close("3", "11", inventory), "unknown; known subtotal $0.50", "unknown")
    case(2, "review-n1-incomplete-inventory-" + _inventory_name)(_n1_incomplete)


@case(2, "review-n2-per-pass-lost-close-unknown")
def t2_review_n2(ctx):
    first = ww2_close("2", "10", mu(opus=Raw("1.5"), haiku=Raw("0.5")), day="03", opening="lane-open")
    middle = ww2_close("3", "10", mu(opus=Raw("2.5"), haiku=Raw("0.5")), day="04")
    last = ww2_close("4", "10", mu(opus=Raw("4")))
    # Dropping haiku alone supports per-pass: only the inside $4 plus the $0.50 control.
    ww2_probe(ctx, "n2-clean-per-pass", first + last, "$4.50", "complete", "per-pass costs")
    ww2_probe(ctx, "n2-paired-contradiction", first + middle + last,
              "unknown; known subtotal $0.50", "unknown")
    ww2_probe(ctx, "n2-unpaired", first + middle[1:] + last,
              "unknown; known subtotal $0.50", "unknown", gap_fragment="line 3")


@case(2, "review-n3-superseded-loss-unknown")
def t2_review_n3_superseded(ctx):
    first = ww2_close("1", "10", mu(opus=Raw("0.5"), haiku=Raw("0.5")), day="02", opening="lane-open")
    orphan = ww2_close("9", "10", mu(opus=Raw("8.5"), haiku=Raw("0.5")), day="03")[1:]
    baseline = ww2_close("3", "10", mu(opus=Raw("2.5"), haiku=Raw("0.5")), day="04")
    inside = ww2_close("5", "10", mu(opus=Raw("4.5"), haiku=Raw("0.5")))
    ww2_probe(ctx, "n3-clean", first + baseline + inside, "$2.50", "complete", "running totals")
    ww2_probe(ctx, "n3-superseded", first + orphan + baseline + inside,
              "unknown; known subtotal $0.50", "unknown", gap_fragment="line 3")


@case(2, "review-n3-terminal-estimate-unknown")
def t2_review_n3_estimate(ctx):
    terminal = claude_pass("R", "2026-10-06T12:00:00+0100", "2026-10-06T12:10:00+0100", None,
                           sid="s-r", opening="lane-resumed", cost_src="transcript-estimate", exit_class="watch-closed")
    ww2_probe(ctx, "n3-estimate", WW2_CARRY + terminal,
              "unknown; known subtotal $0.50", "unknown", gap_fragment="transcript")


@case(2, "review-n4-beat-dropped-model-per-pass")
def t2_review_n4_drop(ctx):
    # Historical close and beat values, identities anonymised: $0.047549400000000006 +
    # $0.0024432000000000004 = $0.0499926000000000064, rounded once to $0.05; control adds $0.50.
    first = ww2_close("0.047549400000000006", "10", {
        "small": entry(Raw("0.001283"), inputTokens=1213, outputTokens=14,
                       cacheReadInputTokens=0, cacheCreationInputTokens=0),
        "large": entry(Raw("0.046266400000000006"), inputTokens=4, outputTokens=356,
                       cacheReadInputTokens=9572, cacheCreationInputTokens=10196)}, opening="lane-open")
    beat = ww2_beat("0.0024432000000000004", ("large",), (2, 4, 10196, 90))
    ww2_probe(ctx, "n4-drop", first + [beat], "$0.55", "complete", "per-pass costs")


@case(2, "review-n4-beat-token-fall-unknown")
def t2_review_n4_token_fall(ctx):
    ww2_probe(ctx, "n4-token-clean", WW2_CARRY + [ww2_beat()], "$2.60", "complete", "running totals")
    ww2_probe(ctx, "n4-token-fall", WW2_CARRY + [ww2_beat(counts=(20, 1, 60, 80))],
              "unknown; known subtotal $0.50", "unknown", gap_fragment="output")


@case(2, "review-n4-beat-carried-model-missing-unknown")
def t2_review_n4_missing(ctx):
    ww2_probe(ctx, "n4-model-drop", WW2_CARRY + [ww2_beat(models=("opus",))],
              "unknown; known subtotal $0.50", "unknown", gap_fragment="haiku")


@case(2, "review-n5-close-beat-evidence-decides")
def t2_review_n5(ctx):
    # One close and one beat is not a blanket unknown: the beat can establish per-pass evidence.
    first = ww2_close("1", "10", mu(opus=Raw("0.5"), haiku=Raw("0.5")), opening="lane-open")
    ww2_probe(ctx, "n5-evidence", first + [ww2_beat("1.10", ("opus",), (10, 20, 30, 40))],
              "$2.60", "complete", "per-pass costs")
    # With every model retained and counts unchanged, neither interpretation is established.
    ww2_probe(ctx, "n5-ambiguous", first + [ww2_beat("1.10")],
              "unknown; known subtotal $0.50", "unknown")


for _state, _usage in (("absent", SESSION_ABSENT), ("null", None)):
    def _n1_missing(ctx, state=_state, usage=_usage):
        lines = ww2_close("2", "10", mu(opus=Raw("2")), opening="lane-open")
        if usage is SESSION_ABSENT:
            lines[-1].pop("usage")
        else:
            lines[-1]["usage"] = usage
        ww2_probe(ctx, "n1-inventory-" + state, lines, "unknown; known subtotal $0.50", "unknown")
    case(2, "review-n1-inventory-" + _state)(_n1_missing)


for _state, _names in (("absent", SESSION_ABSENT), ("null", None), ("wrong-type", "opus"),
                       ("empty", []), ("duplicate-model", ["opus", "opus"]), ("blank-model", [" "])):
    def _n4_names(ctx, state=_state, names=_names):
        beat = ww2_beat()
        if names is SESSION_ABSENT:
            beat["usage"].pop("models")
        else:
            beat["usage"]["models"] = names
        ww2_probe(ctx, "n4-beat-inventory-" + state, [beat], "unknown; known subtotal $0.50", "unknown")
    case(2, "review-n4-beat-inventory-" + _state)(_n4_names)


for _state, _count in (("zero", 0), ("absent", SESSION_ABSENT), ("null", None), ("wrong-type", "1"),
                       ("negative", -1), ("fraction", Raw("0.5")), ("beyond-range", E15)):
    def _n4_counts(ctx, state=_state, count=_count):
        for field in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            beat = ww2_beat()
            if count is SESSION_ABSENT:
                beat["usage"].pop(field)
            else:
                beat["usage"][field] = count
            ww2_probe(ctx, "n4-beat-count-" + state + "-" + field, [beat],
                      "$2.60" if state == "zero" else "unknown; known subtotal $0.50",
                      "complete" if state == "zero" else "unknown")
    case(2, "review-n4-beat-count-" + _state)(_n4_counts)


@case(2, "review-loss-middle-price-unknown")
def t2_review_middle_price(ctx):
    middle = ww2_close("1.5", "11", mu(opus=Raw("1"), haiku=Raw("0.5")))
    middle[-1]["total_cost_usd"] = None
    first = ww2_close("1", "10", mu(opus=Raw("0.5"), haiku=Raw("0.5")), opening="lane-open")
    last = ww2_close("2", "12", mu(opus=Raw("1.5"), haiku=Raw("0.5")))
    ww2_probe(ctx, "middle-price", first + middle + last, "unknown; known subtotal $0.50", "unknown")


@case(2, "review-loss-unclosed-session-opening-unknown")
def t2_review_unclosed(ctx):
    unclosed = {"ts": "2026-10-06T12:00:00+0100", "event": "lane-resumed", "lane": "R", "session_id": "s-r",
                "class": "builder"}
    ww2_probe(ctx, "unclosed", WW2_CARRY + [unclosed], "unknown; known subtotal $0.50", "unknown")


@case(2, "review-loss-only-opening-inside-unknown")
def t2_review_only_opening(ctx):
    prior = ww2_close("1", "10", mu(opus=Raw("1")), day="04", opening="lane-open")
    opening = {"ts": "2026-10-06T12:00:00+0100", "event": "lane-resumed", "lane": "R", "session_id": "s-r",
               "class": "builder"}
    ww2_probe(ctx, "only-opening-inside", prior + [opening], "unknown; known subtotal $0.50", "unknown")


@case(2, "review-loss-close-after-end-unknown")
def t2_review_after_end(ctx):
    prior = ww2_close("1", "10", mu(opus=Raw("1")), day="04", opening="lane-open")
    crossing = claude_pass("R", "2026-10-06T12:00:00+0100", "2026-10-13T12:10:00+0100", Raw("2"),
                           sid="s-r", opening="lane-resumed", models=mu(opus=Raw("2")))
    ww2_probe(ctx, "close-after-end", prior + crossing, "unknown; known subtotal $0.50", "unknown")


@case(2, "review-loss-opening-close-identity-unknown")
def t2_review_opening_identity(ctx):
    lines = ww2_close("1", "10", mu(opus=Raw("1")), opening="lane-open")
    lines[0]["session_id"] = "another-session"
    ww2_probe(ctx, "opening-close-identity", lines, "unknown; known subtotal $0.50", "unknown")


@case(2, "review-loss-only-damaged-line-inside-unknown")
def t2_review_only_damaged(ctx):
    prior = ww2_close("1", "10", mu(opus=Raw("1")), day="04", opening="lane-open")
    # A dated boundary on each side locates the unparsable line inside the interval.
    lines = prior + [{"ts": "2026-10-06T12:00:00+0100", "event": "lane-awake"}, "{",
                     {"ts": "2026-10-06T12:20:00+0100", "event": "lane-awake"}]
    ww2_probe(ctx, "only-damaged-inside", lines, "unknown; known subtotal $0.50", "unknown")


@case(2, "parenthesised-class-completes-the-report", cr5=1)
def t2_paren_class(ctx):
    # L beside the control K (run-ok): both reports written, every figure fixed by hand. 60 + 60 = 120 s
    # (2.0 min) over 2 closes; the classes builder (K) and "(builder)" (L) 60 s each, the recorded one
    # shown quoted, '(builder)', so it cannot read as a label ("'" sorts before "b"); no close with no
    # usable class; $0.50 + $0 = $0.50 over 2 priced closes; no named gap.
    code, main, detail = route_run(ctx, "paren-class", [("run-p.jsonl", REVIEW_EXAMPLE)])
    expect(code == 0, "exit %d" % code)
    one = "1 close: 0 not applicable, 0 unknown or invalid; " + GAPS0
    want = priced_rows([("run-ok", "K"), ("run-p", "L")])
    want[(H, "class builder")] = ("60 s (1.0 min)", "complete", one)
    want[(H, "class '(builder)'")] = ("60 s (1.0 min)", "complete", one)
    want[SP_T] = ("$0.50", "complete", PRICED_COV % ("2 priced closes", "0 priced hold beats", 0, 0, 0, 0, GAPS0))
    expect_table_and_gaps(main, detail, want, [])
    lines = detail.split("\n")
    i = lines.index("### By class")
    want_view = ["- '(builder)': 60 s (1.0 min) over 1 close" + V0, "- builder: 60 s (1.0 min) over 1 close" + V0,
                 "- (all): 120 s (2.0 min) over 2 closes (0 unknown or invalid; 0 named gaps (detail))"]
    expect(lines[i + 1:i + 4] == want_view, "class view: %s" % lines[i + 1:i + 4])
    expect('| run-p:"L":1 | \'(builder)\' | lane-open line 1, 2026-10-06 10:00:00 +0100 | lane-closed line 2, '
           "2026-10-06 10:01:00 +0100 | 60 | completed |" in detail, "L's episode row")


# Every label the reports print in place of a recorded value, and the reader's other display words,
# each with the text a recorded string equal to it must take where a label could stand (FIELDS.md,
# "Recorded strings and the reader's labels"): a string that is one of the labels, begins with a
# parenthesis or a quotation mark, has white space at an end or holds a character that does not print
# is shown by its repr; any other as written. The labels come first, from the reader's own definition
# (READER_LABELS, in its order), each shown by its repr; then strings written out here by hand: other
# parenthesised and quoted text, and the display words the reports print where no recorded value
# stands, "all" and "total" among them, which a recorded value prints as written.
LABEL_STRINGS = [(label, repr(label)) for label in READER_LABELS] + [
    ("(builder)", "'(builder)'"),
    ("'(builder)'", "\"'(builder)'\""), (" (class unrecorded)", "' (class unrecorded)'"),
    ("(class unrecorded)" + chr(0x200b), "'(class unrecorded)\\u200b'"),
    ("unknown", "unknown"), ("undated", "undated"), ("time unknown", "time unknown"), ("every figure", "every figure"),
    ("-", "-"), ("none", "none"), ("none recorded", "none recorded"), ("unresolved", "unresolved"),
    ("0 (measured zero)", "0 (measured zero)"), ("not applicable", "not applicable"), ("invalid", "invalid"),
    ("outside", "outside"), ("unknown or invalid", "unknown or invalid"), ("unknown; known subtotal 0", "unknown; known subtotal 0"),
    ("complete", "complete"), ("incomplete", "incomplete"), ("missing", "missing"), ("unpriced", "unpriced"),
    ("known", "known"), ("all", "all"), ("total", "total"),
]


MISSING_FIELD = object()        # a field a fixture line leaves out


def plan_episode(lane, cls, open_ts, close_ts, dur):
    """An opening and a GPT-6 Astra plan close as oc() writes them, but with CLS (None: absent) on both lines."""
    op = {"ts": open_ts, "event": "lane-open", "lane": lane, "harness": "codex"}
    lines = oc(lane, open_ts, close_ts, dur)
    lines[0], close = op, lines[1]
    close.pop("class")
    if cls is not None:
        op["class"] = close["class"] = cls
    return [op, close]


def label_minutes(secs):
    """Minutes to 0.1 for a whole number of seconds that is a multiple of 10: secs/60 is never a half tenth
    (a multiple of 10 is never 3 more than a multiple of 6), so it rounds to the nearest tenth, (secs + 3) // 6."""
    tenths = (secs + 3) // 6
    return "%d s (%d.%d min)" % (secs, tenths // 10, tenths % 10)


@case(2, "recorded-strings-equal-to-every-label", cr5=1)
def t2_label_strings(ctx):
    # run-a.jsonl: for each string of LABEL_STRINGS (32), an episode C00..C31 of that class on both lines,
    # 10 s times its place (10 ... 320 s), the recorded "(class unrecorded)" 4000 s instead of 30; a boundary
    # whose idle_src, head_denials_src, from and to are that string, its place in minutes of idle (1 ... 29),
    # every other boundary count 0; two more boundaries whose idle_src is absent (100 min) and null (200
    # min); an end marker whose lane is that string, and one with no lane. run-b.jsonl: the real uncertainty,
    # U1 whose close's class is a number (invalid, 1000 s), U2 opened as critic and closed as builder
    # (conflicting, 2000 s), U3 with no class (unrecorded, 3000 s). Both reports written; each recorded
    # string a value of its own, in its own row and line, shown as LABEL_STRINGS says, never merged with
    # the label it equals; the three real states shown by their labels. Helper time 5280 - 30 + 4000 = 9250
    # s in run-a and 6000 s in run-b: 15250 s (15250/60 = 254.17 -> 254.2 min) over 35 closes, complete;
    # the three largest classes the recorded '(class unrecorded)' 4000 s and the real (class unrecorded)
    # 3000 s and (class conflicting) 2000 s. Three closes have no usable class: the review counts read
    # unknown with known subtotal 0, three named gaps. Idle: each string's own minutes, and the unrecorded
    # group 100 + 200 = 300 min over 2 boundaries.
    fx = Fx(ctx.root, "t2-label-strings", script=ctx.script)
    n = len(LABEL_STRINGS)
    lines, secs = [], []
    for i, (s, _) in enumerate(LABEL_STRINGS):
        dur = 4000 if s == "(class unrecorded)" else 10 * (i + 1)
        secs.append(dur)
        lines += plan_episode("C%02d" % i, s, "2026-10-06T08:%02d:00+0100" % i, "2026-10-06T09:%02d:00+0100" % i, dur)
    for i, (s, _) in enumerate(LABEL_STRINGS):
        lines.append({"ts": "2026-10-07T08:%02d:00+0100" % i, "event": "phase-boundary", "from": s, "to": s,
                      "idle_min": i + 1, "idle_src": s, "over_cap_reports": 0, "rewrites": 0, "rewrites_total": 0,
                      "head_denials": 0, "head_denials_src": s, "denials": 0, "run_spend_usd": 0})
    for k, (minutes, src) in enumerate(((100, MISSING_FIELD), (200, None))):
        b = {"ts": "2026-10-07T09:%02d:00+0100" % k, "event": "phase-boundary", "from": "a", "to": "b", "idle_min": minutes,
             "over_cap_reports": 0, "rewrites": 0, "rewrites_total": 0, "head_denials": 0, "denials": 0, "run_spend_usd": 0}
        if src is not MISSING_FIELD:
            b["idle_src"] = src
        lines.append(b)
    for i, (s, _) in enumerate(LABEL_STRINGS):
        lines.append({"ts": "2026-10-08T08:%02d:00+0100" % i, "event": "terminated", "lane": s})
    lines.append({"ts": "2026-10-08T09:00:00+0100", "event": "terminated"})
    fx.write("run-a.jsonl", lines)
    u1 = plan_episode("U1", None, "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 1000)
    u1[1]["class"] = 5
    u2 = plan_episode("U2", "critic", "2026-10-06T10:02:00+0100", "2026-10-06T10:03:00+0100", 2000)
    u2[1]["class"] = "builder"
    u3 = plan_episode("U3", None, "2026-10-06T10:04:00+0100", "2026-10-06T10:05:00+0100", 3000)
    fx.write("run-b.jsonl", u1 + u2 + u3)
    code, out, err, main, detail = fx.report()
    expect(code == 0 and main is not None and detail is not None,
           "exit %d, report written %s, detail written %s: %s" % (code, main is not None, detail is not None, last_line(err)))
    closes, total = n + 3, sum(secs) + 6000
    # Fixed by hand for the 32 strings (the reader's 7 labels and 25 written here): a label added to the
    # reader's LABELS changes them, and this probe says so until they are fixed again.
    expect(n == 32 and total == 15250 and sum(secs) == 9250,
           "PROBE FAILED: the fixture's own sums (%d strings, %d s, %d s)" % (n, sum(secs), total))
    want = builder_rows(closes, label_minutes(total), {},
                        {'run-a/"C02"': label_minutes(4000), 'run-b/"U3"': label_minutes(3000), 'run-b/"U2"': label_minutes(2000)})
    one = "1 close: 0 not applicable, 0 unknown or invalid; " + GAPS0
    del want[(H, "class builder")]
    want[(H, "run run-a")] = (label_minutes(9250), "complete", "%d closes: 0 not applicable, 0 unknown or invalid; %s" % (n, GAPS0))
    want[(H, "run run-b")] = (label_minutes(6000), "complete", "3 closes: 0 not applicable, 0 unknown or invalid; " + GAPS0)
    want.update({(H, "class '(class unrecorded)'"): (label_minutes(4000), "complete", one),
                 (H, "class (class unrecorded)"): (label_minutes(3000), "complete", one),
                 (H, "class (class conflicting)"): (label_minutes(2000), "complete", one)})
    want.update(dict((k, v) for k, v in class_unknown("x").items() if k[0] == RV))
    want[(RV, "reviewing-class episodes")] = ("unknown; known subtotal 0", "unknown", RVC_COV % ("3 closes", GAPS0))
    bounds = n + 2
    want.update({(B, "boundary events"): (str(bounds), "complete", "counted at their own timestamps; " + GAPS0),
                 (B, "cumulative rewrites snapshots"): (str(bounds), "complete", BS_COV % 0),
                 (RF, "head fence (boundaries)"): ("0", "complete", HF_COV % ("%d boundaries" % bounds, 0, GAPS0)),
                 SP_SS: (str(bounds), "complete", SS_COV % 0),
                 (B, "recorded idle, idle_src (source unrecorded)"): ("300 min", "complete", IDLE_COV % "2 boundaries")})
    for i, (s, text) in enumerate(LABEL_STRINGS):
        want[(B, "recorded idle, idle_src " + text)] = ("%d min" % (i + 1), "complete", IDLE_COV % "1 boundary")
    part = "Review activity and possible loops: reviewing-class episodes"
    expect_table_and_gaps(main, detail, want, [
        gl('run-b.jsonl:2 "U1" · 2026-10-06 10:01:00 +0100', "the close's class is a number", part),
        gl('run-b.jsonl:4 "U2" · 2026-10-06 10:03:00 +0100', "the close's class 'builder' and the opening's 'critic' disagree", part),
        gl('run-b.jsonl:6 "U3" · 2026-10-06 10:05:00 +0100', "no class on the close or the opening", part)])
    # The coverage's groups, from each reason's own group, never from its text (which quotes the classes).
    cov = section(main, "## Coverage by reason")
    expect(cov[-4:] == ["- Named gaps affecting this interval's figures: 3:",
                        "  - no class on the close or the opening: 1 (affects Review activity and possible loops)",
                        "  - the close's class '…' and the opening's '…' disagree: 1 (affects Review activity and possible loops)",
                        "  - the close's class is a number: 1 (affects Review activity and possible loops)"],
           "coverage groups: %s" % cov[-4:])
    expect("- Lines under a historical event name (FIELDS.md): %d, each marked in the detail." % (n + 1) in main, "end-marker count")
    # The detail's class view: one line per class, every recorded string apart from every label.
    view = [(text, secs[i]) for i, (s, text) in enumerate(LABEL_STRINGS)] + [
        ("(class invalid)", 1000), ("(class conflicting)", 2000), ("(class unrecorded)", 3000)]
    expect(len(set(t for t, v in view)) == len(view), "PROBE FAILED: two expected class texts are equal")
    want_view = ["- %s: %s over 1 close%s" % (t, label_minutes(v), V0) for t, v in sorted(view)] + [
        "- (all): %s over %d closes (0 unknown or invalid; 0 named gaps (detail))" % (label_minutes(total), closes)]
    got = detail.split("\n")
    i = got.index("### By class")
    expect(got[i + 1:i + 1 + len(want_view)] == want_view, "class view:\n%s" % first_difference(got[i + 1:i + 1 + len(want_view)], want_view))
    for k, (s, text) in enumerate(LABEL_STRINGS):
        expect('| run-a:"C%02d":%d | %s | lane-open line %d,' % (k, 2 * k + 1, text, 2 * k + 1) in detail, "episode C%02d's class cell" % k)
    for key, label in (('run-b:"U1":1', "(class invalid)"), ('run-b:"U2":3', "(class conflicting)"), ('run-b:"U3":5', "(class unrecorded)")):
        expect("| %s | %s | lane-open" % (key, label) in detail, "%s's class cell" % key)
    # The end markers' helpers: each recorded lane as shown, the one with no lane by the label.
    first = 2 * n + n + 2 + 1
    want_hist = ["- run-a.jsonl:%d · 2026-10-08 08:%02d:00 +0100 · terminated · helper %s · an end marker, not a close"
                 % (first + k, k, json.dumps(s, ensure_ascii=True)) for k, (s, text) in enumerate(LABEL_STRINGS)] + [
        "- run-a.jsonl:%d · 2026-10-08 09:00:00 +0100 · terminated · helper (unusable) · an end marker, not a close" % (first + n)]
    expect(section(detail, "## Lines under a historical event name (named in every report)")[1:] == want_hist,
           "end-marker lines:\n%s" % first_difference(section(detail, "## Lines under a historical event name (named in every report)")[1:], want_hist))
    # The boundaries as recorded: from and to by repr, idle_src and head_denials_src as shown; absent or null as None.
    for k, (s, text) in enumerate(LABEL_STRINGS):
        line = ("- run-a.jsonl:%d · 2026-10-07 08:%02d:00 +0100 · from %r to %r · idle_min %d (%s) · over_cap_reports 0 · "
                "rewrites 0 (cumulative 0) · denials 0 · head_denials 0 (%s) · run_spend_usd 0" % (2 * n + 1 + k, k, s, s, k + 1, text, text))
        expect(line in got, "boundary line: %s" % line)
    for k, minutes in enumerate((100, 200)):
        expect("- run-a.jsonl:%d · 2026-10-07 09:%02d:00 +0100 · from 'a' to 'b' · idle_min %d (None) · over_cap_reports 0 · "
               "rewrites 0 (cumulative 0) · denials 0 · head_denials 0 (None) · run_spend_usd 0" % (3 * n + 1 + k, k, minutes) in got,
               "the boundary with idle_src %s" % ("absent", "null")[k])


# ------------------------------------------------------------------------ test 3 -----------

def oc(lane, open_ts, close_ts, dur, **extra):
    c = {"ts": close_ts, "event": "lane-closed", "lane": lane, "class": "builder", "harness": "codex",
         "exit_class": "completed", "duration_s": dur, "cost_src": "codex-plan", "total_cost_usd": None,
         "usage": {"input_tokens": 1, "output_tokens": 1, "calls": 1}, "usage_state": "complete",
         "usage_complete": True, "sandbox_denials": 0, "denials": {"tool": 0, "fence": 0, "sandbox": 0}}
    c.update(extra)
    return [{"ts": open_ts, "event": "lane-open", "lane": lane, "class": "builder", "harness": "codex"}, c]


@case(3, "endpoints-fractions-offsets")
def t3_endpoints(ctx):
    # [2026-10-05 00:00 +0100, 2026-10-12 00:00 +0100): E1 at the start (in, 10), E2 at
    # 23:59:59.999 (in, 20), E3 at the end (out), E4 half a second before the start (out), E5
    # 23:30 +0000 on the 4th = 00:30 +0100 on the 5th (in, 40), E6 23:30Z on the 11th = 00:30 +0100
    # on the 12th (out). In: 10+20+40 = 70 s (1.2 min). The next week holds E3 30 and E6 50 = 80 s.
    fx = Fx(ctx.root, "t3-endpoints", script=ctx.script)
    fx.write("run-e.jsonl",
             oc("E1", "2026-10-04T23:50:00+0100", "2026-10-05T00:00:00+0100", 10)
             + oc("E2", "2026-10-11T23:50:00+0100", "2026-10-11T23:59:59.999+0100", 20)
             + oc("E3", "2026-10-11T23:50:00+0100", "2026-10-12T00:00:00+0100", 30)
             + oc("E4", "2026-10-04T23:50:00+0100", "2026-10-04T23:59:59.5+0100", 5)
             + oc("E5", "2026-10-04T23:20:00+0000", "2026-10-04T23:30:00+0000", 40)
             + oc("E6", "2026-10-11T23:20:00Z", "2026-10-11T23:30:00Z", 50))
    code, out, err, main, detail = fx.report()
    m = as_map(rows_of(main))
    expect(m[(H, "total")] == ("70 s (1.2 min)", "complete", "3 closes: 3 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "week 1 %r" % (m[(H, "total")],))
    e2 = '| run-e:"E2":3 | builder | lane-open line 3, 2026-10-11 23:50:00 +0100 | lane-closed line 4, 2026-10-11 23:59:59.999 +0100 |'
    expect(e2 in detail, "E2 missing from week 1")
    code, out, err, main, detail = fx.report(since="2026-10-12", until="2026-10-19")
    m = as_map(rows_of(main))
    expect(m[(H, "total")][0] == "80 s (1.3 min)", "week 2 %r" % (m[(H, "total")],))
    expect(e2 not in detail, "E2 leaked into week 2")


@case(3, "sub-microsecond-fractions-rendered", cr5=4)
def t3_nanoseconds(ctx):
    # CR-WASTE5 finding 3: an accepted fraction of a second is kept when rendered, however small. N1, N2 and N3
    # close at 10:01:00.000000001, 10:02:00.0000001 and 10:03:00.123456789 on the 6th (10, 20 and 40 s), opened at
    # 10:00:00.000000001, .0000001 and .123456789; the B-WASTE14 version printed the first two as 10:01:00 and
    # 10:02:00 (the quotient in scientific notation, 1E-9 and 1E-7, then dropped). Beside them, the endpoint
    # controls, selected by the exact fraction: S1 closes one nanosecond after the start (in, 80 s), S0 one
    # before it (out, 160 s), Z1 one nanosecond before the end (in, 320 s) and Z0 one after it (out, 640 s).
    # Week 1: 10 + 20 + 40 + 80 + 320 = 470 s (470/60 = 7.83 -> 7.8 min) over 5 closes. The next week holds Z0
    # alone: 640 s (10.7 min).
    fx = Fx(ctx.root, "t3-nanoseconds", script=ctx.script)
    fx.write("run-ns.jsonl",
             oc("N1", "2026-10-06T10:00:00.000000001+0100", "2026-10-06T10:01:00.000000001+0100", 10)
             + oc("N2", "2026-10-06T10:00:00.0000001+0100", "2026-10-06T10:02:00.0000001+0100", 20)
             + oc("N3", "2026-10-06T10:00:00.123456789+0100", "2026-10-06T10:03:00.123456789+0100", 40))
    fx.write("run-ends.jsonl",
             oc("S1", "2026-10-04T23:00:00+0100", "2026-10-05T00:00:00.000000001+0100", 80)
             + oc("S0", "2026-10-04T23:00:00+0100", "2026-10-04T23:59:59.999999999+0100", 160)
             + oc("Z1", "2026-10-11T23:00:00+0100", "2026-10-11T23:59:59.999999999+0100", 320)
             + oc("Z0", "2026-10-11T23:00:00+0100", "2026-10-12T00:00:00.000000001+0100", 640))
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d: %s" % (code, last_line(err)))
    m = as_map(rows_of(main))
    expect(m[(H, "total")] == ("470 s (7.8 min)", "complete", "5 closes: 5 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "week 1 %r" % (m[(H, "total")],))
    for needle in (
            '| run-ns:"N1":1 | builder | lane-open line 1, 2026-10-06 10:00:00.000000001 +0100 | lane-closed line 2, 2026-10-06 10:01:00.000000001 +0100 | 10 |',
            '| run-ns:"N2":3 | builder | lane-open line 3, 2026-10-06 10:00:00.0000001 +0100 | lane-closed line 4, 2026-10-06 10:02:00.0000001 +0100 | 20 |',
            '| run-ns:"N3":5 | builder | lane-open line 5, 2026-10-06 10:00:00.123456789 +0100 | lane-closed line 6, 2026-10-06 10:03:00.123456789 +0100 | 40 |',
            '| run-ends:"S1":1 | builder | lane-open line 1, 2026-10-04 23:00:00 +0100 | lane-closed line 2, 2026-10-05 00:00:00.000000001 +0100 | 80 |',
            '| run-ends:"Z1":5 | builder | lane-open line 5, 2026-10-11 23:00:00 +0100 | lane-closed line 6, 2026-10-11 23:59:59.999999999 +0100 | 320 |',
            # The inventory's first and last events keep their fractions too (each record is unordered: its
            # second opening precedes its first close).
            "| run-ns.jsonl | read | %d | 6 | 2026-10-06 10:00:00.000000001 +0100 | 2026-10-06 10:03:00.123456789 +0100 | no | 0 | unordered |"
            % os.path.getsize(os.path.join(fx.records, "run-ns.jsonl")),
            "| run-ends.jsonl | read | %d | 8 | 2026-10-04 23:00:00 +0100 | 2026-10-12 00:00:00.000000001 +0100 | no | 0 | unordered |"
            % os.path.getsize(os.path.join(fx.records, "run-ends.jsonl"))):
        expect(needle in detail, "detail lacks: %s" % needle)
    for key in ("run-ends:S0:3", "run-ends:Z0:7"):
        expect("| %s |" % key not in detail, "%s counted in week 1" % key)
    code, out, err, main, detail = fx.report(since="2026-10-12", until="2026-10-19")
    m = as_map(rows_of(main))
    expect(m[(H, "total")][:2] == ("640 s (10.7 min)", "complete"), "week 2 %r" % (m[(H, "total")],))
    expect('| run-ends:"Z0":7 | builder | lane-open line 7, 2026-10-11 23:00:00 +0100 | lane-closed line 8, 2026-10-12 00:00:00.000000001 +0100 | 640 |'
           in detail, "Z0 in week 2, its fraction kept")


@case(3, "daylight-saving")
def t3_dst(ctx):
    # The week [2026-10-19 00:00 +0100, 2026-10-26 00:00 +0000) holds 169 hours; 01:30 on the
    # 25th happens twice (+0100 then +0000) and both closes count (60 + 60 = 120 s); a close at
    # 00:30 +0000 on the 26th is after the end. A start inside the repeated hour is refused.
    fx = Fx(ctx.root, "t3-dst", script=ctx.script)
    fx.write("run-dst.jsonl",
             oc("D1", "2026-10-25T01:29:00+0100", "2026-10-25T01:30:00+0100", 60)
             + oc("D2", "2026-10-25T01:29:00+0000", "2026-10-25T01:30:00+0000", 60)
             + oc("D3", "2026-10-26T00:29:00+0000", "2026-10-26T00:30:00+0000", 60))
    code, out, err, main, detail = fx.report(since="2026-10-19", until="2026-10-26")
    expect(code == 0, "exit %d" % code)
    expect("- Interval: [2026-10-19 00:00 +0100, 2026-10-26 00:00 +0000), local time (GMT/BST)." in main, "interval line")
    m = as_map(rows_of(main))
    expect(m[(H, "total")][0] == "120 s (2.0 min)", "dst total %r" % (m[(H, "total")],))
    expect("line 2, 2026-10-25 01:30:00 +0100" in detail and "line 4, 2026-10-25 01:30:00 +0000" in detail, "both 01:30 closes")
    code, out, err = fx.run("--since", "2026-10-25T01:30", "--until", "2026-10-26")
    expect(code == 2 and "ambiguous" in err, "ambiguous start: %d %s" % (code, err))


@case(3, "resumed-helper-distinct-episodes")
def t3_resumed(ctx):
    # R: 100, resumed 200, resumed 300: three episodes, 600 s over 3 closes for one helper.
    fx = Fx(ctx.root, "t3-resumed", script=ctx.script)
    evs = oc("R", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", 100)
    second = oc("R", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", 200)
    third = oc("R", "2026-10-06T10:40:00+0100", "2026-10-06T10:50:00+0100", 300)
    second[0]["event"] = third[0]["event"] = "lane-resumed"
    fx.write("run-r.jsonl", evs + second + third)
    code, out, err, main, detail = fx.report()
    m = as_map(rows_of(main))
    expect(m[(H, 'helper run-r/"R"')] == ("600 s (10.0 min)", "complete", "3 closes: 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "R %r" % (m[(H, 'helper run-r/"R"')],))
    expect(m[(F, "closes")][0] == "3", "closes")
    for key in ('run-r:"R":1', 'run-r:"R":3', 'run-r:"R":5'):
        expect("| %s |" % key in detail, "episode %s" % key)


@case(3, "identity-faults-stay-visible")
def t3_identity(ctx):
    # M has no close (named open). D closes twice (the second has no opening: a gap). X closes a
    # quarter second before its opening (a gap; the opening stays open). N's close has no lane, Z's
    # a number and Y's a blank one (each a gap; each opening stays open). Only D's first close
    # counts: 10 s, total unknown with 5 named gaps on the episode figures.
    fx = Fx(ctx.root, "t3-identity", script=ctx.script)
    evs = ([{"ts": "2026-10-06T09:00:00+0100", "event": "lane-open", "lane": "M", "class": "builder", "harness": "codex"}]
           + oc("D", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", 10)
           + [oc("D", "x", "2026-10-06T10:11:00+0100", 10)[1]]
           + oc("X", "2026-10-06T11:00:00.500+0100", "2026-10-06T11:00:00.250+0100", 1))
    n = oc("N", "2026-10-06T12:00:00+0100", "2026-10-06T12:10:00+0100", 7)
    del n[1]["lane"]
    z = oc("Z", "2026-10-06T12:00:00+0100", "2026-10-06T12:10:00+0100", 7)
    z[1]["lane"] = 5
    y = oc("Y", "2026-10-06T12:00:00+0100", "2026-10-06T12:10:00+0100", 7)
    y[1]["lane"] = " "
    fx.write("run-i.jsonl", evs + n + z + y)
    code, out, err, main, detail = fx.report()
    m = as_map(rows_of(main))
    expect(m[(H, "total")] == ("unknown; known subtotal 10 s (0.2 min)", "unknown",
                               "1 close: 1 timed, 0 not applicable, 0 unknown or invalid; 5 named gaps (detail)"),
           "total %r" % (m[(H, "total")],))
    # Lines: 1 M open; 2-3 D; 4 D's second close; 5-6 X; 7-8 N; 9-10 Z; 11-12 Y.
    for needle in ('- run-i.jsonl:4 "D" · 2026-10-06 10:11:00 +0100 · a close with no opening before it on the record',
                   '- run-i.jsonl:6 "X" · 2026-10-06 11:00:00.25 +0100 · a close timed before its opening (line 5)',
                   "- run-i.jsonl:8 · 2026-10-06 12:10:00 +0100 · no usable lane (absent)",
                   "- run-i.jsonl:10 · 2026-10-06 12:10:00 +0100 · no usable lane (a number)",
                   "- run-i.jsonl:12 · 2026-10-06 12:10:00 +0100 · no usable lane (a string)",
                   '- run-i:"M":1 · open · opened 2026-10-06 09:00:00 +0100 · no close on the record',
                   '- run-i:"X":5 · open · opened 2026-10-06 11:00:00.5 +0100 · no valid close on the record; line 6 closes it at an earlier time',
                   '- run-i:"N":7 · open · opened', '- run-i:"Z":9 · open · opened', '- run-i:"Y":11 · open · opened'):
        expect(needle in detail, "detail lacks: %s" % needle)
    expect("Episodes open or unresolved at acquisition: 5 (0 opened after the interval's end; 0 unresolved by an invalid close or opening)" in main, "open count")


@case(3, "undated-close-leaves-opening-unresolved", cr1=2)
def t3_undated_close(ctx):
    # L opens at 10:00 and its close's ts is "bad"; M opens at 10:10 and its close has no ts; N
    # opens and closes validly (60 s). A malformed close is not evidence that an opening resolved:
    # L and M stay named, unresolved, and their closes are named gaps of the episode figures (each
    # lies between dated neighbours on the 6th, inside the interval). Known: N's 60 s.
    fx = Fx(ctx.root, "t3-undated-close", script=ctx.script)
    lines = oc("L", "2026-10-06T10:00:00+0100", "bad", 30) + oc("M", "2026-10-06T10:10:00+0100", "x", 40)
    del lines[3]["ts"]
    fx.write("run-u.jsonl", lines + oc("N", "2026-10-06T10:20:00+0100", "2026-10-06T10:21:00+0100", 60))
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d %s" % (code, err))
    for needle in (
            '- run-u:"L":1 · unresolved · opened 2026-10-06 10:00:00 +0100 · line 2 closes it with no usable timestamp (\'bad\'): a malformed close is not evidence that the episode resolved · its record holds invalid lines',
            '- run-u:"M":3 · unresolved · opened 2026-10-06 10:10:00 +0100 · line 4 closes it with no usable timestamp (absent): a malformed close is not evidence that the episode resolved · its record holds invalid lines'):
        expect(needle in detail, "detail lacks: %s" % needle)
    expect("- Episodes open or unresolved at acquisition: 2 (0 opened after the interval's end; 2 unresolved by an invalid close or opening), named in the detail; such an episode counts nowhere until a valid close resolves it." in main,
           "open count")
    m = as_map(rows_of(main))
    expect(m[(H, "total")] == ("unknown; known subtotal 60 s (1.0 min)", "unknown",
                               "1 close: 1 timed, 0 not applicable, 0 unknown or invalid; 2 named gaps (detail)"),
           "total %r" % (m[(H, "total")],))
    expect(section(detail, "## Named gaps and the figures they affect") == [
        gl("run-u.jsonl:2 · time unknown", "no usable timestamp ('bad')", EPISODE_PARTS),
        gl("run-u.jsonl:4 · time unknown", "no usable timestamp (absent)", EPISODE_PARTS)], "named gaps")


@case(3, "undated-close-then-valid-close", cr1=2)
def t3_undated_then_valid(ctx):
    # L: an undated close, then a valid close (300 s): at most one close per episode, so the valid
    # close pairs with nothing and is named; the opening stays unresolved. R: an undated close,
    # then a resume and a valid close (600 s): the resumed episode counts; the first opening stays
    # unresolved. Known: 600 s; three named gaps (two undated closes, one unpaired close).
    fx = Fx(ctx.root, "t3-undated-then-valid", script=ctx.script)
    lines = (oc("L", "2026-10-06T10:00:00+0100", "bad", 30)
             + [oc("L", "x", "2026-10-06T10:05:00+0100", 300)[1]]
             + oc("R", "2026-10-06T10:10:00+0100", "bad", 30)
             + oc("R", "2026-10-06T10:20:00+0100", "2026-10-06T10:30:00+0100", 600))
    lines[5]["event"] = "lane-resumed"
    fx.write("run-v.jsonl", lines)
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d %s" % (code, err))
    for needle in (
            '- run-v:"L":1 · unresolved · opened 2026-10-06 10:00:00 +0100 · line 2 closes it with no usable timestamp (\'bad\'): a malformed close is not evidence that the episode resolved; line 3 closes it again · its record holds invalid lines',
            '- run-v:"R":4 · unresolved · opened 2026-10-06 10:10:00 +0100 · a later opening at line 6 replaced it without a valid close; line 5 closes it with no usable timestamp (\'bad\'): a malformed close is not evidence that the episode resolved · its record holds invalid lines',
            '| run-v:"R":6 | builder | lane-resumed line 6, 2026-10-06 10:20:00 +0100 | lane-closed line 7, 2026-10-06 10:30:00 +0100 | 600 |'):
        expect(needle in detail, "detail lacks: %s" % needle)
    expect('| run-v:"L":1 |' not in detail, "L counted as an episode")
    m = as_map(rows_of(main))
    expect(m[(H, "total")] == ("unknown; known subtotal 600 s (10.0 min)", "unknown",
                               "1 close: 1 timed, 0 not applicable, 0 unknown or invalid; 3 named gaps (detail)"),
           "total %r" % (m[(H, "total")],))
    expect(m[(F, "closes")] == ("unknown; known subtotal 1", "unknown", "3 named gaps (detail)"), "closes %r" % (m[(F, "closes")],))
    expect(section(detail, "## Named gaps and the figures they affect") == [
        gl("run-v.jsonl:2 · time unknown", "no usable timestamp ('bad')", EPISODE_PARTS),
        gl('run-v.jsonl:3 "L" · 2026-10-06 10:05:00 +0100',
           "a close after a close of this helper at line 2 with no usable timestamp ('bad'); not paired", EPISODE_PARTS),
        gl("run-v.jsonl:5 · time unknown", "no usable timestamp ('bad')", EPISODE_PARTS)], "named gaps")


@case(3, "historical-names-preserve-associations", cr1=6)
def t3_historical(ctx):
    # The store's historical sequences: a lane-open closed by `lane-close` (run-20260903-cost:5-6);
    # a close, `lane-resume`, then a close marked resume (run-20260904-mode:6-9); an opening followed
    # by `lane-aborted` (run-20260905-closeoutA:16-18); `spawn` and `close-out` (2-3 September);
    # `probe-open` and `probe-closed` (the probe ladders). Each pair reads as the writers' opening
    # and close, so 5 episodes close in the interval; their metric fields, absent under the writers'
    # names, are unknown, never inferred: one duration (2187 s; 2187/60 = 36.45 -> 36.4 half-even)
    # is known; every exit status and class is unknown. `lane-aborted` closes nothing: R2 stays
    # open with the marker noted.
    fx = Fx(ctx.root, "t3-historical", script=ctx.script)
    fx.write("run-hist-g.jsonl", [
        {"ts": "2026-10-06T23:26+0100", "event": "lane-open", "lane": "C-cost-1", "agent": "critic"},
        {"ts": "2026-10-06T23:53+0100", "event": "lane-close", "lane": "C-cost-1", "detail": "critic returned: 11 findings"},
        {"ts": "2026-10-07T12:31+0100", "event": "lane-open", "lane": "BUILD-M", "agent": "builder"},
        {"ts": "2026-10-07T13:11+0100", "event": "lane-closed", "lane": "BUILD-M", "tokens": 366209, "duration_s": 2187},
        {"ts": "2026-10-07T13:11+0100", "event": "lane-resume", "lane": "BUILD-M", "reason": "one defect found live"},
        {"ts": "2026-10-07T13:30+0100", "event": "lane-closed", "lane": "BUILD-M", "resume": True, "tokens": "unmetered"},
        {"ts": "2026-10-07T14:00:00+0100", "event": "lane-open", "lane": "R2", "class": "reflector"},
        {"ts": "2026-10-07T14:01+0100", "event": "lane-aborted", "lane": "R2"},
        {"ts": "2026-10-07T15:00+0100", "event": "spawn", "lane": "S1", "agent": "critic"},
        {"ts": "2026-10-07T15:10+0100", "event": "close-out", "lane": "S1", "metered": False},
        {"ts": "2026-10-07T15:20+0100", "event": "probe-open", "lane": "P1", "kind": "headless head session"},
        {"ts": "2026-10-07T15:21+0100", "event": "probe-closed", "lane": "P1", "exit": 0},
    ])
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d %s" % (code, err))
    expect('- run-hist-g:"C-cost-1":1 ·' not in detail, "C-cost-1 is still named open: its lane-close was ignored")
    for needle in (
            '| run-hist-g:"C-cost-1":1 | (class unrecorded) | lane-open line 1, 2026-10-06 23:26:00 +0100 | lane-close line 2 (historical name, read as lane-closed), 2026-10-06 23:53:00 +0100 | unknown (duration_s is not on the close) | unknown (exit_class is not on the close) |',
            '| run-hist-g:"BUILD-M":3 | (class unrecorded) | lane-open line 3, 2026-10-07 12:31:00 +0100 | lane-closed line 4, 2026-10-07 13:11:00 +0100 | 2187 | unknown (exit_class is not on the close) (later resumed) |',
            '| run-hist-g:"BUILD-M":5 | (class unrecorded) | lane-resume line 5 (historical name, read as lane-resumed), 2026-10-07 13:11:00 +0100 | lane-closed line 6, 2026-10-07 13:30:00 +0100 | unknown (duration_s is not on the close) |',
            '| run-hist-g:"S1":9 | (class unrecorded) | spawn line 9 (historical name, read as lane-open), 2026-10-07 15:00:00 +0100 | close-out line 10 (historical name, read as lane-closed), 2026-10-07 15:10:00 +0100 |',
            '| run-hist-g:"P1":11 | (class unrecorded) | probe-open line 11 (historical name, read as lane-open), 2026-10-07 15:20:00 +0100 | probe-closed line 12 (historical name, read as lane-closed), 2026-10-07 15:21:00 +0100 |',
            '- run-hist-g:"R2":7 · open · opened 2026-10-07 14:00:00 +0100 · no valid close on the record; line 8 records lane-aborted, a historical end marker that is not a close'):
        expect(needle in detail, "detail lacks: %s" % needle)
    expect(section(detail, "## Lines under a historical event name (named in every report)")[1:] == [
        '- run-hist-g.jsonl:2 · 2026-10-06 23:53:00 +0100 · lane-close · helper "C-cost-1" · read as lane-closed',
        '- run-hist-g.jsonl:5 · 2026-10-07 13:11:00 +0100 · lane-resume · helper "BUILD-M" · read as lane-resumed',
        '- run-hist-g.jsonl:8 · 2026-10-07 14:01:00 +0100 · lane-aborted · helper "R2" · an end marker, not a close',
        '- run-hist-g.jsonl:9 · 2026-10-07 15:00:00 +0100 · spawn · helper "S1" · read as lane-open',
        '- run-hist-g.jsonl:10 · 2026-10-07 15:10:00 +0100 · close-out · helper "S1" · read as lane-closed',
        '- run-hist-g.jsonl:11 · 2026-10-07 15:20:00 +0100 · probe-open · helper "P1" · read as lane-open',
        '- run-hist-g.jsonl:12 · 2026-10-07 15:21:00 +0100 · probe-closed · helper "P1" · read as lane-closed'], "historical lines")
    m = as_map(rows_of(main))
    for key, want in (((H, "total"), ("unknown; known subtotal 2187 s (36.4 min)", "unknown",
                                      "5 closes: 1 timed, 0 not applicable, 4 unknown or invalid; " + GAPS0)),
                      ((F, "closes"), ("5", "complete", GAPS0)),
                      ((F, "status unknown or invalid"), ("5", "complete", "no usable exit_class")),
                      ((F, "non-completed, later resumed"), ("unknown; known subtotal 0", "unknown", LATER)),
                      ((RV, "reviewing-class episodes"), ("unknown; known subtotal 0", "unknown", RVC_COV % ("5 closes", GAPS0)))):
        expect(m[key] == want, "%s: %r" % (" / ".join(key), m[key]))
    expect("- Lines under a historical event name (FIELDS.md): 7, each marked in the detail." in main, "historical count")
    expect("- Episodes open or unresolved at acquisition: 1 (0 opened after the interval's end; 0 unresolved by an invalid close or opening)" in main, "open count")


# ------------------------------------------------------------------------ test 4 -----------

@case(4, "record-without-run-open-and-boundary-only-run")
def t4_attended(ctx):
    # An attended record with lanes and no run-open counts like any other (one 30 s close); a
    # boundary-only run with run-open contributes its boundary (idle 4) and no episode.
    fx = Fx(ctx.root, "t4-attended", script=ctx.script)
    fx.write("run-attended.jsonl", oc("A", "2026-10-06T10:00:00+0100", "2026-10-06T10:00:30+0100", 30))
    fx.write("run-bonly.jsonl", [
        {"ts": "2026-10-06T09:00:00+0100", "event": "run-open", "session": "s", "session_kind": "head"},
        {"ts": "2026-10-06T11:00:00+0100", "event": "phase-boundary", "idle_min": 4, "idle_src": "transcript",
         "over_cap_reports": 0, "rewrites": 0, "head_denials": 0, "denials": 0}])
    code, out, err, main, detail = fx.report()
    m = as_map(rows_of(main))
    expect(m[(H, "total")][0] == "30 s (0.5 min)", "attended %r" % (m[(H, "total")],))
    expect(m[(B, "boundary events")][0] == "1" and m[(B, "recorded idle, idle_src transcript")][0] == "4 min", "boundary-only")
    expect("- Records read: 2 with events in the interval, 0 outside it; 1 without run-open (counted like any other)." in main, "coverage")
    expect("Runs open at acquisition: 1." in main, "open run")


@case(4, "old-open-and-opening-after-interval")
def t4_open(ctx):
    # An opening 60 days before the interval and one after its end are both named, in a report
    # of any interval, and neither counts.
    fx = Fx(ctx.root, "t4-open", script=ctx.script)
    fx.write("run-o.jsonl", [
        {"ts": "2026-08-06T10:00:00+0100", "event": "lane-open", "lane": "OLD", "class": "builder"},
        {"ts": "2026-10-20T10:00:00+0100", "event": "lane-open", "lane": "NEW", "class": "builder"}])
    for since, until in ((SINCE, UNTIL), ("2026-11-02", "2026-11-09")):
        code, out, err, main, detail = fx.report(since=since, until=until)
        expect('- run-o:"OLD":1 · open · opened 2026-08-06 10:00:00 +0100 · no close on the record' in detail, "old open %s" % until)
        expect('- run-o:"NEW":2 · open · opened 2026-10-20 10:00:00 +0100 · no close on the record%s' % (
            " · opened after the interval's end" if until == UNTIL else "") in detail, "new open %s" % until)
    code, out, err, main, detail = fx.report()
    expect("Episodes open or unresolved at acquisition: 2 (1 opened after the interval's end; 0 unresolved by an invalid close or opening)" in main, "counts")


@case(4, "malformed-empty-and-invalid-timestamps")
def t4_malformed(ctx):
    # run-bad.jsonl: a dated close (5 s), then an unparsable line, a line with no event, a misspelt
    # event, and closes stamped with hour 25, minute 60, offset +99:99, no offset and a space for
    # the T; then a dated close (6 s). Its dated lines are in order, so each undated line lies
    # between 10:00 and 12:00 on the 6th and reaches this interval: every figure is unknown, and
    # the two dated closes give the known subtotal 11 s. run-empty.jsonl holds nothing and is named.
    fx = Fx(ctx.root, "t4-malformed", script=ctx.script)
    good = oc("G", "2026-10-06T09:59:00+0100", "2026-10-06T10:00:00+0100", 5)
    good2 = oc("G2", "2026-10-06T11:59:00+0100", "2026-10-06T12:00:00+0100", 6)
    lines = good + ['{"ts": "2026-10-06T10:30:00+0100", "event": "lane-cl', '{"ts": "2026-10-06T10:31:00+0100"}',
                    {"ts": "2026-10-06T10:32:00+0100", "event": "lane-clsoed", "lane": "G"}]
    for bad_ts in ("2026-10-06T25:00:00+0100", "2026-10-06T10:60:00+0100", "2026-10-06T10:00:00+9999",
                   "2026-10-06T10:00:00", "2026-10-06 10:00:00+0100"):
        lines.append({"ts": bad_ts, "event": "lane-closed", "lane": "Q"})
    fx.write("run-bad.jsonl", lines + good2)
    open(os.path.join(fx.records, "run-empty.jsonl"), "w").close()
    code, out, err, main, detail = fx.report()
    m = as_map(rows_of(main))
    expect(m[(H, "total")][0] == "unknown; known subtotal 11 s (0.2 min)", "total %r" % (m[(H, "total")],))
    expect(m[(B, "boundary events")] == ("unknown; known subtotal 0", "unknown", "counted at their own timestamps; 3 named gaps (detail)"),
           "boundaries %r" % (m[(B, "boundary events")],))
    for needle in ("run-bad.jsonl:3 · not JSON", "run-bad.jsonl:4 · no event name (absent)",
                   "run-bad.jsonl:5 · an event name outside the known list ('lane-clsoed')",
                   "run-bad.jsonl:6 · no usable timestamp ('2026-10-06T25:00:00+0100')",
                   "run-bad.jsonl:7 · no usable timestamp ('2026-10-06T10:60:00+0100')",
                   "run-bad.jsonl:8 · no usable timestamp ('2026-10-06T10:00:00+9999')",
                   "run-bad.jsonl:9 · no usable timestamp ('2026-10-06T10:00:00')",
                   "run-bad.jsonl:10 · no usable timestamp ('2026-10-06 10:00:00+0100')",
                   "run-bad.jsonl:3 · not JSON · kind unknown · between 2026-10-06 10:00:00 +0100 and 2026-10-06 10:31:00 +0100 · reaches this interval",
                   "run-bad.jsonl:7 · no usable timestamp ('2026-10-06T10:60:00+0100') · kind lane-closed · between 2026-10-06 10:32:00 +0100 and 2026-10-06 11:59:00 +0100 · reaches this interval",
                   "| run-empty.jsonl | empty |"):
        expect(needle in detail, "detail lacks: %s" % needle)
    expect("- Records holding invalid or undated lines: 1, each named in the detail in every report until mended." in main, "bad count")
    # The same damage is named in a later week's report but reaches none of its figures.
    code, out, err, main, detail = fx.report(since="2026-11-02", until="2026-11-09")
    m = as_map(rows_of(main))
    expect(m[(H, "total")][0] == "0 s (0.0 min)" and m[(H, "total")][1] == "complete", "later week %r" % (m[(H, "total")],))
    expect("run-bad.jsonl:6 · no usable timestamp" in detail and "outside this interval" in detail, "named later")


@case(4, "event-ts-lane-null-and-wrong-type", cr3=3)
def t4_null_kinds(ctx):
    # CR-WASTE3 finding 3, the structural fields' cells: run-n.jsonl holds a valid 60 s episode (lines
    # 1-2), then a line whose event is null (3) and one whose event is a number (4), each of unknown
    # kind and so feeding every figure; two closes whose ts is null (5) and a number (6), undated
    # between 10:06 and 10:07 and so in this interval, feeding the episode parts; and an opening whose
    # lane is null (7). Five named gaps; helper time known only as its 60 s subtotal.
    fx = Fx(ctx.root, "t4-null-kinds", script=ctx.script)
    fx.write("run-n.jsonl", oc("N", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60) + [
        {"ts": "2026-10-06T10:05:00+0100", "event": None},
        {"ts": "2026-10-06T10:06:00+0100", "event": 5},
        {"ts": None, "event": "lane-closed", "lane": "U"},
        {"ts": 5, "event": "lane-closed", "lane": "U"},
        {"ts": "2026-10-06T10:07:00+0100", "event": "lane-open", "lane": None, "class": "builder"}])
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d %s" % (code, err))
    expect(section(detail, "## Named gaps and the figures they affect") == [
        "- run-n.jsonl:3 · 2026-10-06 10:05:00 +0100 · no event name (null) · affects: every figure",
        "- run-n.jsonl:4 · 2026-10-06 10:06:00 +0100 · no event name (a number) · affects: every figure",
        gl("run-n.jsonl:5 · time unknown", "no usable timestamp (None)", EPISODE_PARTS),
        gl("run-n.jsonl:6 · time unknown", "no usable timestamp (5)", EPISODE_PARTS),
        gl("run-n.jsonl:7 · 2026-10-06 10:07:00 +0100", "no usable lane (null)", EPISODE_PARTS)],
        "named gaps:\n%s" % "\n".join(section(detail, "## Named gaps and the figures they affect")))
    m = as_map(rows_of(main))
    expect(m[(H, "total")] == ("unknown; known subtotal 60 s (1.0 min)", "unknown",
                               "1 close: 1 timed, 0 not applicable, 0 unknown or invalid; 5 named gaps (detail)"),
           "total %r" % (m[(H, "total")],))
    expect("- Records holding invalid or undated lines: 1, each named in the detail in every report until mended." in main, "bad count")


@case(4, "event-array-or-object-named", cr4=1)
def t4_event_kinds(ctx):
    # CR-WASTE4 finding 1: a line whose event is an array or an object is an invalid line, named, and
    # the report completes. run-n.jsonl opens with the review's own line (an empty array, 10:00), then
    # a valid 60 s episode (lines 2-3), an empty object (4), an array holding a close's name (5) and
    # an object holding one (6): four lines of unknown kind, each feeding every figure of run run-n
    # (no usable lane or class, so every helper and class). run-v.jsonl holds an independent 30 s
    # episode: its run and helper rows stay complete. Every other total reads unknown with its known
    # subtotal: 60 + 30 = 90 s (1.5 min) over 2 closes, plan tokens 1 + 1 = 2 each way; 4 named gaps.
    fx = Fx(ctx.root, "t4-event-kinds", script=ctx.script)
    fx.write("run-n.jsonl", ['{"ts":"2026-10-06T10:00:00+0100","event":[]}']
             + oc("N", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60)
             + [{"ts": "2026-10-06T10:05:00+0100", "event": {}},
                {"ts": "2026-10-06T10:06:00+0100", "event": ["lane-closed"], "lane": "N"},
                {"ts": "2026-10-06T10:07:00+0100", "event": {"name": "lane-closed"}, "lane": "N"}])
    fx.write("run-v.jsonl", oc("V", "2026-10-06T10:00:00+0100", "2026-10-06T10:00:30+0100", 30))
    code, out, err, main, detail = fx.report()
    expect(code == 0 and main is not None and detail is not None,
           "exit %d, report written %s, detail written %s: %s" % (code, main is not None, detail is not None, err.strip()[-300:]))
    expect(section(detail, "## Named gaps and the figures they affect") == [
        "- run-n.jsonl:1 · 2026-10-06 10:00:00 +0100 · no event name (a list) · affects: every figure",
        "- run-n.jsonl:4 · 2026-10-06 10:05:00 +0100 · no event name (an object) · affects: every figure",
        "- run-n.jsonl:5 · 2026-10-06 10:06:00 +0100 · no event name (a list) · affects: every figure",
        "- run-n.jsonl:6 · 2026-10-06 10:07:00 +0100 · no event name (an object) · affects: every figure"],
        "named gaps:\n%s" % "\n".join(section(detail, "## Named gaps and the figures they affect")))
    for n, kind, at in ((1, "a list", "10:00"), (4, "an object", "10:05"), (5, "a list", "10:06"), (6, "an object", "10:07")):
        line = ("- run-n.jsonl:%d · no event name (%s) · kind unknown · its own time 2026-10-06 %s:00 +0100 · reaches this "
                "interval" % (n, kind, at))
        expect(line in detail.split("\n"), "detail lacks: %s" % line)
    expect("- Records holding invalid or undated lines: 1, each named in the detail in every report until mended." in main, "bad count")
    expect("  - no event name: 4 (affects Helper time, Failed closes, Review activity and possible loops, Phase boundaries, "
           "Refusals, Priced spend)" in main.split("\n"), "the coverage's gap line")
    g4, u0 = gn(4), "unknown; known subtotal 0"
    ch = "2 closes: 2 known, 0 not applicable, 0 unknown or invalid; " + g4
    want = {
        (H, "total"): ("unknown; known subtotal 90 s (1.5 min)", "unknown", "2 closes: 2 timed, 0 not applicable, 0 unknown or invalid; " + g4),
        (H, "run run-n"): ("unknown; known subtotal 60 s (1.0 min)", "unknown", "1 close: 0 not applicable, 0 unknown or invalid; " + g4),
        (H, "run run-v"): ("30 s (0.5 min)", "complete", VIEW),
        (H, "class builder"): ("unknown; known subtotal 90 s (1.5 min)", "unknown", "2 closes: 0 not applicable, 0 unknown or invalid; " + g4),
        (H, 'helper run-n/"N"'): ("unknown; known subtotal 60 s (1.0 min)", "unknown", "1 close: 0 not applicable, 0 unknown or invalid; " + g4),
        (H, 'helper run-v/"V"'): ("30 s (0.5 min)", "complete", VIEW),
        (F, "closes"): ("unknown; known subtotal 2", "unknown", g4),
        (F, "completed"): ("unknown; known subtotal 2", "unknown", "exit_class completed"),
        (F, "non-completed"): (u0, "unknown", NONCOMP % (0, 0, g4)),
        (F, "status unknown or invalid"): (u0, "unknown", "no usable exit_class"),
        (F, "non-completed, later resumed"): (u0, "unknown", LATER),
        (RV, "reviewing-class episodes"): (u0, "unknown", RVC_COV % ("0 closes", g4)),
        (RV, "evidenced item associations"): EVID[2:],
        (RV, "positional candidate groups"): (u0, "unknown", GROUPS_COV % g4),
        (RV, "reviewing-class episodes with no positional group"): (u0, "unknown", NOGROUP_COV),
        (RV, "candidate groups with two or more reviewing-class episodes"): (u0, "unknown", MULTI_COV),
        (RV, "rounds"): ROUNDS[2:],
        (B, "boundary events"): (u0, "unknown", "counted at their own timestamps; " + g4),
        (B, "recorded idle unknown"): (u0, "unknown", IDLEU_COV),
        (B, "over-cap reports"): (u0, "unknown", OVER_COV % "0 boundaries"),
        (B, "rewrites (deltas)"): (u0, "unknown", REW_COV % "0 boundaries"),
        (B, "cumulative rewrites snapshots"): (u0, "unknown", BS_COV % 0),
        (RF, "helper tool"): (u0, "unknown", ch),
        (RF, "helper fence"): (u0, "unknown", ch),
        (RF, "helper sandbox"): (u0, "unknown", ch),
        (RF, "head fence (boundaries)"): (u0, "unknown", HF_COV % ("0 boundaries", 0, g4)),
        (RF, "boundary summary of helper tool refusals"): (u0, "unknown", HS_COV % ("0 boundaries", g4)),
        SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 0, 0, g4)),
        SP_PC: ("unknown; known subtotal 2", "unknown", PLAN_COV % (2, 0, 0, 0, 0, 0)),
        SP_TCI: tok(2, 2, 0, tc(2), gaps=4),
        SP_TCO: tok(2, 2, 0, tc(2), gaps=4),
        SP_TII: tok(0, 0, 0, ti(0), gaps=4),
        SP_TIO: tok(0, 0, 0, ti(0), gaps=4),
        SP_UN: (u0, "unknown", "token totals only; no dollar figure"),
        SP_NA: (u0, "unknown", "exit_class spawn-failed"),
        SP_HB: (u0, "unknown", "plan usage or no process"),
        SP_SS: (u0, "unknown", SS_COV % 0),
    }
    e = compare_map(rows_of(main), want)
    expect(e is None, e)


@case(4, "lane-awake-feeds-no-figure")
def t4_lane_awake(ctx):
    # The keep-awake line both wrappers write after lane-spawned (or lane-respawned), as lane.py and codex-lane.py
    # write it (lane.py's AWAKE_EVENT, start_awake's fields: awake, caffeinate_pid, watched_pid, command, note), is
    # a known event that feeds no figure: it opens, closes and resolves nothing and no gap is named for it. A's
    # Claude pass (60 s) beside a started keep-awake line, B's GPT-6 Astra pass (30 s) beside a skipped one, and
    # C's keep-awake line after its opening with no close, so C stays open. Helper time 60 + 30 = 90 s (1.5 min)
    # over 2 closes, complete; 1 episode open; no invalid line; no named gap.
    fx = Fx(ctx.root, "t4-lane-awake", script=ctx.script)
    den = {"tool": 0, "fence": 0, "sandbox": 0}
    awake = lambda ts, lane, pid, **kw: dict({"ts": ts, "run": "run-w", "lane": lane, "event": "lane-awake",
                                              "session_id": "s-" + lane, "wrapper_pid": 9, "class": "builder",
                                              "detached": False, "watched_pid": pid,
                                              "command": ["/usr/bin/caffeinate", "-i", "-w", str(pid)]}, **kw)
    fx.write("run-w.jsonl", [
        {"ts": "2026-10-06T10:00:00+0100", "run": "run-w", "lane": "A", "event": "lane-open", "class": "builder", "session_id": "s-A"},
        {"ts": "2026-10-06T10:00:01+0100", "run": "run-w", "lane": "A", "event": "lane-spawned", "class": "builder", "pid": 11},
        awake("2026-10-06T10:00:01+0100", "A", 11, awake="started", caffeinate_pid=12,
              note="caffeinate pid 12 holds an idle-sleep assertion until pid 11 exits"),
        {"ts": "2026-10-06T10:01:00+0100", "run": "run-w", "lane": "A", "event": "lane-closed", "class": "builder",
         "session_id": "s-A", "exit_class": "completed", "duration_s": 60, "cost_src": "result", "total_cost_usd": Raw("0.50"),
         "denials": den, "usage": fixture_inventory(Raw("0.50"))},
        {"ts": "2026-10-06T10:00:00+0100", "run": "run-w", "lane": "B", "event": "lane-open", "harness": "codex", "class": "builder"},
        {"ts": "2026-10-06T10:00:02+0100", "run": "run-w", "lane": "B", "event": "lane-spawned", "harness": "codex", "class": "builder", "pid": 21},
        awake("2026-10-06T10:00:02+0100", "B", 21, harness="codex", awake="skipped", caffeinate_pid=None,
              note="no caffeinate at /usr/bin/caffeinate (another platform, or a missing binary): the host may sleep while pid 21 "
                   "runs, and a sleep reads as silence"),
        {"ts": "2026-10-06T10:00:30+0100", "run": "run-w", "lane": "B", "event": "lane-closed", "harness": "codex", "class": "builder",
         "exit_class": "completed", "duration_s": 30, "cost_src": "codex-plan", "total_cost_usd": None,
         "usage": {"input_tokens": 1, "output_tokens": 1, "calls": 1}, "usage_complete": True, "usage_state": "complete",
         "sandbox_denials": 0, "denials": den},
        {"ts": "2026-10-06T11:00:00+0100", "run": "run-w", "lane": "C", "event": "lane-open", "class": "builder"},
        {"ts": "2026-10-06T11:00:01+0100", "run": "run-w", "lane": "C", "event": "lane-spawned", "class": "builder", "pid": 31},
        awake("2026-10-06T11:00:01+0100", "C", 31, awake="started", caffeinate_pid=32,
              note="caffeinate pid 32 holds an idle-sleep assertion until pid 31 exits")])
    code, out, err, main, detail = fx.report()
    expect(code == 0 and main is not None and detail is not None, "exit %d: %s" % (code, last_line(err)))
    gaps = section(detail, "## Named gaps and the figures they affect")
    expect(gaps == ["- none"], "named gaps:\n%s" % "\n".join(gaps))
    m = as_map(rows_of(main))
    expect(m[(H, "total")] == ("90 s (1.5 min)", "complete", "2 closes: 2 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "helper time %r" % (m[(H, "total")],))
    expect(m[(F, "closes")][:2] == ("2", "complete") and m[SP_T][:2] == ("$0.50", "complete"), "closes %r, priced %r" % (m[(F, "closes")], m[SP_T]))
    for line in ("- Records holding invalid or undated lines: 0, each named in the detail in every report until mended.",
                 "- Episodes open or unresolved at acquisition: 1 (0 opened after the interval's end; 0 unresolved by an "
                 "invalid close or opening), named in the detail; such an episode counts nowhere until a valid close resolves it."):
        expect(line in main.split("\n"), "main report lacks: %s" % line)
    expect("lane-awake" not in "\n".join(section(detail, "## Records holding invalid or undated lines (named in every report)")),
           "a keep-awake line is named invalid")


@case(4, "stop-requested-feeds-no-figure")
def t4_stop_requested(ctx):
    # The line lane.py writes when a stop is asked of a running pass (a3_request_stop: run, lane, pass_id and its
    # intent, with cause, reason, explicit, ts and requester) is a known event that feeds no figure: it opens, closes
    # and resolves nothing and no gap is named for it (B-WW1's proposed first hunk). A's pass (60 s, $0.50) beside a
    # stop asked of it before its close; B's opening with a stop asked and no close, so B stays open. Helper time
    # 60 s over 1 close, complete; priced $0.50, complete; 1 episode open; no invalid line; no named gap.
    fx = Fx(ctx.root, "t4-stop-requested", script=ctx.script)
    stop = lambda ts, lane, pass_id: {"event": "stop-requested", "ts": ts, "run": "run-q", "lane": lane, "pass_id": pass_id,
                                      "intent": {"cause": "deadline", "reason": "past its deadline", "explicit": False,
                                                 "ts": ts, "requester": {"pid": 9, "start": "x"}}}
    fx.write("run-q.jsonl", priced_episode("A", "2026-10-06T10:01:00+0100")[:1]
             + [stop("2026-10-06T10:00:30+0100", "A", "p-A")] + priced_episode("A", "2026-10-06T10:01:00+0100")[1:]
             + [{"ts": "2026-10-06T11:00:00+0100", "event": "lane-open", "lane": "B", "class": "builder"},
                stop("2026-10-06T11:00:30+0100", "B", "p-B")])
    code, out, err, main, detail = fx.report()
    expect(code == 0 and main is not None and detail is not None, "exit %d: %s" % (code, last_line(err)))
    gaps = section(detail, "## Named gaps and the figures they affect")
    expect(gaps == ["- none"], "named gaps:\n%s" % "\n".join(gaps))
    m = as_map(rows_of(main))
    expect(m[(H, "total")] == ("60 s (1.0 min)", "complete", "1 close: 1 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "helper time %r" % (m[(H, "total")],))
    expect(m[SP_T][:2] == ("$0.50", "complete"), "priced %r" % (m[SP_T],))
    for line in ("- Records holding invalid or undated lines: 0, each named in the detail in every report until mended.",
                 "- Episodes open or unresolved at acquisition: 1 (0 opened after the interval's end; 0 unresolved by an "
                 "invalid close or opening), named in the detail; such an episode counts nowhere until a valid close resolves it."):
        expect(line in main.split("\n"), "main report lacks: %s" % line)


@case(4, "ordered-and-unordered-undated")
def t4_undated(ctx):
    # run-ordered.jsonl: an undated close between two September lines: outside this interval. unordered:
    # an undated close in a record whose dated lines run backwards: it reaches every interval.
    fx = Fx(ctx.root, "t4-undated", script=ctx.script)
    fx.write("run-ordered.jsonl", [
        {"ts": "2026-09-01T10:00:00+0100", "event": "observation"},
        {"ts": "bad", "event": "lane-closed", "lane": "U"},
        {"ts": "2026-09-02T10:00:00+0100", "event": "observation"}])
    code, out, err, main, detail = fx.report()
    m = as_map(rows_of(main))
    expect(m[(H, "total")][1] == "complete", "ordered reached %r" % (m[(H, "total")],))
    expect("run-ordered.jsonl:2 · no usable timestamp ('bad') · kind lane-closed · between 2026-09-01 10:00:00 +0100 and 2026-09-02 10:00:00 +0100 · outside this interval" in detail,
           "ordered span")
    fx.write("run-unordered.jsonl", [
        {"ts": "2026-09-02T10:00:00+0100", "event": "observation"},
        {"ts": "bad", "event": "lane-closed", "lane": "U"},
        {"ts": "2026-09-01T10:00:00+0100", "event": "observation"}])
    code, out, err, main, detail = fx.report()
    m = as_map(rows_of(main))
    expect(m[(H, "total")] == ("unknown; known subtotal 0 s (0.0 min)", "unknown",
                               "0 closes: 0 timed, 0 not applicable, 0 unknown or invalid; 1 named gap (detail)"),
           "unordered %r" % (m[(H, "total")],))
    expect(m[(B, "boundary events")][1] == "complete", "an undated close does not reach the boundary figure")
    expect("any time (its record's dated lines are not in order) · reaches this interval" in detail, "unordered span")


@case(4, "unreadable-files-named", cr3=1)
def t4_unreadable(ctx):
    # run-locked.jsonl cannot be read and run-dir.jsonl is a folder, not a regular file (the input
    # contract: never opened): both named in every report, every figure unknown; the readable control
    # still counts.
    # A name gone between the listing and the read is T4.file-disappearing-during-acquisition; a
    # symbolic link (never followed) is T5.links-never-followed.
    fx = Fx(ctx.root, "t4-unreadable", script=ctx.script)
    fx.write("run-control.jsonl", oc("C", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60))
    locked = fx.write("run-locked.jsonl", oc("L", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60))
    os.makedirs(os.path.join(fx.records, "run-dir.jsonl"))
    os.chmod(locked, 0)
    try:
        code, out, err, main, detail = fx.report(since="2026-11-02", until="2026-11-09")
    finally:
        os.chmod(locked, 0o644)
    m = as_map(rows_of(main))
    expect(m[(H, "total")] == ("unknown; known subtotal 0 s (0.0 min)", "unknown",
                               "0 closes: 0 timed, 0 not applicable, 0 unknown or invalid; 2 named gaps (detail)"),
           "total %r" % (m[(H, "total")],))
    expect("| run-dir.jsonl | %s |" % NOT_REGULAR_CELL in detail, "the folder is not named as not a regular file")
    expect("| run-locked.jsonl | unreadable: cannot be read (Permission denied) |" in detail, "locked")
    expect("| run-control.jsonl | read |" in detail, "control read")
    expect("named in every report" in detail, "every report")


@case(4, "file-disappearing-during-acquisition")
def t4_disappearing(ctx):
    # In process: the listing returns three names and one file is removed before it is read.
    fx = Fx(ctx.root, "t4-vanish", script=ctx.script)
    fx.write("run-va.jsonl", oc("A", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60))
    victim = fx.write("run-vb.jsonl", oc("B", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60))
    fx.write("run-vc.jsonl", oc("C", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60))
    mod = reader_module(ctx.script, "ww_inprocess")
    real = os.listdir

    def listing(path):
        names = real(path)
        if os.path.realpath(path) == os.path.realpath(fx.records) and os.path.exists(victim):
            os.unlink(victim)
        return names
    os.listdir = listing
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = mod.main(["--records", fx.records, "--tools-dir", fx.tools, "--since", SINCE, "--until", UNTIL])
    finally:
        os.listdir = real
    detail = open(os.path.join(fx.tools, "reports", "waste-detail-2026-10-12.md"), encoding="utf-8").read()
    main = open(os.path.join(fx.tools, "reports", "waste-report-2026-10-12.md"), encoding="utf-8").read()
    expect(code == 0, "exit %r" % code)
    expect("| run-vb.jsonl | gone: listed, then gone before it could be read |" in detail, "gone named")
    m = as_map(rows_of(main))
    expect(m[(H, "total")][0] == "unknown; known subtotal 120 s (2.0 min)", "total %r" % (m[(H, "total")],))


@case(4, "empty-interval-versus-empty-store")
def t4_empty(ctx):
    # Records with nothing in the interval: a measured zero, exit 0. An empty or missing or
    # unreadable records folder: a failed premise, exit 2, nothing written.
    fx = Fx(ctx.root, "t4-empty", script=ctx.script)
    fx.write("run-old.jsonl", oc("O", "2026-09-06T10:00:00+0100", "2026-09-06T10:01:00+0100", 60))
    code, out, err, main, detail = fx.report()
    m = as_map(rows_of(main))
    expect(code == 0 and m[(H, "total")] == ("0 s (0.0 min)", "complete",
                                             "0 closes: 0 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "measured zero %r" % (m[(H, "total")],))
    expect(m[(F, "closes")][:2] == ("0", "complete"), "no closes")
    empty = Fx(ctx.root, "t4-empty-store", script=ctx.script)
    before = tree_manifest(empty.tools)
    code, out, err, main, detail = empty.report()
    expect(code == 2 and "PROBE FAILED: no candidate record" in err and main is None, "empty store %d %s" % (code, err))
    code, out, err = empty.run("--since", SINCE, "--until", UNTIL, records=os.path.join(empty.dir, "absent"))
    expect(code == 2 and "PROBE FAILED: no records folder" in err, "missing folder %d %s" % (code, err))
    os.chmod(empty.records, 0)
    try:
        code, out, err = empty.run("--since", SINCE, "--until", UNTIL)
    finally:
        os.chmod(empty.records, 0o755)
    expect(code == 2 and "cannot be listed" in err, "unreadable folder %d %s" % (code, err))
    expect(tree_manifest(empty.tools) == before, "a failed premise wrote something")
    code, out, err = fx.run("--since", UNTIL, "--until", UNTIL)
    expect(code == 2 and "empty interval" in err, "empty interval %d %s" % (code, err))


@case(4, "no-admitted-record-is-a-failed-premise", finding=1, cr3=1)
def t4_none_admitted(ctx):
    # Under the input contract only the five pinned event logs are not admitted: a folder holding nothing else,
    # however record-like their contents, has an empty inventory of run records, a failed premise
    # (exit 2, nothing written), and no file is opened (each guarded). Adding one record under any
    # other name, here one without the run- prefix, makes the same folder a valid inventory.
    fx = Fx(ctx.root, "t4-none-admitted", script=ctx.script)
    refs = [fx.write(n, oc("Q", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60)) for n in PINNED]
    before = tree_manifest(fx.tools)
    code, out, err, opened = guarded_run(ctx, fx, refs)
    expect(code == 2 and "PROBE FAILED: no admitted run record" in err and "FORBIDDEN" not in err,
           "no admitted record: %d %s" % (code, err.strip()[-300:]))
    expect(not [o for o in opened if o.startswith(os.path.realpath(fx.records) + os.sep)],
           "a file in the records folder was opened: %s" % opened)
    expect(tree_manifest(fx.tools) == before, "a failed premise wrote something")
    fx.write("notes.jsonl", oc("Y", "2026-10-06T10:00:00+0100", "2026-10-06T10:00:30+0100", 30))
    code, out, err, opened = guarded_run(ctx, fx, refs)
    expect(code == 0 and "FORBIDDEN" not in err, "with one admitted record: %d %s" % (code, err.strip()[-300:]))
    main = open(os.path.join(fx.tools, "reports", "waste-report-2026-10-12.md"), encoding="utf-8").read()
    expect(as_map(rows_of(main))[(H, "total")][:2] == ("30 s (0.5 min)", "complete"), "the admitted record's 30 s")


def reached_by_unknown_lines(closes, secs, usd, g, views_rows):
    """The full table when CLOSES valid closes like K (together SECS of helper time and USD priced) sit
    beside G lines of unknown kind in another run (FIELDS.md, "Scope of a gap": such a line feeds every
    part of its own run, every helper and every class): every total reads unknown with its known
    subtotal; VIEWS_ROWS holds the helper-time view rows, fixed by the case."""
    G, u0 = gn(g), "unknown; known subtotal 0"
    ch = "%s: %d known, 0 not applicable, 0 unknown or invalid; %s" % (pl(closes, "close"), closes, G)
    out = {
        (H, "total"): ("unknown; known subtotal " + secs, "unknown",
                       "%s: %d timed, 0 not applicable, 0 unknown or invalid; %s" % (pl(closes, "close"), closes, G)),
        (F, "closes"): ("unknown; known subtotal %d" % closes, "unknown", G),
        (F, "completed"): ("unknown; known subtotal %d" % closes, "unknown", "exit_class completed"),
        (F, "non-completed"): (u0, "unknown", NONCOMP % (0, 0, G)),
        (F, "status unknown or invalid"): (u0, "unknown", "no usable exit_class"),
        (F, "non-completed, later resumed"): (u0, "unknown", LATER),
        (RV, "reviewing-class episodes"): (u0, "unknown", RVC_COV % ("0 closes", G)),
        (RV, "evidenced item associations"): EVID[2:],
        (RV, "positional candidate groups"): (u0, "unknown", GROUPS_COV % G),
        (RV, "reviewing-class episodes with no positional group"): (u0, "unknown", NOGROUP_COV),
        (RV, "candidate groups with two or more reviewing-class episodes"): (u0, "unknown", MULTI_COV),
        (RV, "rounds"): ROUNDS[2:],
        (B, "boundary events"): (u0, "unknown", "counted at their own timestamps; " + G),
        (B, "recorded idle unknown"): (u0, "unknown", IDLEU_COV),
        (B, "over-cap reports"): (u0, "unknown", OVER_COV % "0 boundaries"),
        (B, "rewrites (deltas)"): (u0, "unknown", REW_COV % "0 boundaries"),
        (B, "cumulative rewrites snapshots"): (u0, "unknown", BS_COV % 0),
        (RF, "helper tool"): (u0, "unknown", ch), (RF, "helper fence"): (u0, "unknown", ch),
        (RF, "helper sandbox"): (u0, "unknown", ch),
        (RF, "head fence (boundaries)"): (u0, "unknown", HF_COV % ("0 boundaries", 0, G)),
        (RF, "boundary summary of helper tool refusals"): (u0, "unknown", HS_COV % ("0 boundaries", G)),
        SP_T: ("unknown; known subtotal " + usd, "unknown", PRICED_COV % (pl(closes, "priced close"), "0 priced hold beats", 0, 0, 0, 0, G)),
        SP_PC: (u0, "unknown", PLAN_COV % (0, 0, 0, 0, 0, 0)),
        SP_TCI: tok(0, 0, 0, tc(0), gaps=g), SP_TCO: tok(0, 0, 0, tc(0), gaps=g),
        SP_TII: tok(0, 0, 0, ti(0), gaps=g), SP_TIO: tok(0, 0, 0, ti(0), gaps=g),
        SP_UN: (u0, "unknown", "token totals only; no dollar figure"),
        SP_NA: (u0, "unknown", "exit_class spawn-failed"),
        SP_HB: (u0, "unknown", "plan usage or no process"),
        SP_SS: (u0, "unknown", SS_COV % 0),
    }
    out.update(views_rows)
    return out


@case(4, "number-the-decimal-library-cannot-hold-named", route=5)
def t4_unrepresentable(ctx):
    # Route 5: run-x holds X's opening (10:00), its close with a duration of 1e9999999999999999999 and
    # an observation holding 1e-9999999999999999999 in a field no figure reads. The decimal library
    # holds no exponent past about 10^18, and its InvalidOperation is no ValueError: in the B-WASTE12
    # version the line parse let it through and the report aborted. Now each line is named not JSON,
    # like a NaN: undated after 10:00, of unknown kind, each feeds every figure of run-x; X stays open;
    # K's 60 s and $0.50 stay the known subtotals.
    code, main, detail = route_run(ctx, "unrepresentable", [("run-x.jsonl", [
        priced_episode("X", "2026-10-06T10:30:00+0100")[0],
        dict(priced_episode("X", "2026-10-06T10:30:00+0100")[1], duration_s=Raw("1e9999999999999999999")),
        {"ts": "2026-10-06T10:40:00+0100", "event": "observation", "note_n": Raw("1e-9999999999999999999")}])])
    expect(code == 0, "exit %d" % code)
    g2 = gn(2)
    want = reached_by_unknown_lines(1, "60 s (1.0 min)", "$0.50", 2, {
        (H, "run run-ok"): ("60 s (1.0 min)", "complete", VIEW),
        (H, "run run-x"): ("unknown; known subtotal 0 s (0.0 min)", "unknown", "0 closes: 0 not applicable, 0 unknown or invalid; " + g2),
        (H, "class builder"): ("unknown; known subtotal 60 s (1.0 min)", "unknown", "1 close: 0 not applicable, 0 unknown or invalid; " + g2),
        (H, 'helper run-ok/"K"'): ("60 s (1.0 min)", "complete", VIEW)})
    expect_table_and_gaps(main, detail, want, [
        "- run-x.jsonl:2 · time unknown · not JSON (a number the reader cannot represent (1e9999999999999999999)) · affects: every figure",
        "- run-x.jsonl:3 · time unknown · not JSON (a number the reader cannot represent (1e-9999999999999999999)) · affects: every figure"])
    for needle in ("- run-x.jsonl:2 · not JSON (a number the reader cannot represent (1e9999999999999999999)) · kind unknown · "
                   "between 2026-10-06 10:00:00 +0100 and the end · reaches this interval",
                   '- run-x:"X":1 · open · opened 2026-10-06 10:00:00 +0100 · no close on the record · its record holds invalid lines'):
        expect(needle in detail.split("\n"), "detail lacks: %s" % needle)


@case(4, "timestamp-fraction-bounded", route=6)
def t4_fraction(ctx):
    # Route 6, a record: run-x holds three episodes opened at 10:00. X closes at 10:30 with a fraction of
    # 5,000 digits (its integer read raises ValueError past 4,300 digits in Python 3.11 and later: the
    # B-WASTE12 version aborted), Y at 10:31 with 10 digits, Z at 10:32 with 9 (nanoseconds, the most a
    # fraction may hold). X's and Y's closes have no usable timestamp: each is named, undated between
    # 10:00 and 10:00, its opening unresolved, and reaches the episode parts of run-x for its own helper
    # and class (builder, so no review count). Z counts, its fraction kept. Known: 120 s and $1.00.
    long_ts = "2026-10-06T10:30:00." + "1" * 5000 + "+0100"
    lines = (priced_episode("X", long_ts) + priced_episode("Y", "2026-10-06T10:31:00.1234567891+0100")
             + priced_episode("Z", "2026-10-06T10:32:00.123456789+0100"))
    code, main, detail = route_run(ctx, "fraction", [("run-x.jsonl", lines)])
    expect(code == 0, "exit %d" % code)
    g2, u0 = gn(2), "unknown; known subtotal 0"
    want = priced_rows([("run-ok", "K"), ("run-x", "Z")])
    ch = "2 closes: 2 known, 0 not applicable, 0 unknown or invalid; " + g2
    want.update({
        (H, "total"): ("unknown; known subtotal 120 s (2.0 min)", "unknown", "2 closes: 2 timed, 0 not applicable, 0 unknown or invalid; " + g2),
        (H, "run run-x"): ("unknown; known subtotal 60 s (1.0 min)", "unknown", "1 close: 0 not applicable, 0 unknown or invalid; " + g2),
        (H, "class builder"): ("unknown; known subtotal 120 s (2.0 min)", "unknown", "2 closes: 0 not applicable, 0 unknown or invalid; " + g2),
        (F, "closes"): ("unknown; known subtotal 2", "unknown", g2),
        (F, "completed"): ("unknown; known subtotal 2", "unknown", "exit_class completed"),
        (F, "non-completed"): (u0, "unknown", NONCOMP % (0, 0, g2)),
        (F, "status unknown or invalid"): (u0, "unknown", "no usable exit_class"),
        (F, "non-completed, later resumed"): (u0, "unknown", LATER),
        (RF, "helper tool"): (u0, "unknown", ch), (RF, "helper fence"): (u0, "unknown", ch), (RF, "helper sandbox"): (u0, "unknown", ch),
        SP_T: ("unknown; known subtotal $1.00", "unknown", PRICED_COV % ("2 priced closes", "0 priced hold beats", 0, 0, 0, 0, g2)),
        SP_PC: (u0, "unknown", PLAN_COV % (0, 0, 0, 0, 0, 0)),
        SP_TCI: tok(0, 0, 0, tc(0), gaps=2), SP_TCO: tok(0, 0, 0, tc(0), gaps=2),
        SP_TII: tok(0, 0, 0, ti(0), gaps=2), SP_TIO: tok(0, 0, 0, ti(0), gaps=2),
        SP_UN: (u0, "unknown", "token totals only; no dollar figure"),
        SP_NA: (u0, "unknown", "exit_class spawn-failed")})
    expect_table_and_gaps(main, detail, want, [
        gl("run-x.jsonl:2 · time unknown", "no usable timestamp ('2026-10-06T10:30:00.%s)" % ("1" * 19), EPISODE_PARTS),
        gl("run-x.jsonl:4 · time unknown", "no usable timestamp ('2026-10-06T10:31:00.1234567891+0100')", EPISODE_PARTS)])
    expect("| lane-closed line 6, 2026-10-06 10:32:00.123456789 +0100 | 60 | completed |" in detail,
           "Z's close, its nine-digit fraction kept")
    expect('- run-x:"X":1 · unresolved · opened 2026-10-06 10:00:00 +0100 · line 2 closes it with no usable timestamp' in detail,
           "X unresolved")


@case(4, "store-line-timestamp-fraction-bounded", route=6)
def t4_store_fraction(ctx):
    # Route 6, the store: a listed line whose interval starts with a fraction of 5,000 digits (the
    # B-WASTE12 version raised ValueError reading the store and wrote nothing). Now the line is named
    # malformed (no readable interval): exit 1, both files written, the figures K's own.
    code, main, detail = route_run(ctx, "store-fraction", [], [json.dumps(
        {"kind": "listed", "key": "helper-time@2026-09-28..2026-10-05", "class": "helper-time", "name": "helper-time",
         "interval": ["2026-09-28T00:00:00." + "1" * 5000 + "+0100", "2026-10-05T00:00:00+0100"], "at": "2026-10-05T00:00:00+0100"})])
    expect(code == 1, "exit %d" % code)
    expect("**Store continuity failure:** line 2: a listed line without its key or its interval. This report's lines were "
           "appended; the key store-continuity@2026-10-05..2026-10-12 stays open until disposed (exit 1)." in main.split("\n"),
           "the continuity line")
    expect_table_and_gaps(main, detail, priced_rows([("run-ok", "K")]), [])


@case(4, "unpaired-surrogate-named", route=7)
def t4_surrogates(ctx):
    # Route 7, records: run-x holds an opening whose lane holds an unpaired high surrogate, an
    # observation whose member name holds an unpaired low one and a boundary whose idle_src ends in one
    # (each written as a JSON escape). The B-WASTE12 version rendered them and could not write its
    # report as UTF-8 (UnicodeEncodeError, no report). Now each line is named not JSON, undated, of
    # unknown kind: every figure unknown with the known subtotals of run-ok, which holds K and E😀, a
    # helper whose name carries a surrogate pair (the control: a pair is one character, read and shown).
    fx_lines = [{"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "X\ud800", "class": "builder"},
                {"ts": "2026-10-06T10:05:00+0100", "event": "observation", "\udc00": 1},
                {"ts": "2026-10-06T11:00:00+0100", "event": "phase-boundary", "idle_min": 1, "idle_src": "t\udfff",
                 "over_cap_reports": 0, "rewrites": 0, "head_denials": 0, "denials": 0}]
    emoji = "E\U0001F600"
    fx = Fx(ctx.root, "surrogates", script=ctx.script)
    fx.write("run-ok.jsonl", priced_episode("K", "2026-10-06T10:01:00+0100") + priced_episode(emoji, "2026-10-06T10:02:00+0100"))
    fx.write("run-x.jsonl", fx_lines)
    expect("\\ud83d\\ude00" in open(os.path.join(fx.records, "run-ok.jsonl"), encoding="utf-8").read(),
           "PROBE FAILED: the control's pair is not written as an escape")
    code, out, err, main, detail = fx.report()
    expect(main is not None and detail is not None and code == 0,
           "exit %d, report written %s, detail written %s: %s" % (code, main is not None, detail is not None, last_line(err)))
    g3 = gn(3)
    want = reached_by_unknown_lines(2, "120 s (2.0 min)", "$1.00", 3, {
        (H, "run run-ok"): ("120 s (2.0 min)", "complete", "2 closes: 0 not applicable, 0 unknown or invalid; " + GAPS0),
        (H, "run run-x"): ("unknown; known subtotal 0 s (0.0 min)", "unknown", "0 closes: 0 not applicable, 0 unknown or invalid; " + g3),
        (H, "class builder"): ("unknown; known subtotal 120 s (2.0 min)", "unknown", "2 closes: 0 not applicable, 0 unknown or invalid; " + g3),
        (H, "helper run-ok/" + emoji): ("60 s (1.0 min)", "complete", VIEW),
        (H, 'helper run-ok/"K"'): ("60 s (1.0 min)", "complete", VIEW)})
    expect_table_and_gaps(main, detail, want, [
        "- run-x.jsonl:%d · time unknown · not JSON (a string holding the unpaired surrogate U+%s, which is no character) · "
        "affects: every figure" % (n, cp) for n, cp in ((1, "D800"), (2, "DC00"), (3, "DFFF"))])
    expect("- run-ok/%s: 60 s (1.0 min) over 1 close (0 not applicable, 0 unknown or invalid; 0 named gaps (detail))" % json.dumps(emoji, ensure_ascii=True) in detail.split("\n"),
           "the control helper's line")


@case(4, "store-line-unpaired-surrogate-named", route=7)
def t4_store_surrogate(ctx):
    # Route 7, the store: a disposition whose note ends in an unpaired surrogate, rendered among the
    # dispositions recorded since the previous report (the B-WASTE12 version wrote its detail, then
    # failed on the report). Now the line is named not JSON: exit 1, both files written.
    code, main, detail = route_run(ctx, "store-surrogate", [], [json.dumps(
        {"kind": "disposition", "key": "helper-time@2026-10-05..2026-10-12", "disposition": "kept", "note": "n\udc00",
         "at": "2026-10-06T00:00:00+0100"})])
    expect(code == 1, "exit %d" % code)
    expect("**Store continuity failure:** line 2: not JSON. This report's lines were appended; the key "
           "store-continuity@2026-10-05..2026-10-12 stays open until disposed (exit 1)." in main.split("\n"), "the continuity line")
    expect(section(main, "## Dispositions")[-1] == "- none", "the line is no disposition")
    expect_table_and_gaps(main, detail, priced_rows([("run-ok", "K")]), [])


@case(4, "store-determination-keyed-by-its-own-field", route=8)
def t4_store_key(ctx):
    # Route 8: two run-ended lines, valid by their kind's fields, each also carrying an `episode` (a
    # list, then a number). The B-WASTE12 version keyed them by that field (an unhashable list: TypeError,
    # no report; a number would be ordered against a string). Now each is keyed by its run: run-ok's
    # names a last event the record lacks and run-zz has no record, so both are void, listed in order.
    code, main, detail = route_run(ctx, "store-key", [], [
        json.dumps({"kind": "run-ended", "run": "run-ok", "episode": ["x"], "evidence": "e1", "at": "2026-10-06T00:00:00+0100",
                    "record_lines": 2, "record_last_event": "x"}),
        json.dumps({"kind": "run-ended", "run": "run-zz", "episode": 5, "evidence": "e2", "at": "2026-10-06T00:00:00+0100",
                    "record_lines": 2, "record_last_event": "x"})])
    expect(code == 0, "exit %d" % code)
    expect(section(main, "## Determinations applied")[:2] == [
        "- run-ended run-ok at 2026-10-06T00:00:00+0100: void: its record changed after the determination. Evidence: e1",
        "- run-ended run-zz at 2026-10-06T00:00:00+0100: void: its record changed after the determination. Evidence: e2"],
        "determinations %s" % section(main, "## Determinations applied")[:2])
    expect_table_and_gaps(main, detail, priced_rows([("run-ok", "K")]), [])


@case(4, "store-line-nested-past-the-stack-named", route=9)
def t4_store_deep(ctx):
    # Route 9: a store line of 100,000 nested arrays. The store's parse caught no RecursionError (the
    # B-WASTE12 version aborted). Now it is named not JSON: exit 1, both files written.
    code, main, detail = route_run(ctx, "store-deep", [], ["[" * 100000 + "]" * 100000])
    expect(code == 1, "exit %d" % code)
    expect("**Store continuity failure:** line 2: not JSON. This report's lines were appended; the key "
           "store-continuity@2026-10-05..2026-10-12 stays open until disposed (exit 1)." in main.split("\n"), "the continuity line")
    expect_table_and_gaps(main, detail, priced_rows([("run-ok", "K")]), [])


@case(4, "deepest-nesting-renders", route=10)
def t4_deep_render(ctx):
    # Route 10, a guard (shown not to arise): a recorded value rendered as recorded (a boundary's
    # `from`, by repr) nested as deep as the line parse accepts. The parse runs deeper in the reader's
    # stack than the rendering, so whatever it accepts renders. The deepest list json.loads accepts here
    # is found by halving; the reader runs in its own process, so the boundaries span a window of
    # depths around it. Each line is rendered or named not JSON, and the report completes.
    lo, hi = 1, 1000000
    while lo < hi:
        mid = (lo + hi + 1) // 2
        try:
            json.loads("[" * mid + "]" * mid)
            lo = mid
        except RecursionError:
            hi = mid - 1
    depths = [max(1, lo + k) for k in range(-200, 201, 40)]
    lines = ['{"ts":"2026-10-06T11:%02d:00+0100","event":"phase-boundary","from":%s,"to":"b","idle_min":0,'
             '"idle_src":"transcript","over_cap_reports":0,"rewrites":0,"head_denials":0,"denials":0}' % (i, "[" * d + "]" * d)
             for i, d in enumerate(depths)]
    code, main, detail = route_run(ctx, "deep-render", [("run-deep.jsonl", lines)])
    rendered = [l for l in section(detail, "## Phase boundaries") if l.startswith("- run-deep.jsonl:")]
    named = [l for l in section(detail, "## Records holding invalid or undated lines (named in every report)")
             if l.startswith("- run-deep.jsonl:") and " · not JSON · " in l]
    expect(code == 0 and len(rendered) + len(named) == len(depths) and rendered,
           "exit %d; %d lines rendered and %d named of %d (depths %d to %d)" % (code, len(rendered), len(named), len(depths), depths[0], depths[-1]))


@case(4, "extreme-recorded-years-render", route=11)
def t4_years(ctx):
    # Route 11, a guard (shown not to arise): local times built from the earliest and latest stamps the
    # parse accepts (year 1 at +23:59, year 9999 at -23:59, which is in year 10000 here) render: a run
    # opened in year 1, an opening in each, and an undated line between them, its span rendered from
    # both. The report completes; K's figures stand.
    code, main, detail = route_run(ctx, "years", [("run-years.jsonl", [
        {"ts": "0001-01-01T00:00:00+23:59", "event": "run-open", "session": "s", "session_kind": "head"},
        {"ts": "0001-01-01T00:00:00+23:59", "event": "lane-open", "lane": "A", "class": "builder"},
        {"ts": "bad", "event": "observation"},
        {"ts": "9999-12-31T23:59:59-23:59", "event": "lane-open", "lane": "B", "class": "builder"}])])
    expect(code == 0, "exit %d" % code)
    lines = detail.split("\n")
    for prefix in ('- run-years:"A":2 · open · opened 0000-12-3', '- run-years:"B":4 · open · opened 10000-01-01 ',
                   "- run-years.jsonl:3 · no usable timestamp ('bad') · kind observation · between 0000-12-3",
                   "- run-years · last run-open or run-resume at 0000-12-3"):
        expect([l for l in lines if l.startswith(prefix)], "detail lacks a line beginning: %s" % prefix)
    want = priced_rows([("run-ok", "K")])
    expect(as_map(rows_of(main))[(H, "total")] == want[(H, "total")], "helper time %r" % (as_map(rows_of(main))[(H, "total")],))


# ------------------------------------------------------------------------ generated records ----
# CR-WASTE5 finding 2(b): a generative case. From a fixed seed it builds records out of the field and state
# matrix's values (zero, positive, absent, null, wrong type, other invalid, not applicable) together with
# adversarial strings (parenthesised text, every label of LABEL_STRINGS, white space, very long and non-ASCII
# text) and in-range extreme numbers and fractions, many records per run, and requires of each run: both
# reports written with exit 0, every invalid line it planted named (and no other), and no recorded string of
# its distinctive set in the coverage's gap groups. Whether a line is invalid is decided here, from FIELDS.md's
# rules for a line ("Inputs": strict JSON, an object, a known event name, a usable ts; an opening or close
# with a non-blank lane), never by the reader: a line meant valid is built valid, and each invalid one is
# built with one named defect. The seed and size are fixed: GEN_RUNS runs of GEN_RECORDS records of GEN_EPISODES
# episodes each, with boundaries, gates, beats, snapshots, end markers and planted invalid lines among them. The
# size was the smallest tried at which this seed failed the B-WASTE14 version and CR-WASTE5 finding 1's restored
# route and no one of 100 other seeds let that route pass either (measured in B-WASTE15's evidence). B-WASTE16's
# fold kept it and measured it again with the extended case below (evidence-B-WASTE16/generative-case.md): at
# this size, and at 6, 8 and 10 records, the fold passes this seed and 100 others, and the B-WASTE15 version and
# each of seven restored routes (CR-WASTE5 finding 1's, CR-WASTE6's three findings', and three of their
# families') fail this seed and all 100 others.
GEN_SEED, GEN_RUNS, GEN_RECORDS, GEN_EPISODES = 20261015, 1, 9, 6
# The session fields (B-WW1's fold: a close's and a beat's session_id, a beat's lane already drawn, a close's
# usage.modelUsage and each model's costUSD), drawn from a third stream seeded GEN_SEED + 2, so the first two
# draw each record and kit as before; set while t4_generated runs, None otherwise.
GEN_SESSIONS = {"rng": None}
GEN_STRINGS = [s for s, text in LABEL_STRINGS] + [
    "(critic)", "(", ")", "()", "((builder))", "(class invalid", "it's (builder)", "\"(builder)\"", "'", "\"",
    " ", "  ", "\t", "builder ", " critic", "line\nbreak", chr(0xa0) + "builder", chr(0x200b), "x" + chr(0x200b) + "y",
    "L" * 10000, "".join(map(chr, (0x6279, 0x8bc4, 0x8005))) * 2000, "".join(map(chr, (0x43a, 0x440, 0x438, 0x442, 0x438, 0x43a))), "".join(map(chr, (0x646, 0x627, 0x642, 0x62f))),
    "e" + chr(0x301), "\U0001F9EA", "\U0001F600 (builder)", "|", " " + chr(0xb7) + " ", "\\", "%s", "%d", "{}", "a:b", "a/b", "@x"]
# The strings the coverage's groups must never hold: each long enough, and with a parenthesis or a character
# beyond ASCII, that no group's own words contain it.
GEN_DISTINCT = sorted(set(s for s in GEN_STRINGS if len(s) >= 8 and ("(" in s or any(ord(c) > 127 for c in s))))
GEN_LANES = [s for s in GEN_STRINGS if s.strip()]
GEN_ABSENT = object()
# Numbers within the reader's range (magnitude below 10^15, at most 30 places): extremes, mixed scales, a
# zero with an exponent far above, a negative zero and the review's prices.
GEN_NUMBERS = [Raw(t) for t in ("0", "1", "0.5", "90.5", "999999999999999", "999999999999999.999999999999999999999999999999",
                                "1e-30", "0.000000000000000000000000000001", "0E+999999999", "-0.0", "0.025", "1e14",
                                "123456789.123456789123456789123456", "0.1", "3.000000000000000000000000000006", "5E+3")]
GEN_COUNTS = [0, 1, 3, 999999999999999, 2 ** 40]
GEN_STATES = [GEN_ABSENT, None, True, False, [], {}, [1], {"a": 1}, "90.5", "1", -1, Raw("-0.5"), Raw("1.5")]
GEN_SESSION_IDS = [GEN_ABSENT, None, 5, "", " ", "s1", "s1", "s2", [], {}]
GEN_OPENINGS = ("lane-open", "lane-open", "lane-open", "lane-resumed", "spawn", "probe-open", "lane-resume")
GEN_CLOSES = ("lane-closed", "lane-closed", "lane-closed", "close-out", "close-out-2", "lane-close", "probe-closed")
GEN_EXITS = ("completed", "completed", "limit", "killed", "spawn-failed", "watch-closed", "stall", "empty")
GEN_START = 1791154800          # 2026-10-05 00:00:00 +0100, the interval's start; it runs 7 days
GEN_BAD_TS = (GEN_ABSENT, None, 5, "bad", "2026-10-06T25:00:00+0100", "2026-10-06T10:60:00+0100", "2026-10-06T10:00:00",
              "2026-10-06 10:00:00+0100", "2026-10-06T10:00:00.1234567891+0100", "2026-10-06T10:00:00+9999",
              "(class unrecorded)", "None", "2026-02-30T10:00:00+0100", "0000-01-01T00:00:00+0100")


def gen_value(rng, kind):
    """One recorded value for a field of KIND: a number, a count or a string field, drawn from the matrix's
    states, the in-range numbers and the adversarial strings."""
    r = rng.random()
    if r < 0.35:
        return rng.choice(GEN_STATES)
    if kind == "number":
        return rng.choice(GEN_NUMBERS + GEN_COUNTS)
    if kind == "count":
        return rng.choice(GEN_COUNTS)
    return rng.choice(GEN_STRINGS)


def gen_ts(rng, t):
    """A usable timestamp for the instant T (whole seconds), in one of the forms the parse accepts: an offset
    of +0100, +01:00, Z, -0400 or +0530, seconds with a fraction of 1 to 9 digits, or minutes alone."""
    off = rng.choice((3600, 3600, 0, -14400, 19800))
    zone = "Z" if off == 0 and rng.random() < 0.5 else "%s%02d%s%02d" % (
        "+" if off >= 0 else "-", abs(off) // 3600, rng.choice(("", ":")), abs(off) % 3600 // 60)
    st = time.gmtime(t + off)
    form = rng.random()
    if form < 0.1 and st.tm_sec == 0:
        return time.strftime("%Y-%m-%dT%H:%M", st) + zone
    frac = "" if form < 0.5 else "." + "".join(rng.choice("0123456789") for _ in range(rng.randint(1, 9)))
    return time.strftime("%Y-%m-%dT%H:%M:%S", st) + frac + zone


def gen_put(line, key, value):
    if value is not GEN_ABSENT:
        line[key] = value


def gen_close_fields(rng, line):
    """A close's figure fields, each drawn on its own."""
    for key, kind in (("duration_s", "number"), ("exit_class", "string"), ("sandbox_denials", "count"),
                      ("fence_denials_transcript", "count"), ("usage_state", "string"), ("usage_complete", "string")):
        value = gen_value(rng, kind)
        if key == "exit_class" and rng.random() < 0.5:
            value = rng.choice(GEN_EXITS)
        if key == "usage_state" and rng.random() < 0.5:
            value = rng.choice(("complete", "incomplete", "zero", "missing"))
        if key == "usage_complete" and rng.random() < 0.5:
            value = rng.choice((True, False))
        gen_put(line, key, value)
    gen_put(line, "cost_src", rng.choice(("result", "result", "codex-plan", "transcript-estimate", GEN_ABSENT, None,
                                          gen_value(rng, "string"))))
    gen_put(line, "total_cost_usd", gen_value(rng, "number"))
    for key, members in (("denials", ("tool", "fence", "sandbox")), ("usage", ("input_tokens", "output_tokens", "calls"))):
        if rng.random() < 0.75:
            line[key] = {}
            for m in members:
                gen_put(line[key], m, gen_value(rng, "count"))
        else:
            gen_put(line, key, rng.choice((GEN_ABSENT, None, "unknown", "none reported", 5, [], gen_value(rng, "string"))))
    gen_session_fields(line)


def gen_session_fields(line):
    """A close's or a beat's session_id, and a close's usage.modelUsage when its usage is an object: models
    named by adversarial strings, each costUSD drawn from the matrix's values and the in-range numbers."""
    srng = GEN_SESSIONS["rng"]
    if srng is None:
        return
    pick = srng.choice(GEN_SESSION_IDS + GEN_STRINGS[:6])
    gen_put(line, "session_id", pick)
    if line.get("event") != "hold-beat" and isinstance(line.get("usage"), dict) and srng.random() < 0.7:
        models = srng.choice((GEN_ABSENT, None, [], "x", {}))
        if srng.random() < 0.7:
            models = {}
            for _ in range(srng.randint(1, 3)):
                entry = {"inputTokens": 1}
                gen_put(entry, "costUSD", gen_value(srng, "number"))
                models[srng.choice(["opus", "haiku"] + GEN_STRINGS[:8])] = entry if srng.random() < 0.8 else srng.choice((5, None, "x"))
        gen_put(line["usage"], "modelUsage", models)


def gen_other(rng, ts):
    """A valid line of a known kind other than an episode's: a boundary, a gate, a beat, a snapshot, an end
    marker, a run-open, or an observation holding whatever it holds."""
    kind = rng.choice(("phase-boundary", "phase-boundary", "gate", "gate", "hold-beat", "head-exit", "run-close",
                       "terminated", "stalled", "lane-aborted", "run-open", "observation", "note"))
    line = {"ts": ts, "event": kind}
    if kind == "phase-boundary":
        for key, k in (("idle_min", "number"), ("idle_src", "string"), ("over_cap_reports", "count"), ("rewrites", "count"),
                       ("rewrites_total", "count"), ("head_denials", "count"), ("head_denials_src", "string"),
                       ("denials", "count"), ("run_spend_usd", "number"), ("from", "string"), ("to", "string")):
            gen_put(line, key, gen_value(rng, k))
    elif kind == "gate":
        gen_put(line, "item", gen_value(rng, "string"))
        gen_put(line, "decision", rng.choice(("allow", "allow", "allow", "refuse", GEN_ABSENT, None, "maybe", gen_value(rng, "string"))))
        gen_put(line, "run_spend_usd", gen_value(rng, "number"))
    elif kind == "hold-beat":
        gen_put(line, "lane", gen_value(rng, "string"))
        gen_put(line, "cost_src", rng.choice(("result", "codex-plan", GEN_ABSENT, None, gen_value(rng, "string"))))
        gen_put(line, "total_cost_usd", gen_value(rng, "number"))
        gen_session_fields(line)
    elif kind == "head-exit":
        gen_put(line, "spent_usd", gen_value(rng, "number"))
    elif kind == "run-close":
        gen_put(line, "shape", rng.choice((GEN_ABSENT, GEN_ABSENT, "plain-lane-run", None, gen_value(rng, "string"))))
        gen_put(line, "run_spend_usd", gen_value(rng, "number"))
        gen_put(line, "spend_usd", gen_value(rng, "number"))
    elif kind in ("terminated", "stalled", "lane-aborted"):
        gen_put(line, "lane", rng.choice(GEN_LANES + [GEN_ABSENT, None, " ", 5]))
    else:
        gen_put(line, rng.choice(GEN_STRINGS[:40]), gen_value(rng, "number"))
    return line


def gen_invalid(rng, ts):
    """A line with one defect that makes it invalid (FIELDS.md, "Inputs"), as the text written, or bytes."""
    d = rng.randrange(11)
    if d == 0:
        return '{"ts": "%s", "event": "lane-cl' % ts
    if d == 1:
        return rng.choice(('[1, 2, 3]', '"(class unrecorded)"', '42', 'null'))
    if d == 2:
        line = {"ts": ts}
        gen_put(line, "event", rng.choice((GEN_ABSENT, None, 5, [], {}, ["lane-closed"])))
        return dumps_raw(line)
    if d == 3:
        return dumps_raw({"ts": ts, "event": rng.choice(GEN_STRINGS), "lane": "L"})
    if d == 4:
        line = {"event": rng.choice(("observation", "lane-closed", "phase-boundary", "gate")), "lane": "L"}
        gen_put(line, "ts", rng.choice(GEN_BAD_TS))
        return dumps_raw(line)
    if d == 5:
        line = {"ts": ts, "event": rng.choice(GEN_OPENINGS + GEN_CLOSES)}
        gen_put(line, "lane", rng.choice((GEN_ABSENT, None, " ", "", "\t", 5, [], {})))
        gen_put(line, "class", gen_value(rng, "string"))
        return dumps_raw(line)
    if d == 6:
        return '{"ts": "%s", "event": "observation", "a": 1, "a": 2}' % ts
    if d == 7:
        return '{"ts": "%s", "event": "observation", "x": %s}' % (ts, rng.choice(("NaN", "Infinity", "-Infinity")))
    if d == 8:
        return '{"ts": "%s", "event": "lane-open", "lane": "x\\ud800", "class": "builder"}' % ts
    if d == 9:
        return '{"ts": "%s", "event": "observation", "x": %s}' % (ts, rng.choice(("1e9999999999999999999", "-1E-9999999999999999999")))
    return b'\xff\xfe{"ts": "' + ts.encode() + b'", "event": "observation"}'


def gen_record(rng):
    """One record's lines (text or bytes) and the line numbers it made invalid."""
    lines, bad = [], set()
    t = GEN_START + rng.randrange(-86400, 6 * 86400)
    if rng.random() < 0.3:
        lines.append(dumps_raw({"ts": gen_ts(rng, t), "event": "run-open", "session": "s", "session_kind": "head"}))
    for e in range(GEN_EPISODES):
        lane = rng.choice(["L%d" % e] * 3 + GEN_LANES)
        same = rng.random() < 0.75
        cls_open = gen_value(rng, "string") if rng.random() < 0.8 else rng.choice(("builder", "critic", "verifier"))
        cls_close = cls_open if same else gen_value(rng, "string")
        for k in range(1 if rng.random() < 0.8 else 2):        # a resumed helper is a second episode
            t += rng.randrange(1, 4000)
            op = {"ts": gen_ts(rng, t), "event": rng.choice(GEN_OPENINGS) if k == 0 else "lane-resumed", "lane": lane}
            gen_put(op, "class", cls_open)
            lines.append(dumps_raw(op))
            while rng.random() < 0.4:
                t += rng.randrange(1, 600)
                if rng.random() < 0.15:
                    lines.append(gen_invalid(rng, gen_ts(rng, t)))
                    bad.add(len(lines))
                elif rng.random() < 0.1:
                    lines.append("")
                else:
                    lines.append(dumps_raw(gen_other(rng, gen_ts(rng, t))))
            if rng.random() < 0.9:                              # else the episode stays open
                t += rng.randrange(1, 4000)
                close = {"ts": gen_ts(rng, t), "event": rng.choice(GEN_CLOSES), "lane": lane}
                gen_put(close, "class", cls_close)
                gen_close_fields(rng, close)
                lines.append(dumps_raw(close))
    if rng.random() < 0.15 and len(lines) > 3:                   # an unordered record
        i = rng.randrange(1, len(lines) - 1)
        if i + 1 not in bad and i + 2 not in bad and lines[i] and lines[i + 1]:
            lines[i], lines[i + 1] = lines[i + 1], lines[i]
    return lines, bad


# CR-WASTE6 (B-WASTE16's fold, brief item 4): each generated run also holds records under arbitrary names (colons,
# the reader's labels, "all", spaces, quotation marks, other scripts and long names among them) and a disposition
# history in the held design's line format, beside a planted kit whose effects are fixed here from the rules
# (README.md, "The dispositions store"; FIELDS.md, "Recorded strings and the reader's labels"), never by the
# reader: two openings whose episode strings collide, abandoned by that string (in the held format or the
# B-WASTE15 one), and sometimes one of them by its structured identity; an opening abandoned uniquely (held,
# counted or structured, its extent written in another offset form of the same instant); one voided by a later
# event; one not yet applicable (always held); and all.jsonl and (all).jsonl, each closing an episode of class
# "all" and "(all)" in the interval. These are drawn from a second stream, seeded GEN_SEED + 1, so the first
# stream draws each record's contents as before; no name drawn for a record is a stem a kit string could be read
# with, so each kit string names exactly the openings planted for it.
GEN_NAMES = ["r", "r:x", "a:b", "a:b:c", "x:1", "1", ":", "::", "a::b", ":lead", "trail:", "total", "None", "(class invalid)",
             "(unusable)", "(builder)", "it's", "\"q\"", "a b", " lead", "trail ", "x" * 200,
             "".join(map(chr, (0x43a, 0x440, 0x438, 0x442, 0x438, 0x43a))), "\U0001F9EA", "e" + chr(0x301), "%s", "{}", "a|b",
             "@x", ".hidden", "-dash", "a.jsonl", "L" * 240, "run-g", "-", "undated", "(source unrecorded)"]
GEN_KIT_PARTS = ["x", "y", "q", "a:b", "1", "z z", "(all)", "all", "x:1", ":", "None", "it's"]
GEN_FIGURE_KEYS = ["helper-time", "failed-closes", "review-activity", "phase-boundaries", "refusals", "priced-spend", "coverage"]
GEN_FORGED = "- (all): 999 s (16.7 min) over 1 close (0 unknown or invalid; 0 named gaps (detail))"   # a total row, forged


def fold_name(s):
    """A name as this file system compares names (case and Unicode form aside), so no two drawn names are one file."""
    return unicodedata.normalize("NFC", s).casefold()


def kit_ts(rng, t, other_form=False):
    """The instant T (whole seconds) in one of the forms the parse accepts, every one that instant: an offset of
    +0100, +01:00, Z, +0000, -0400 or +0530, with or without a zero fraction; OTHER_FORM leaves out "+0100" with
    no fraction, the form a whole-second local time takes here in October."""
    forms = [(3600, "+0100"), (3600, "+01:00"), (0, "Z"), (0, "+0000"), (-14400, "-0400"), (19800, "+0530")]
    off, zone = rng.choice(forms[1:] if other_form else forms)
    frac = rng.choice(("", "", ".0", ".000"))
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t + off)) + frac + zone


def kit_stems(key):
    """The record stems the episode string KEY can be read with: each prefix of its head before a ":"."""
    head = key.rsplit(":", 1)[0]
    return [head[:i] for i, ch in enumerate(head) if ch == ":"]


def identity_of(name, lane, n):
    return "record %r, helper %s, line %d" % (name, json.dumps(lane, ensure_ascii=True), n)


def gen_kit(rng, run):
    """One run's kit: {name: lines}, the store lines (history, then determinations), and what the rules fix: the
    openings' texts with "open" or "left out", the determinations' lines, the carried keys, and the kit's record
    stems with the stems its strings can be read with (no other record may take one)."""
    open_t = GEN_START - 2 * 86400 + rng.randrange(0, 3600)
    decided = GEN_START - 86400 + rng.randrange(0, 3600)
    local = lambda t: time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(t))
    records, dets, openings, entries, keys = {}, [], [], [], []

    def opening(lane, t=open_t):
        return dumps_raw({"ts": kit_ts(rng, t), "event": "lane-open", "lane": lane, "class": "builder"})

    def det(episode, fmt, at, count, ident=None, other_form=False, evidence=""):
        line = {"kind": "abandoned", "episode": episode, "evidence": evidence, "at": kit_ts(rng, at),
                "last_event": kit_ts(rng, open_t, other_form), "record_last_event": kit_ts(rng, open_t, other_form)}
        if fmt in ("counted", "structured"):
            line["record_lines"] = count
        if fmt == "structured":
            line.update(record=ident[0], helper=ident[1], line=ident[2])
        dets.append(line)
        keys.append(episode)
        return line

    # Two openings whose strings collide: p.jsonl opens "q:h", p:q.jsonl opens "h", each at line 1, each its record's
    # only line, so each record's extent is the determination's: the string applies to neither.
    p = "p%d" % run + rng.choice(("", ":z", " (all)", ":all", ":None"))
    q, h = rng.choice(GEN_KIT_PARTS), rng.choice(GEN_KIT_PARTS)
    pair = [(p + ".jsonl", q + ":" + h), (p + ":" + q + ".jsonl", h)]
    for name, lane in pair:
        records[name] = [opening(lane)]
    key = "%s:%s:1" % (p, q + ":" + h)
    line = det(key, rng.choice(("held", "counted")), decided, 1, evidence="kit %d: a collision" % run)
    entries.append(determination_entry(key, "ambiguous: its episode string could name 2 openings (%s; %s); it applies to "
                                            "none of them" % (identity_of(pair[0][0], pair[0][1], 1), identity_of(pair[1][0], pair[1][1], 1)),
                                       at=line["at"], evidence=line["evidence"]))
    target = rng.choice(pair) if rng.random() < 0.5 else None
    if target:
        line = det(key, "structured", decided, 1, ident=(target[0], target[1], 1), evidence="kit %d: one of the pair" % run)
        entries.append(determination_entry("%s (%s)" % (key, identity_of(target[0], target[1], 1)), APPLIED, at=line["at"],
                                           evidence=line["evidence"]))
    for name, lane in pair:
        openings.append(("%s (%s)" % (json.dumps(key, ensure_ascii=True), identity_of(name, lane, 1)), local(open_t), "left out" if (name, lane) == target else "open"))
    # One opening, at line K after K-1 observations, abandoned uniquely; its extent in another form of the instant.
    u, w, k = "u%d" % run + rng.choice(("", ":y", " all", ":(all)")), rng.choice(GEN_KIT_PARTS), rng.randrange(1, 4)
    records[u + ".jsonl"] = [dumps_raw({"ts": kit_ts(rng, open_t - 100 * (k - i)), "event": "observation"}) for i in range(1, k)] + [opening(w)]
    fmt = rng.choice(("held", "counted", "structured"))
    ukey = "%s:%s:%d" % (u, w, k)
    line = det(ukey, fmt, decided, k, ident=(u + ".jsonl", w, k), other_form=True, evidence="kit %d: unique" % run)
    entries.append(determination_entry(ukey, APPLIED + (HELD_LIMIT if fmt == "held" else ""), at=line["at"], evidence=line["evidence"]))
    openings.append((u + ":" + json.dumps(w, ensure_ascii=True) + ":" + str(k), local(open_t), "left out"))
    # One voided by a later event (an observation after the determination, before the interval).
    v, vl = "w%d" % run + rng.choice(("", ":a", " b")), rng.choice(GEN_KIT_PARTS)
    records[v + ".jsonl"] = [opening(vl), dumps_raw({"ts": kit_ts(rng, GEN_START - 43200), "event": "observation"})]
    fmt = rng.choice(("held", "counted", "structured"))
    vkey = "%s:%s:1" % (v, vl)
    line = det(vkey, fmt, decided, 1, ident=(v + ".jsonl", vl, 1), evidence="kit %d: voided" % run)
    entries.append(determination_entry(vkey, VOIDED, at=line["at"], evidence=line["evidence"]))
    openings.append((v + ":" + json.dumps(vl, ensure_ascii=True) + ":1", local(open_t), "open"))
    # One not yet applicable: decided inside the interval, in the held format (so every run holds a held line).
    pd, pl_ = "pd%d" % run + rng.choice(("", ":c", " (x)")), rng.choice(GEN_KIT_PARTS)
    records[pd + ".jsonl"] = [opening(pl_)]
    pkey = "%s:%s:1" % (pd, pl_)
    line = det(pkey, "held", GEN_START + 86400 + rng.randrange(0, 3600), 1, evidence="kit %d: pending" % run)
    entries.append(determination_entry(pkey, PENDING + HELD_LIMIT, at=line["at"], evidence=line["evidence"]))
    openings.append((pd + ":" + json.dumps(pl_, ensure_ascii=True) + ":1", local(open_t), "open"))
    # The views' total beside the recorded "all" and "(all)": each a run, a class and a helper closing in the interval;
    # and a helper whose lane holds a line break and a whole total row, which must stay on one line.
    for name, lane, cls in (("all.jsonl", "A", "all"), ("(all).jsonl", "P", "(all)"), ("lb%d.jsonl" % run, "B\n" + GEN_FORGED, "builder")):
        t = GEN_START + 3 * 86400 + rng.randrange(0, 3600)
        records[name] = [dumps_raw({"ts": kit_ts(rng, t), "event": "lane-open", "lane": lane, "class": cls}),
                         dumps_raw({"ts": kit_ts(rng, t + 60), "event": "lane-closed", "lane": lane, "class": cls,
                                    "exit_class": "completed", "duration_s": 60, "cost_src": "result", "total_cost_usd": 0.5,
                                    "denials": {"tool": 0, "fence": 0, "sandbox": 0}})]
    # The history, in the held format (no `at` on its report, listed and disposition lines), two earlier weeks.
    history, listed, disposed = [], [], set()
    for back in (2, 1):
        s, e = GEN_START - 7 * 86400 * back, GEN_START - 7 * 86400 * (back - 1)
        label = "%s..%s" % (time.strftime("%Y-%m-%d", time.localtime(s)), time.strftime("%Y-%m-%d", time.localtime(e)))
        interval = [time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t)) for t in (s, e)]
        chosen = rng.sample(GEN_FIGURE_KEYS, rng.randint(1, 4))
        history.append({"kind": "report", "interval": interval, "report": "waste-report-%s.md" % label[-10:],
                        "detail": "waste-detail-%s.md" % label[-10:], "listed": len(chosen), "not_seen": 0})
        for fk in chosen:
            history.append({"kind": "listed", "key": "%s@%s" % (fk, label), "class": fk, "name": fk, "interval": interval})
            listed.append("%s@%s" % (fk, label))
    for key_ in rng.sample(listed, rng.randint(0, len(listed))):
        history.append({"kind": "disposition", "key": key_, "disposition": rng.choice(("fixed", "registered", "kept", "owner")),
                        "note": rng.choice(("kept for review", "(builder)", "all", "None", "x:y", "it's"))})
        disposed.add(key_)
    rng.shuffle(dets)
    carried = ["- %s: open, carried from an earlier report" % k for k in sorted(set(listed) - disposed)]
    stems = set(n[:-len(".jsonl")] for n in records)
    reserved = set(s for k in keys for s in kit_stems(k)) | stems
    return records, history + dets, openings, entries, carried, reserved


VIEW_ROW = re.compile(r"\A- (.*): (?:unknown; known subtotal )?\S+ s \(\S+ min\) over [0-9]+ closes? "
                      r"\((?:[0-9]+ not applicable, )?[0-9]+ unknown or invalid; [0-9]+ named gaps? \(detail\)\)\Z")


def gen_run(rng, kit_rng, run):
    """One generated run, drawn as t4_generated draws it: its records {name: lines}, the store lines appended after
    init, the kit's openings and determination lines, the carried keys, and the invalid lines planted ("name:n").
    The records' contents come from RNG, as before this fold; their names, the kit and the history from KIT_RNG."""
    records, store_lines, openings, entries, carried, reserved = gen_kit(kit_rng, run)
    used = set(fold_name(n) for n in records) | set(fold_name(s + ".jsonl") for s in reserved)
    want_bad = set()
    for r in range(GEN_RECORDS):
        pool = [s for s in GEN_NAMES if fold_name(s + ".jsonl") not in used]
        stem = kit_rng.choice(pool) if pool and kit_rng.random() < 0.6 else "run-g%d-%d" % (run, r)
        name = stem + ".jsonl"
        expect(fold_name(name) not in used, "PROBE FAILED: the drawn name %r is taken" % name)
        used.add(fold_name(name))
        lines, bad = gen_record(rng)
        if r == 0:          # every run plants at least one invalid line: the naming check's own control
            lines.append(gen_invalid(rng, gen_ts(rng, GEN_START + 3600)))
            bad.add(len(lines))
        records[name] = lines
        want_bad |= set("%s:%d" % (name, n) for n in bad)
    return records, store_lines, openings, entries, carried, want_bad


@case(4, "generated-records-complete-both-reports", cr5=2, family=4)
def t4_generated(ctx):
    rng = random.Random(GEN_SEED)
    kit_rng = random.Random(GEN_SEED + 1)
    GEN_SESSIONS["rng"] = random.Random(GEN_SEED + 2)
    problems = []
    for run in range(GEN_RUNS):
        fx = Fx(ctx.root, "generated-%d" % run, script=ctx.script)
        records, store_lines, openings, entries, carried, want_bad = gen_run(rng, kit_rng, run)
        for name, lines in records.items():
            with open(os.path.join(fx.records, name), "wb") as h:
                h.write(b"".join((l if isinstance(l, bytes) else l.encode("utf-8")) + b"\n" for l in lines))
        # The session fields' control: the third stream planted session ids and per-model costs in this run.
        text = [l for lines in records.values() for l in lines if isinstance(l, str)]
        for member in ('"session_id"', '"modelUsage"', '"costUSD"'):
            if not any(member in l for l in text):
                problems.append("PROBE FAILED: run %d planted no %s (control)" % (run, member))
        append_store_lines(fx, store_lines)
        code, out, err, main, detail = fx.report()
        if code != 0 or main is None or detail is None or "Store continuity failure" in main:
            problems.append("run %d: exit %d, report written %s, detail written %s, store continuity %s: %s"
                            % (run, code, main is not None, detail is not None,
                               "failed" if main and "Store continuity failure" in main else "held", last_line(err)))
            if main is None or detail is None:
                continue        # both written (a continuity failure exits 1 with both): every other check still runs
        bad_lines = [l for l in section(detail, "## Records holding invalid or undated lines (named in every report)") if l != "- none"]
        named = set(w for w in want_bad if any(l.startswith("- %s · " % w) for l in bad_lines))
        if named != want_bad or len(bad_lines) != len(want_bad):
            problems.append("run %d: invalid lines not named %s; %d named for %d planted" % (
                run, sorted(want_bad - named)[:5], len(bad_lines), len(want_bad)))
        cov = section(main, "## Coverage by reason")
        groups = [l for l in cov[[i for i, l in enumerate(cov) if l.startswith("- Named gaps")][0] + 1:] if l.startswith("  - ")]
        leaked = [s for s in GEN_DISTINCT if any(s in g for g in groups)]
        if leaked:
            problems.append("run %d: recorded strings in the coverage's groups: %r" % (run, [s[:30] for s in leaked][:3]))
        if not want_bad or not groups:
            problems.append("PROBE FAILED: run %d planted %d invalid lines and named %d gap groups (control)"
                            % (run, len(want_bad), len(groups)))
        # The kit (CR-WASTE6): each planted opening open or left out, and each determination's effect, as fixed above.
        open_list = section(detail, "## Episodes open or unresolved at acquisition")
        for text, opened, state in openings:
            line = open_entry(text, opened=opened)
            if state == "open" and line not in open_list:
                problems.append("run %d: the open episode %s is not named open" % (run, text[:120]))
            if state == "left out" and any(l.startswith("- %s · " % text) for l in open_list):
                problems.append("run %d: the abandoned episode %s is still named open" % (run, text[:120]))
        dets = section(main, "## Determinations applied")
        for entry in entries:
            if entry not in dets:
                problems.append("run %d: no determination line %s" % (run, entry[:200]))
        # Each helper-time view: its total row, the label, once and last; every row's name its own; the recorded
        # "all" and "(all)" the kit closed among the rows, and its helper whose lane holds a line break and a total
        # row on one line, the line break escaped (the check's own control).
        lines = detail.split("\n")
        for head, planted in (("### By run", ("all", "'(all)'")), ("### By class", ("all", "'(all)'")),
                              ("### By helper", ('all/"A"', '\'(all)\'/"P"', "lb%d/%s" % (run, json.dumps("B\n" + GEN_FORGED, ensure_ascii=True))))):
            i = lines.index(head) + 1
            rows = []
            while lines[i]:
                m = VIEW_ROW.match(lines[i])
                rows.append(m.group(1) if m else None)
                i += 1
            if None in rows or len(set(rows)) != len(rows) or rows.count("(all)") != 1 or rows[-1] != "(all)":
                problems.append("run %d: %s's rows %s: no unique total row last, or two rows of one name"
                                % (run, head, [r[:40] if r else r for r in rows][-6:]))
            if not set(planted) <= set(rows):
                problems.append("PROBE FAILED: run %d's %s lacks the recorded rows %s (control)" % (run, head, planted))
        keys = [l for l in dispositions_lines(main) if l.endswith(": open, carried from an earlier report")]
        if keys != carried:
            problems.append("run %d: carried keys %s, want %s" % (run, keys[:4], carried[:4]))
    expect(not problems, "; ".join(problems))


# ------------------------------------------------------------------------ test 5 -----------

BOOT = r'''
import os, sys, runpy
FORBID = set(p for p in os.environ["WW_FORBID"].split(os.pathsep) if p)
FORBID_DIRS = [d for d in os.environ.get("WW_FORBID_DIRS", "").split(os.pathsep) if d]
LOG = os.path.realpath(os.environ["WW_OPEN_LOG"])
SPAWN = ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork",
         "os.forkpty", "pty.spawn", "os.startfile", "_posixsubprocess.fork_exec", "os.popen")
seen = []
def hook(event, args):
    if event == "open":
        path = args[0]
        if isinstance(path, int) or path is None:
            return
        try:
            raw = os.path.abspath(os.fsdecode(path))
            real = os.path.realpath(raw)
        except Exception:
            return
        if real == LOG:
            return
        seen.append(real)
        for p in (raw, real):
            if p in FORBID or any(p == d or p.startswith(d + os.sep) for d in FORBID_DIRS):
                os.write(2, ("FORBIDDEN READ %s\n" % real).encode())
                os._exit(97)
    elif event in SPAWN or event.startswith("subprocess."):
        os.write(2, ("FORBIDDEN SUBPROCESS %s\n" % event).encode())
        os._exit(98)
sys.addaudithook(hook)
import atexit
def dump():
    fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    os.write(fd, "\n".join(seen).encode())
    os.close(fd)
atexit.register(dump)
script = sys.argv[1]
sys.argv = sys.argv[1:]
namespace = runpy.run_path(script, run_name="weekly_waste_test")
caught = []
namespace["main"].__globals__["containment_observer"] = caught.append
result = namespace["main"](sys.argv[1:])
import json
sys.stderr.write("CONTAINMENT-TEST-CHANNEL " + json.dumps(caught) + "\n")
sys.exit(result)
'''


def guarded_run(ctx, fx, refs, script=None, extra=(), prelude="", env_extra=None):
    """The reader under the audit hook (BOOT), every path in REFS and the projects folder guarded.
    PRELUDE runs before the hook is installed (the fixed clock, FIXED_CLOCK); ENV_EXTRA adds to the
    run's environment. Returns the exit code, stdout, stderr and the paths opened."""
    boot = os.path.join(fx.dir, "boot.py")
    with open(boot, "w") as h:
        h.write(prelude + BOOT)
    log = os.path.join(fx.dir, "opens.log")
    if os.path.exists(log):
        os.unlink(log)
    env = {"WW_FORBID": os.pathsep.join(os.path.realpath(r) for r in refs),
           "WW_FORBID_DIRS": os.path.realpath(fx.projects), "WW_OPEN_LOG": log}
    env.update(env_extra or {})
    code, out, err = fx.run("--since", SINCE, "--until", UNTIL, *extra, prefix=[PY, "-I", "-B", boot],
                            env=env, script=script or fx.script)
    opened = open(log).read().split("\n") if os.path.exists(log) else []
    return code, out, err, [o for o in opened if o]


def allowed_roots(fx, script):
    roots = [os.path.realpath(fx.records), os.path.realpath(fx.tools), os.path.realpath(script)]
    for p in (sys.prefix, sys.base_prefix, sys.exec_prefix, os.path.dirname(os.path.realpath(PY))):
        roots.append(os.path.realpath(p))
    return roots


@case(5, "records-only-reads-under-audit", finding=1, cr3=1)
def t5_guarded(ctx):
    # Scene A under the audit hook: every file a record references, all of them outside the
    # contract (the transcript outside the records folder, the report, brief, prompt, hand-off and
    # .log event stream, the pinned event log), the other pinned event log and the per-run table are
    # guarded and unreadable. The reader opens the five admitted records, build-20260914-fit (no
    # run- prefix) among them, and nothing else.
    fx = Fx(ctx.root, "t5-guard", script=ctx.script)
    refs = scene_a(fx)
    for r in refs:
        os.chmod(r, 0)
    try:
        code, out, err, opened = guarded_run(ctx, fx, refs)
    finally:
        for r in refs:
            os.chmod(r, 0o644)
    expect(code == 0, "guarded run exit %d: %s" % (code, err.strip()[-300:]))
    expect("FORBIDDEN" not in err, err)
    roots = allowed_roots(fx, fx.script)
    odd = [o for o in opened if not any(o == r or o.startswith(r + os.sep) for r in roots)]
    expect(not odd, "opens outside the declared inputs: %s" % odd[:5])
    recs = [o for o in opened if o.startswith(os.path.realpath(fx.records) + os.sep)]
    expect(sorted(set(os.path.basename(o) for o in recs)) ==
           ["build-20260914-fit.jsonl", "run-a.jsonl", "run-hist-c.jsonl", "run-kill-d.jsonl", "run-plain-b.jsonl"],
           "record opens: %s" % sorted(set(recs)))
    expect_rows(open(os.path.join(fx.tools, "reports", "waste-report-2026-10-12.md"), encoding="utf-8").read(), SCENE_A_ROWS)


@case(5, "referenced-files-changed-or-removed", finding=1, cr3=1)
def t5_changes(ctx):
    # Changing, then removing, every referenced file and every pinned event log (all outside the
    # contract) changes no figure, no named gap and no counted episode. (Removing them rightly
    # changes the inventory, the coverage listing and the link list, which are not figures.)
    fx = Fx(ctx.root, "t5-change", script=ctx.script)
    refs = scene_a(fx)
    seen = []
    for step in ("as-is", "changed", "removed"):
        if step == "changed":
            for r in refs:
                with open(r, "w") as h:
                    h.write('{"event": "lane-closed", "lane": "B1", "duration_s": 99999}\n')
        if step == "removed":
            for r in refs:
                os.unlink(r)
        code, out, err, main, detail = fx.report()
        expect(code == 0, "%s exit %d" % (step, code))
        seen.append((rows_of(main), section(detail, "## Named gaps and the figures they affect"),
                     section(detail, "## Episodes closing in the interval")))
    expect(seen[0][0] == SCENE_A_ROWS, "the figures are not scene A's")
    for i, what in ((0, "figures"), (1, "named gaps"), (2, "episodes")):
        expect(seen[0][i] == seen[1][i] == seen[2][i], "%s changed with the referenced files" % what)


def admission_fixture(fx):
    """The input contract's guarded fixture (CR-WASTE3 finding 1): two records whose lines name, as a transcript,
    event log, report, brief, prompt or hand-off, files in every form outside the contract: the
    current event stream (`.log`), a report, a prompt and a hand-off (`.md`) in the records folder,
    a transcript (a `.jsonl` under the projects folder) and a brief in a folder of its own, both
    outside the records folder, and two of the pinned event logs. A third pinned event log is named
    by nothing. Each pinned log holds a record-like close of 99999 s naming run-c.jsonl that would
    change every figure if it were read. Returns the paths of every file outside the contract, so
    that every referenced fixture path is guarded, none exempt."""
    R, D = fx.sub("<R>"), os.path.realpath(fx.dir)
    os.makedirs(os.path.join(fx.dir, "briefs"))
    fx.write("run-c.jsonl",
             oc("C1", "2026-10-06T10:00:00+0100", "2026-10-06T10:02:00+0100", 120, events=R + "/run-c-events-C1.log")
             + oc("C2", "2026-10-06T10:00:00+0100", "2026-10-06T10:03:00+0100", 180, report=R + "/run-c-report-C2.md")
             + oc("C3", "2026-10-06T10:00:00+0100", "2026-10-06T10:04:00+0100", 240, transcript=fx.sub("<T>/" + UUID_NAME),
                  prompt_file=R + "/run-c-prompt-C3.md", brief=D + "/briefs/brief-C3.md"))
    fx.write("run-d.jsonl",
             oc("D1", "2026-10-06T10:00:00+0100", "2026-10-06T10:00:30+0100", 30, events=R + "/" + PINNED[0])
             + oc("D2", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60, events=R + "/" + PINNED[2],
                  handoff=R + "/handoff-d.md"))
    refs = [fx.write(UUID_NAME, ['{"type": "user", "message": "TRANSCRIPT-MARKER"}'], fx.projects),
            fx.write("brief-C3.md", ["BRIEF-MARKER"], os.path.join(fx.dir, "briefs"))]
    for name in ("run-c-events-C1.log", "run-c-report-C2.md", "run-c-prompt-C3.md", "handoff-d.md"):
        refs.append(fx.write(name, ["MARKER"]))
    for name in (PINNED[0], PINNED[2], PINNED[4]):
        refs.append(fx.write(name, oc("Q", "2026-10-06T09:00:00+0100", "2026-10-06T09:30:00+0100", 99999,
                                      events=R + "/run-c.jsonl")))
    return refs


# The coverage lines of the admission fixture, fixed by hand: five *.jsonl names in name order (the
# pinned L1, L3 and L6, then run-c and run-d); run-c and run-d admitted, the three pinned not; four
# other entries (the .log and three .md).
ADMISSION_COVERAGE = [
    candidates_line(5, 2, 2, 3),
    pinned_line(3),
    "  - `%s`" % PINNED[0],
    "  - `%s`" % PINNED[2],
    "  - `%s`" % PINNED[4],
    others_line(4),
    "- Records read: 2 with events in the interval, 0 outside it; 2 without run-open (counted like any other).",
]


def guarded_reports(fx):
    main = open(os.path.join(fx.tools, "reports", "waste-report-2026-10-12.md"), encoding="utf-8").read()
    detail = open(os.path.join(fx.tools, "reports", "waste-detail-2026-10-12.md"), encoding="utf-8").read()
    return main, detail


def record_opens(fx, opened):
    return sorted(set(os.path.basename(o) for o in opened if o.startswith(os.path.realpath(fx.records) + os.sep)))


@case(5, "admission-by-name-before-any-open", finding=1, cr3=1)
def t5_admission(ctx):
    # Every file a record of this fixture references lies outside the contract, and every one is
    # guarded, together with the pinned event log nothing names: the run must pass without opening
    # any (no referenced path exempt). The reader opens exactly the two admitted records. Durations
    # 120 + 180 + 240 + 30 + 60 = 630 s (10.5 min), complete, no named gap. Changing the guarded files
    # (record-like lines naming the records as evidence), then removing them, changes no figure, no
    # named gap and no coverage line about the records, each run under the same guard.
    fx = Fx(ctx.root, "t5-admission", script=ctx.script)
    refs = admission_fixture(fx)
    code, out, err, opened = guarded_run(ctx, fx, refs)
    expect(code == 0 and "FORBIDDEN" not in err, "guarded exit %d %s" % (code, err.strip()[-300:]))
    expect(record_opens(fx, opened) == ["run-c.jsonl", "run-d.jsonl"], "opened: %s" % record_opens(fx, opened))
    main, detail = guarded_reports(fx)
    got = section(main, "## Coverage by reason")[:len(ADMISSION_COVERAGE)]
    expect(got == ADMISSION_COVERAGE, "coverage:\n%s" % first_difference(got, ADMISSION_COVERAGE))
    for name in (PINNED[0], PINNED[2], PINNED[4]):
        expect("| %s | %s | - | - | - | - | - | - | - |" % (name, NOT_ADMITTED_CELL) in detail, "inventory lacks %s" % name)
    first = (rows_of(main), section(detail, "## Named gaps and the figures they affect"))
    expect(as_map(first[0])[(H, "total")] == ("630 s (10.5 min)", "complete",
                                              "5 closes: 5 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "total %r" % (as_map(first[0])[(H, "total")],))
    expect(first[1] == ["- none"], "named gaps %s" % first[1])
    for step in ("changed", "removed"):
        for r in refs:
            if step == "changed":
                with open(r, "w") as h:
                    for target in ("run-c.jsonl", "run-d.jsonl"):
                        h.write(json.dumps({"ts": "2026-10-06T10:00:00+0100", "event": "lane-closed", "lane": "C1",
                                            "duration_s": 99999, "events": fx.sub("<R>/" + target),
                                            "transcript": fx.sub("<R>/" + target)}) + "\n")
            else:
                os.unlink(r)
        code, out, err, opened = guarded_run(ctx, fx, refs)
        expect(code == 0 and "FORBIDDEN" not in err, "%s: guarded exit %d %s" % (step, code, err.strip()[-300:]))
        expect(record_opens(fx, opened) == ["run-c.jsonl", "run-d.jsonl"], "%s: opened %s" % (step, record_opens(fx, opened)))
        main, detail = guarded_reports(fx)
        expect((rows_of(main), section(detail, "## Named gaps and the figures they affect")) == first,
               "%s: files outside the contract changed a figure or a named gap" % step)


@case(5, "excluded-file-naming-other-candidates-changes-nothing", finding=1, cr3=1)
def t5_excluded_contents(ctx):
    # Excluded-file reference invariance under the input contract: run-b-rec.jsonl names a pinned
    # event log as its event log and a .md as its report; run-c-rec.jsonl holds an independent 120 s
    # episode. Neither excluded file is ever opened (both guarded in every run), so what they hold
    # changes nothing: as written, with a close of 99999 s naming run-c-rec.jsonl in `events`, with
    # lines naming both records in `events`, `transcript` and `grants`, and removed. Each time: 60 +
    # 120 = 180 s (3.0 min), complete, no named gap (a reference inside a file never read is never
    # seen), both records read.
    fx = Fx(ctx.root, "t5-excluded", script=ctx.script)
    R = fx.sub("<R>")
    a = fx.write(PINNED[1], ['{"type": "thread.started", "thread_id": "t"}'])
    rep = fx.write("run-b-rec-report-B.md", ["REPORT-MARKER"])
    fx.write("run-b-rec.jsonl", oc("B", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60, events=a, report=rep))
    fx.write("run-c-rec.jsonl", oc("C", "2026-10-06T10:00:00+0100", "2026-10-06T10:02:00+0100", 120))
    want_total = ("180 s (3.0 min)", "complete", "2 closes: 2 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0)
    seen = []
    for step in ("as-is", "names-the-other-record", "names-both-records", "removed"):
        if step in ("names-the-other-record", "names-both-records"):
            for path in (a, rep):
                if step == "names-the-other-record":
                    fx.write(os.path.basename(path), oc("Q", "2026-10-06T09:00:00+0100", "2026-10-06T09:30:00+0100", 99999,
                                                        events=R + "/run-c-rec.jsonl"))
                else:
                    fx.write(os.path.basename(path), [
                        {"ts": "2026-10-06T09:00:00+0100", "event": "lane-closed", "lane": "B",
                         "events": R + "/run-b-rec.jsonl", "transcript": R + "/run-c-rec.jsonl",
                         "grants": [R + "/run-b-rec.jsonl", R + "/run-c-rec.jsonl"], "duration_s": 5}])
        elif step == "removed":
            os.unlink(a)
            os.unlink(rep)
        code, out, err, opened = guarded_run(ctx, fx, [a, rep])
        expect(code == 0 and "FORBIDDEN" not in err, "%s: guarded exit %d %s" % (step, code, err.strip()[-300:]))
        expect(record_opens(fx, opened) == ["run-b-rec.jsonl", "run-c-rec.jsonl"], "%s: opened %s" % (step, record_opens(fx, opened)))
        main, detail = guarded_reports(fx)
        m = as_map(rows_of(main))
        expect(m[(H, "total")] == want_total, "%s: total %r" % (step, m[(H, "total")]))
        expect("| run-b-rec.jsonl | read |" in detail and "| run-c-rec.jsonl | read |" in detail, "%s: a record not read" % step)
        seen.append((rows_of(main), section(detail, "## Named gaps and the figures they affect")))
    expect(seen[0][1] == ["- none"], "named gaps: %s" % seen[0][1])
    expect(all(x == seen[0] for x in seen), "an excluded file's contents changed a figure or a named gap")


@case(5, "admission-decided-before-the-first-open", finding=1, cr3=1)
def t5_admission_order(ctx):
    # In process: every admission decision is logged before the first file of the records folder
    # is opened (by any call: an audit hook sees builtins.open and os.open alike), one decision per
    # candidate, and the files opened are exactly the admitted ones, each once: under the input
    # contract the three records whatever their names (one without the run- prefix, one containing
    # -events-), never the pinned event log.
    fx = Fx(ctx.root, "t5-order", script=ctx.script)
    for name, lane in (("run-a.jsonl", "A"), ("b-rec.jsonl", "B"), ("run-x-events-y.jsonl", "X")):
        fx.write(name, oc(lane, "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60))
    fx.write(PINNED[0], oc("Q", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 99999))
    mod = reader_module(ctx.script, "ww_order")
    expect(callable(getattr(mod, "admitted", None)), "the reader has no admission decision by name")
    log = []
    real_admitted = mod.admitted

    def logged_admitted(name, *listing):
        # The decision may read the folder's listing too (a read log is left out only beside its run's record).
        log.append(("admit", name))
        return real_admitted(name, *listing)
    mod.admitted = logged_admitted
    buf = io.StringIO()
    audit_opens(fx.records, log)
    try:
        with contextlib.redirect_stdout(buf):
            code = mod.main(["--records", fx.records, "--tools-dir", fx.tools, "--since", SINCE, "--until", UNTIL])
    finally:
        audit_stop()
    expect(code == 0, "exit %r" % code)
    admits = [i for i, e in enumerate(log) if e[0] == "admit"]
    opens = [i for i, e in enumerate(log) if e[0] == "open"]
    expect(sorted(e[1] for e in log if e[0] == "admit") ==
           sorted(["b-rec.jsonl", PINNED[0], "run-a.jsonl", "run-x-events-y.jsonl"]),
           "one decision per candidate: %s" % log)
    expect(opens and max(admits) < min(opens), "a file was opened before every admission was decided: %s" % log)
    expect(sorted(e[1] for e in log if e[0] == "open") == ["b-rec.jsonl", "run-a.jsonl", "run-x-events-y.jsonl"], "opens: %s" % log)


@case(5, "pinned-event-logs-only-exact", cr3=1)
def t5_pinned(ctx):
    # The five event logs pinned by exact name are not admitted: never opened (guarded) and listed,
    # whatever they hold (here a record-like close of 99999 s each). Near misses are run records
    # under the input contract, admitted and read: L4 (a log the contract does not pin), L10, L1-2 and a prefixed
    # name hold closes of 10, 20, 30 and 40 s: 100 s (100/60 = 1.67 -> 1.7 min). A .bak copy of a
    # pinned log is no candidate at all (guarded too). Name order puts L1-2 before L1 ('-' sorts
    # before '.') and L1 before L10. A name that differs from a pinned one only in case gets its own
    # folder (the default macOS file system folds case): admitted and read, 15 + 30 = 45 s.
    fx = Fx(ctx.root, "t5-pinned", script=ctx.script)
    refs = [fx.write(n, oc("Q", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", 99999)) for n in PINNED]
    near = (("run-20260909-n14-accept-events-L4.jsonl", 10), ("run-20260909-n14-accept-events-L10.jsonl", 20),
            ("run-20260909-n14-accept-events-L1-2.jsonl", 30), ("xrun-20260909-n14-accept-events-L1.jsonl", 40))
    for name, dur in near:
        fx.write(name, oc("P", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", dur))
    refs.append(fx.write(PINNED[0] + ".bak", oc("Q", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", 99999)))
    code, out, err, opened = guarded_run(ctx, fx, refs)
    expect(code == 0 and "FORBIDDEN" not in err, "guarded exit %d %s" % (code, err.strip()[-300:]))
    expect(record_opens(fx, opened) == sorted(n for n, d in near), "opened %s" % record_opens(fx, opened))
    main, detail = guarded_reports(fx)
    want = [candidates_line(9, 4, 4, 5), pinned_line(5)] + ["  - `%s`" % n for n in PINNED] + [others_line(1)]
    got = section(main, "## Coverage by reason")[:len(want)]
    expect(got == want, "coverage:\n%s" % first_difference(got, want))
    expect(as_map(rows_of(main))[(H, "total")] == ("100 s (1.7 min)", "complete",
                                                   "4 closes: 4 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "total %r" % (as_map(rows_of(main))[(H, "total")],))
    case_fx = Fx(ctx.root, "t5-pinned-case", script=ctx.script)
    case_fx.write(PINNED[0].replace("-L1.", "-l1."), oc("Q", "2026-10-06T10:00:00+0100", "2026-10-06T10:00:15+0100", 15))
    case_fx.write("run-z.jsonl", oc("Z", "2026-10-06T10:00:00+0100", "2026-10-06T10:00:30+0100", 30))
    code, out, err, opened = guarded_run(ctx, case_fx, [])
    expect(code == 0 and "FORBIDDEN" not in err and record_opens(case_fx, opened) == [PINNED[0].replace("-L1.", "-l1."), "run-z.jsonl"],
           "a case variant of a pinned name: %d %s %s" % (code, record_opens(case_fx, opened), err.strip()[-200:]))
    main, detail = guarded_reports(case_fx)
    expect(as_map(rows_of(main))[(H, "total")][:2] == ("45 s (0.8 min)", "complete"), "case variant total %r"
           % (as_map(rows_of(main))[(H, "total")],))


# The inventory's status for the command checker's read log, `<run>-unplaced-reads.jsonl` (FIELDS.md, "Admission").
READ_LOG_CELL = ("not admitted: the command checker's read log, `<run>-unplaced-reads.jsonl` beside its run's record "
                 "`<run>.jsonl`, by its name (FIELDS.md, \"Admission\"); not opened, its contents unread and unknown")
# Lines as lane-fence.py's read logging writes them (record_unplaced_reads): no `event`, so each would be a line
# with no event name if the file were read as a run record.
READ_LOG_LINES = [{"v": 1, "ts": "2026-10-06T10:00:00+0100", "who": "lane:R", "sid": "?", "cwd": "/w", "n": 0,
                   "reads": [], "cmd": "", "cut": False},
                  {"v": 1, "ts": "2026-10-06T10:00:30+0100", "who": "lane:R", "sid": "?", "cwd": "/w", "n": 1,
                   "reads": [["parameter", "$X"]], "cmd": "cat \"$X\"", "cut": False}]


@case(5, "command-checker-read-logs-left-out-by-name")
def t5_read_logs(ctx):
    # The command checker's read logging appends to `<run>-unplaced-reads.jsonl` in the records folder, `<run>` a
    # run id ([A-Za-z0-9._-]{1,128}). Such a name is left out by its name before any file is opened, as a pinned
    # event log is: never opened (guarded), listed in the coverage and the inventory, read by no figure, and
    # refused as a run by the subcommands. Near misses are run records: "run r-unplaced-reads.jsonl" (a space, so
    # no run id) holds a 30 s episode, admitted and read; a .bak copy of the log is no candidate (guarded).
    # run-r.jsonl holds a 60 s episode: 60 + 30 = 90 s (1.5 min), complete, no named gap. Name order: the space
    # (0x20) sorts first, then "run-r-" before "run-r." ('-' 0x2d, '.' 0x2e). A second folder holds a read log
    # beside a pinned event log and one record, for the line that names both kinds.
    fx = Fx(ctx.root, "t5-read-logs", script=ctx.script)
    fx.write("run-r.jsonl", oc("R", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60))
    fx.write("run r-unplaced-reads.jsonl", oc("Q", "2026-10-06T10:00:00+0100", "2026-10-06T10:00:30+0100", 30))
    refs = [fx.write("run-r-unplaced-reads.jsonl", READ_LOG_LINES), fx.write("run-r-unplaced-reads.jsonl.bak", READ_LOG_LINES)]
    code, out, err, opened = guarded_run(ctx, fx, refs)
    expect(code == 0 and "FORBIDDEN" not in err, "guarded exit %d %s" % (code, err.strip()[-300:]))
    expect(record_opens(fx, opened) == ["run r-unplaced-reads.jsonl", "run-r.jsonl"], "opened %s" % record_opens(fx, opened))
    main, detail = guarded_reports(fx)
    want = [candidates_line(3, 2, 2, 1),
            "- Not admitted by name: 1, read logs of the command checker (`<run>-unplaced-reads.jsonl`), never opened, their "
            "contents unread and unknown; no figure reads them (FIELDS.md, \"Admission\"):",
            "  - `run-r-unplaced-reads.jsonl`", others_line(1)]
    got = section(main, "## Coverage by reason")[:len(want)]
    expect(got == want, "coverage:\n%s" % first_difference(got, want))
    expect("| run-r-unplaced-reads.jsonl | %s | - | - | - | - | - | - | - |" % READ_LOG_CELL in detail.split("\n"),
           "inventory lacks the read log's line")
    expect(as_map(rows_of(main))[(H, "total")] == ("90 s (1.5 min)", "complete",
                                                   "2 closes: 2 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "total %r" % (as_map(rows_of(main))[(H, "total")],))
    expect(section(detail, "## Named gaps and the figures they affect") == ["- none"], "a named gap")
    code, out, err = fx.run("end-run", "run-r-unplaced-reads", "--evidence", "a read log is no run")
    expect(code == 2 and "not admitted as a run record by its name" in err, "end-run of a read log: %d %s" % (code, err.strip()[-200:]))
    both = Fx(ctx.root, "t5-read-logs-both", script=ctx.script)
    both.write("run-z.jsonl", oc("Z", "2026-10-06T10:00:00+0100", "2026-10-06T10:00:20+0100", 20))
    refs = [both.write(PINNED[0], oc("Q", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", 99999)),
            both.write("run-z-unplaced-reads.jsonl", READ_LOG_LINES)]
    code, out, err, opened = guarded_run(ctx, both, refs)
    expect(code == 0 and "FORBIDDEN" not in err and record_opens(both, opened) == ["run-z.jsonl"],
           "both kinds: guarded exit %d, opened %s %s" % (code, record_opens(both, opened), err.strip()[-200:]))
    main, detail = guarded_reports(both)
    want = [candidates_line(3, 1, 1, 2),
            "- Not admitted by name: 2, 1 event log pinned by name and 1 read log of the command checker "
            "(`<run>-unplaced-reads.jsonl`), never opened, their contents unread and unknown; no figure reads them "
            "(FIELDS.md, \"Admission\"):",
            "  - `%s`" % PINNED[0], "  - `run-z-unplaced-reads.jsonl`", others_line(0)]
    got = section(main, "## Coverage by reason")[:len(want)]
    expect(got == want, "both kinds' coverage:\n%s" % first_difference(got, want))
    expect(as_map(rows_of(main))[(H, "total")][:2] == ("20 s (0.3 min)", "complete"), "both kinds' total")


@case(5, "read-log-name-without-its-run-record-admitted")
def t5_read_log_alone(ctx):
    # CR-WW1 finding 6: a run whose own id ends in "-unplaced-reads" has the record name of a read log, and the logger
    # writes one only beside its run's record (lane-fence.py's record_unplaced_reads: while `<run>.jsonl` is a regular
    # file there). So the name is left out only when `<run>.jsonl` is in the same listing, decided from the names
    # before any file is opened, and listed; with no such record beside it, it is a run record like any other. Here
    # run-q-unplaced-reads.jsonl holds a 45 s episode and no run-q.jsonl is in the folder: admitted, opened and read.
    # run-r.jsonl (60 s) sits beside run-r-unplaced-reads.jsonl, a read log: left out, never opened, listed.
    # 45 + 60 = 105 s (1.75 min, 1.8), complete; FIELDS.md states the rule.
    fx = Fx(ctx.root, "t5-read-log-alone", script=ctx.script)
    fx.write("run-q-unplaced-reads.jsonl", oc("Q", "2026-10-06T10:00:00+0100", "2026-10-06T10:00:45+0100", 45))
    fx.write("run-r.jsonl", oc("R", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60))
    refs = [fx.write("run-r-unplaced-reads.jsonl", READ_LOG_LINES)]
    code, out, err, opened = guarded_run(ctx, fx, refs)
    expect(code == 0 and "FORBIDDEN" not in err, "guarded exit %d %s" % (code, err.strip()[-300:]))
    expect(record_opens(fx, opened) == ["run-q-unplaced-reads.jsonl", "run-r.jsonl"], "opened %s" % record_opens(fx, opened))
    main, detail = guarded_reports(fx)
    want = [candidates_line(3, 2, 2, 1),
            "- Not admitted by name: 1, read logs of the command checker (`<run>-unplaced-reads.jsonl`), never opened, their "
            "contents unread and unknown; no figure reads them (FIELDS.md, \"Admission\"):",
            "  - `run-r-unplaced-reads.jsonl`", others_line(0)]
    got = section(main, "## Coverage by reason")[:len(want)]
    expect(got == want, "coverage:\n%s" % first_difference(got, want))
    expect(as_map(rows_of(main))[(H, "total")] == ("105 s (1.8 min)", "complete",
                                                   "2 closes: 2 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "total %r" % (as_map(rows_of(main))[(H, "total")],))
    fields = open(os.path.join(os.path.dirname(os.path.abspath(ctx.script)), "FIELDS.md"), encoding="utf-8").read()
    expect(READ_LOG_RULE in fields, "FIELDS.md does not state the read logs' rule: %r" % READ_LOG_RULE)


# FIELDS.md's statement of the rule (CR-WW1 finding 6), held word for word.
READ_LOG_RULE = ("a name of that form is left out only when `<run>.jsonl` is in the same listing; with no such record "
                 "beside it, it is a run record like any other")


# ------------------------------------------------------------------------ the input contract ----
# The owner's decision B17 (spec-D19.md, "Input contract (the owner's decision B17, 14 October
# 2026)"): "An admitted record remains an input when another record names it as evidence; that
# reference alone is neither a prohibited read nor incomplete figure coverage. Excluded evidence
# files remain unopened, including through subprocesses." R1's breach cases retired with its breach
# rule (B-WASTE14's fold); these replace them. What the contract promises (spec-D19.md's last section,
# "What a reference may and may not change"): no figure, no coverage status and no other substantive
# report content changes; the acquisition time, the measured byte counts and the folder inventory are
# reported as they are. These cases check more strongly than that: they run the reader under the audit
# hook on a fixed clock, so that two runs over the same inputs write the same bytes, compare whole report
# files under substitutions of equal length, and fix by hand the lines a removal changes.

FIXED_CLOCK = r'''
import os as _os, time as _time
_FIXED = float(_os.environ["WW_FIXED_CLOCK"])
_time.time = lambda: _FIXED
'''
# The instant the fixed clock reads, 2026-10-15 06:00:00 +0100 (any instant serves, so long as the
# runs compared read the same one): the acquisition window, the runtime and the store's times.
CLOCK = {"WW_FIXED_CLOCK": "1792040400"}


def fixed_run(ctx, fx, refs, script=None, env_extra=None):
    """One guarded run (guarded_run, REFS guarded) on the fixed clock, its previous reports removed
    first: (exit, stderr, opens, main report bytes, detail bytes), a file not written being None."""
    paths = [os.path.join(fx.tools, "reports", "waste-%s-%s.md" % (kind, UNTIL)) for kind in ("report", "detail")]
    for p in paths:
        if os.path.exists(p):
            os.unlink(p)
    env = dict(CLOCK)
    env.update(env_extra or {})
    code, out, err, opened = guarded_run(ctx, fx, refs, script=script, prelude=FIXED_CLOCK, env_extra=env)
    got = [open(p, "rb").read() if os.path.exists(p) else None for p in paths]
    return code, err, opened, got[0], got[1]


def bytes_differ(got, want):
    """None when two report files hold the same bytes, else where they first differ, in one line."""
    if got == want:
        return None
    if got is None or want is None:
        return "a report was not written"
    g, w = got.decode("utf-8").split("\n"), want.decode("utf-8").split("\n")
    for i in range(max(len(g), len(w))):
        a = g[i] if i < len(g) else "<none>"
        b = w[i] if i < len(w) else "<none>"
        if a != b:
            return "line %d is %r, not %r" % (i + 1, a[:100], b[:100])
    return "the line ends differ"


def record_open_counts(fx, opened):
    """How many times each file directly in the records folder was opened."""
    recs = os.path.realpath(fx.records) + os.sep
    counts = {}
    for o in opened:
        if o.startswith(recs) and os.sep not in o[len(recs):]:
            counts[o[len(recs):]] = counts.get(o[len(recs):], 0) + 1
    return counts


def builder_rows(n, total, runs, helpers):
    """The whole figures table, fixed from the definitions, for N valid builder closes as oc() writes
    them (GPT-6 Astra plan usage, complete, 1 token in and 1 out, every refusal count a measured zero)
    whose durations total TOTAL, with no boundary, gate, beat, snapshot or gap: no review class, so
    every review count is 0; every refusal channel N known zeros; N plan closes, N tokens each way.
    RUNS and HELPERS map the helper-time view rows the main report shows (the three largest of each)
    to their values, one close each."""
    closes = pl(n, "close")
    ch = "%s: %d known, 0 not applicable, 0 unknown or invalid; %s" % (closes, n, GAPS0)
    out = {
        (H, "total"): (total, "complete", "%s: %d timed, 0 not applicable, 0 unknown or invalid; %s" % (closes, n, GAPS0)),
        (H, "class builder"): (total, "complete", "%s: 0 not applicable, 0 unknown or invalid; %s" % (closes, GAPS0)),
        (F, "closes"): (str(n), "complete", GAPS0),
        (F, "completed"): (str(n), "complete", "exit_class completed"),
        (F, "non-completed"): ("0", "complete", NONCOMP % (0, 0, GAPS0)),
        (F, "status unknown or invalid"): ("0", "complete", "no usable exit_class"),
        (F, "non-completed, later resumed"): ("0", "complete", LATER),
        (RV, "reviewing-class episodes"): ("0", "complete", RVC_COV % ("0 closes", GAPS0)),
        (RV, "evidenced item associations"): EVID[2:],
        (RV, "positional candidate groups"): ("0", "complete", GROUPS_COV % GAPS0),
        (RV, "reviewing-class episodes with no positional group"): ("0", "complete", NOGROUP_COV),
        (RV, "candidate groups with two or more reviewing-class episodes"): ("0", "complete", MULTI_COV),
        (RV, "rounds"): ROUNDS[2:],
        (B, "boundary events"): ("0", "complete", "counted at their own timestamps; " + GAPS0),
        (B, "recorded idle unknown"): ("0", "complete", IDLEU_COV),
        (B, "over-cap reports"): ("0", "complete", OVER_COV % "0 boundaries"),
        (B, "rewrites (deltas)"): ("0", "complete", REW_COV % "0 boundaries"),
        (B, "cumulative rewrites snapshots"): ("0", "complete", BS_COV % 0),
        (RF, "helper tool"): ("0", "complete", ch),
        (RF, "helper fence"): ("0", "complete", ch),
        (RF, "helper sandbox"): ("0", "complete", ch),
        (RF, "head fence (boundaries)"): ("0", "complete", HF_COV % ("0 boundaries", 0, GAPS0)),
        (RF, "boundary summary of helper tool refusals"): ("0", "complete", HS_COV % ("0 boundaries", GAPS0)),
        SP_T: ("$0.00", "complete", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 0, 0, GAPS0)),
        SP_PC: (str(n), "complete", PLAN_COV % (n, 0, 0, 0, 0, 0)),
        SP_TCI: tok(n, n, 0, tc(n)),
        SP_TCO: tok(n, n, 0, tc(n)),
        SP_TII: tok(0, 0, 0, ti(0)),
        SP_TIO: tok(0, 0, 0, ti(0)),
        SP_UN: ("0", "complete", "token totals only; no dollar figure"),
        SP_NA: ("0", "complete", "exit_class spawn-failed"),
        SP_HB: ("0", "complete", "plan usage or no process"),
        SP_SS: ("0", "complete", SS_COV % 0),
    }
    for key, value in runs.items():
        out[(H, "run " + key)] = (value, "complete", VIEW)
    for key, value in helpers.items():
        out[(H, "helper " + key)] = (value, "complete", VIEW)
    return out


def evidence_refs(fx):
    """The forms in which the retired R1 cases named a record as evidence, each naming an admitted
    record of its own here, in the spellings those cases used: `event_log` (the review's own line, a
    bare name), `eventLog` (the records folder's real path), a list under `refs.transcripts` (`./`), a
    `durable-transcript` line's `file` (the folder as given), a `lane-report-persisted` line's `path`
    (`../spawn-records/`), `handoff` (`~`, HOME the fixture's folder), `paths.brief_copy`,
    `prior.event-stream`, `paths.report`, and a close's `events`, `transcript` and `report`. Returns
    (label, target, value) in the order run-a.jsonl holds them (reference_record)."""
    R, G = fx.sub("<R>"), fx.records
    return [("event_log", "run-b.jsonl", "run-b.jsonl"),
            ("eventLog", "run-c.jsonl", R + "/run-c.jsonl"),
            ("refs.transcripts", "run-d.jsonl", "./run-d.jsonl"),
            ("durable-transcript file", "run-e.jsonl", G + "/run-e.jsonl"),
            ("lane-report-persisted path", "run-f.jsonl", "../spawn-records/run-f.jsonl"),
            ("handoff", "run-g.jsonl", "~/store/spawn-records/run-g.jsonl"),
            ("paths.brief_copy", "run-h.jsonl", R + "/run-h.jsonl"),
            ("prior.event-stream", "run-i.jsonl", R + "/run-i.jsonl"),
            ("paths.report", "run-j.jsonl", R + "/run-j.jsonl"),
            ("events", "run-k.jsonl", R + "/run-k.jsonl"),
            ("transcript", "run-l.jsonl", R + "/run-l.jsonl"),
            ("report", "run-m.jsonl", R + "/run-m.jsonl")]


def reference_record(fx, refs, active, drop=False):
    """Writes run-a.jsonl: nine dated lines of known kinds that feed no figure, each holding one of the
    first nine references, then A's 60 s episode, whose close holds the last three. A reference whose
    label is not in ACTIVE holds dashes of its own length instead, naming no file, so the record keeps
    its bytes; with DROP the reference fields are left out altogether."""
    v = dict((label, value if label in active else "-" * len(value)) for label, target, value in refs)
    ts = lambda n: "2026-10-06T09:%02d:00+0100" % n
    lines = [({"ts": ts(0), "event": "observation"}, {"event_log": v["event_log"]}),
             ({"ts": ts(1), "event": "observation"}, {"eventLog": v["eventLog"]}),
             ({"ts": ts(2), "event": "note"}, {"refs": {"transcripts": [v["refs.transcripts"]]}}),
             ({"ts": ts(3), "event": "durable-transcript"}, {"file": v["durable-transcript file"]}),
             ({"ts": ts(4), "event": "lane-report-persisted"}, {"path": v["lane-report-persisted path"]}),
             ({"ts": ts(5), "event": "observation"}, {"handoff": v["handoff"]}),
             ({"ts": ts(6), "event": "observation"}, {"paths": {"brief_copy": v["paths.brief_copy"]}}),
             ({"ts": ts(7), "event": "observation"}, {"prior": {"event-stream": v["prior.event-stream"]}}),
             ({"ts": ts(8), "event": "observation"}, {"paths": {"report": v["paths.report"]}})]
    close = {} if drop else {"events": v["events"], "transcript": v["transcript"], "report": v["report"]}
    fx.write("run-a.jsonl", [dict(base, **({} if drop else field)) for base, field in lines]
             + oc("A", "2026-10-06T09:10:00+0100", "2026-10-06T09:11:00+0100", 60, **close))


@case(5, "admitted-record-named-as-evidence-changes-nothing", b17=1)
def t5_named_record(ctx):
    # B17: "An admitted record remains an input when another record names it as evidence; that
    # reference alone is neither a prohibited read nor incomplete figure coverage." run-a.jsonl names
    # run-b to run-m as evidence, one each, in every field the retired R1 cases read as naming
    # evidence (evidence_refs). Each target holds one builder episode of 10, 20, ... 120 s and is read
    # as a run record like any other, opened once, never by a reference: 60 + (10 + 20 + ... + 120) =
    # 60 + 780 = 840 s (840/60 = 14.0 min) over 13 closes, complete; the three largest runs and
    # helpers 120, 110 and 100 s (2.0, 1.83 -> 1.8 and 1.67 -> 1.7 min). Both report files are written,
    # no breach is named and no total reads partial. Both files are byte for byte those of the same
    # fixture without the references (each value dashes of its own length, naming no file), with all
    # twelve at once and with each alone; left out altogether, the fields change only run-a.jsonl's
    # byte count, in the input volume and its inventory row.
    fx = Fx(ctx.root, "t5-named-record", script=ctx.script)
    refs = evidence_refs(fx)
    labels = [label for label, target, value in refs]
    for n, (label, target, value) in enumerate(refs, 1):
        fx.write(target, oc(target[4].upper(), "2026-10-06T10:00:00+0100",
                            "2026-10-06T10:%02d:%02d+0100" % divmod(10 * n, 60), 10 * n))
    home = {"HOME": fx.dir}
    records = sorted(["run-a.jsonl"] + [target for label, target, value in refs])
    reference_record(fx, refs, ())
    code, err, opened, base_main, base_detail = fixed_run(ctx, fx, [], env_extra=home)
    expect(code == 0 and base_main and base_detail and "FORBIDDEN" not in err,
           "without the references: exit %d %s" % (code, err.strip()[-300:]))
    bad, first = [], None
    for active in [labels] + [[label] for label in labels]:
        reference_record(fx, refs, active)
        code, err, opened, main, detail = fixed_run(ctx, fx, [], env_extra=home)
        what = "all twelve" if len(active) > 1 else active[0]
        whys = []
        if code != 0 or "FORBIDDEN" in err:
            whys.append("exit %d %s" % (code, err.strip()[-160:]))
        for name, got, want in (("main report", main, base_main), ("detail", detail, base_detail)):
            if bytes_differ(got, want):
                whys.append("the %s's %s" % (name, bytes_differ(got, want)))
        if record_open_counts(fx, opened) != dict((r, 1) for r in records):
            whys.append("record opens %s" % record_open_counts(fx, opened))
        if whys:
            bad.append(what)
            first = first or "%s: %s" % (what, whys[0])
    expect(not bad, "%d of 13 runs with references differ from the run without them (%s); first, %s"
           % (len(bad), ", ".join(bad), first))
    # The run with all twelve references, fixed by hand.
    reference_record(fx, refs, labels)
    code, err, opened, main, detail = fixed_run(ctx, fx, [], env_extra=home)
    main, detail = main.decode("utf-8"), detail.decode("utf-8")
    e = compare_map(rows_of(main), builder_rows(13, "840 s (14.0 min)",
                                                {"run-m": "120 s (2.0 min)", "run-l": "110 s (1.8 min)", "run-k": "100 s (1.7 min)"},
                                                {'run-m/"M"': "120 s (2.0 min)", 'run-l/"L"': "110 s (1.8 min)", 'run-k/"K"': "100 s (1.7 min)"}))
    expect(e is None, e)
    want = [candidates_line(13, 13, 13, 0), "- Not admitted by name: 0.", others_line(0),
            "- Records read: 13 with events in the interval, 0 outside it; 13 without run-open (counted like any other).",
            "- Records holding invalid or undated lines: 0, each named in the detail in every report until mended.",
            "- Episodes open or unresolved at acquisition: 0 (0 opened after the interval's end; 0 unresolved by an "
            "invalid close or opening), named in the detail; such an episode counts nowhere until a valid close resolves it.",
            "- Runs open at acquisition: 0.",
            "- Lines under a historical event name (FIELDS.md): 0, each marked in the detail.",
            "- Named gaps affecting this interval's figures: 0."]
    got = section(main, "## Coverage by reason")
    expect(got == want, "coverage:\n%s" % first_difference(got, want))
    for n, (label, target, value) in enumerate(refs, 1):
        row = "| %s | read | %d | 2 | 2026-10-06 10:00:00 +0100 | 2026-10-06 10:%02d:%02d +0100 | no | 0 | ordered |" % (
            target, os.path.getsize(os.path.join(fx.records, target)), (10 * n) // 60, (10 * n) % 60)
        expect(row in detail.split("\n"), "inventory row of %s (named in %s): %s" % (target, label, row))
    expect(not re.search(r"(?i)breach", main + detail), "a breach was named: %s"
           % [l for l in (main + "\n" + detail).split("\n") if re.search(r"(?i)breach", l)][:3])
    expect("partial" not in main + detail, "a total reads partial")
    expect(dispositions_lines(main) == ["- %s@2026-10-05..2026-10-12: listed by this report; open" % k for k in (
        "helper-time", "failed-closes", "review-activity", "phase-boundaries", "refusals", "priced-spend")],
        "keys: %r" % dispositions_lines(main))
    # The reference fields left out altogether: only run-a.jsonl's byte count changes.
    reference_record(fx, refs, (), drop=True)
    code, err, opened, main2, detail2 = fixed_run(ctx, fx, [], env_extra=home)
    expect(code == 0 and "FORBIDDEN" not in err, "fields left out: exit %d %s" % (code, err.strip()[-300:]))
    for name, old, new, prefix in (("main report", base_main, main2, "- Runtime: "),
                                   ("detail", base_detail, detail2, "| run-a.jsonl | read | ")):
        a, b = old.decode("utf-8").split("\n"), new.decode("utf-8").split("\n")
        moved = [(x, y) for x, y in zip(a, b) if x != y]
        expect(len(a) == len(b) and len(moved) == 1 and moved[0][0].startswith(prefix)
               and re.sub(r"[0-9]+", "N", moved[0][0]) == re.sub(r"[0-9]+", "N", moved[0][1]),
               "fields left out: the %s differs in %s" % (name, moved[:3]))


# The event stream's figures, fixed by hand (CR-WASTE3 finding 1's case, read by B17). Its three lines
# have no event name and no ts: each feeds every part of run run-f-events-F, every helper and every
# class, in every interval (an undated line of a record with no dated line reaches all of them), so
# every total that could hold an input of that run reads unknown with its known subtotal and 3 named
# gaps. run-f's own run and helper rows read none of them: F's 60 s close, complete. The plan tokens
# are F's own 3 in and 3 out.
STREAM_ROWS = {
    (H, "total"): ("unknown; known subtotal 60 s (1.0 min)", "unknown", "1 close: 1 timed, 0 not applicable, 0 unknown or invalid; " + gn(3)),
    (H, "run run-f"): ("60 s (1.0 min)", "complete", VIEW),
    (H, "run run-f-events-F"): ("unknown; known subtotal 0 s (0.0 min)", "unknown", "0 closes: 0 not applicable, 0 unknown or invalid; " + gn(3)),
    (H, "class builder"): ("unknown; known subtotal 60 s (1.0 min)", "unknown", "1 close: 0 not applicable, 0 unknown or invalid; " + gn(3)),
    (H, 'helper run-f/"F"'): ("60 s (1.0 min)", "complete", VIEW),
    (F, "closes"): ("unknown; known subtotal 1", "unknown", gn(3)),
    (F, "completed"): ("unknown; known subtotal 1", "unknown", "exit_class completed"),
    (F, "non-completed"): ("unknown; known subtotal 0", "unknown", NONCOMP % (0, 0, gn(3))),
    (F, "status unknown or invalid"): ("unknown; known subtotal 0", "unknown", "no usable exit_class"),
    (F, "non-completed, later resumed"): ("unknown; known subtotal 0", "unknown", LATER),
    (RV, "reviewing-class episodes"): ("unknown; known subtotal 0", "unknown", RVC_COV % ("0 closes", gn(3))),
    (RV, "evidenced item associations"): EVID[2:],
    (RV, "positional candidate groups"): ("unknown; known subtotal 0", "unknown", GROUPS_COV % gn(3)),
    (RV, "reviewing-class episodes with no positional group"): ("unknown; known subtotal 0", "unknown", NOGROUP_COV),
    (RV, "candidate groups with two or more reviewing-class episodes"): ("unknown; known subtotal 0", "unknown", MULTI_COV),
    (RV, "rounds"): ROUNDS[2:],
    (B, "boundary events"): ("unknown; known subtotal 0", "unknown", "counted at their own timestamps; " + gn(3)),
    (B, "recorded idle unknown"): ("unknown; known subtotal 0", "unknown", IDLEU_COV),
    (B, "over-cap reports"): ("unknown; known subtotal 0", "unknown", OVER_COV % "0 boundaries"),
    (B, "rewrites (deltas)"): ("unknown; known subtotal 0", "unknown", REW_COV % "0 boundaries"),
    (B, "cumulative rewrites snapshots"): ("unknown; known subtotal 0", "unknown", BS_COV % 0),
    (RF, "helper tool"): ("unknown; known subtotal 0", "unknown", "1 close: 1 known, 0 not applicable, 0 unknown or invalid; " + gn(3)),
    (RF, "helper fence"): ("unknown; known subtotal 0", "unknown", "1 close: 1 known, 0 not applicable, 0 unknown or invalid; " + gn(3)),
    (RF, "helper sandbox"): ("unknown; known subtotal 0", "unknown", "1 close: 1 known, 0 not applicable, 0 unknown or invalid; " + gn(3)),
    (RF, "head fence (boundaries)"): ("unknown; known subtotal 0", "unknown", HF_COV % ("0 boundaries", 0, gn(3))),
    (RF, "boundary summary of helper tool refusals"): ("unknown; known subtotal 0", "unknown", HS_COV % ("0 boundaries", gn(3))),
    SP_T: ("unknown; known subtotal $0.00", "unknown", PRICED_COV % ("0 priced closes", "0 priced hold beats", 0, 0, 0, 0, gn(3))),
    SP_PC: ("unknown; known subtotal 1", "unknown", PLAN_COV % (1, 0, 0, 0, 0, 0)),
    SP_TCI: ("unknown; known subtotal 3", "unknown", TOK_COV % (tc(1), 1, 0, pl(0, "close"), gn(3))),
    SP_TCO: ("unknown; known subtotal 3", "unknown", TOK_COV % (tc(1), 1, 0, pl(0, "close"), gn(3))),
    SP_TII: ("unknown; known subtotal 0", "unknown", TOK_COV % (ti(0), 0, 0, pl(0, "close"), gn(3))),
    SP_TIO: ("unknown; known subtotal 0", "unknown", TOK_COV % (ti(0), 0, 0, pl(0, "close"), gn(3))),
    SP_UN: ("unknown; known subtotal 0", "unknown", "token totals only; no dollar figure"),
    SP_NA: ("unknown; known subtotal 0", "unknown", "exit_class spawn-failed"),
    SP_HB: ("unknown; known subtotal 0", "unknown", "plan usage or no process"),
    SP_SS: ("unknown; known subtotal 0", "unknown", SS_COV % 0),
}


@case(5, "event-stream-under-an-admitted-name-read-as-a-record", b17=1)
def t5_named_stream(ctx):
    # An event stream misfiled under an admitted name (an id containing -events-, not pinned) and named
    # as its event log by the close beside it. B17 "does not promise to detect misfiled evidence before
    # opening it": the file is read as a run record, never parsed as evidence, and the reference changes
    # nothing. Its three lines are GPT-6 Astra events with no `event` name and no `ts`, each an invalid,
    # undated line of its own run, named (STREAM_ROWS); the 999999 and 888888 tokens of its
    # turn.completed are never summed or shown. Both files written, each opened once, no breach, no
    # partial total, and both reports byte for byte those of the same fixture without the reference
    # (dashes of its length).
    fx = Fx(ctx.root, "t5-named-stream", script=ctx.script)
    stream = fx.sub("<R>") + "/run-f-events-F.jsonl"
    fx.write("run-f-events-F.jsonl", ['{"type": "thread.started", "thread_id": "t1"}', '{"type": "turn.started"}',
                                      '{"type": "turn.completed", "usage": {"input_tokens": 999999, "cached_input_tokens": 0, '
                                      '"output_tokens": 888888}}'])

    def record(value):
        fx.write("run-f.jsonl", oc("F", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60,
                                   usage={"input_tokens": 3, "output_tokens": 3, "calls": 1}, events=value))
    record("-" * len(stream))
    code, err, opened, base_main, base_detail = fixed_run(ctx, fx, [])
    expect(code == 0 and base_main and base_detail and "FORBIDDEN" not in err,
           "without the reference: exit %d %s" % (code, err.strip()[-300:]))
    record(stream)
    code, err, opened, main, detail = fixed_run(ctx, fx, [])
    expect(code == 0 and main and detail and "FORBIDDEN" not in err, "with it: exit %d %s" % (code, err.strip()[-300:]))
    for name, got, want in (("main report", main, base_main), ("detail", detail, base_detail)):
        expect(bytes_differ(got, want) is None, "the reference changed the %s: %s" % (name, bytes_differ(got, want)))
    expect(record_open_counts(fx, opened) == {"run-f-events-F.jsonl": 1, "run-f.jsonl": 1},
           "record opens %s" % record_open_counts(fx, opened))
    main, detail = main.decode("utf-8"), detail.decode("utf-8")
    e = compare_map(rows_of(main), STREAM_ROWS)
    expect(e is None, e)
    expect(section(detail, "## Named gaps and the figures they affect") == [
        "- run-f-events-F.jsonl:%d · time unknown · no event name (absent) · affects: every figure" % n for n in (1, 2, 3)],
        "named gaps %s" % section(detail, "## Named gaps and the figures they affect"))
    expect("| run-f-events-F.jsonl | read | %d | 3 | - | - | no | 3 | ordered |"
           % os.path.getsize(os.path.join(fx.records, "run-f-events-F.jsonl")) in detail.split("\n"), "the stream's inventory row")
    expect("999999" not in main + detail and "888888" not in main + detail, "an event log's usage was read as evidence")
    expect(not re.search(r"(?i)breach", main + detail) and "partial" not in main + detail, "a breach or a partial total")


def excluded_fixture(fx):
    """Case (b)'s fixture: run-a.jsonl's 60 s close names as evidence seven files outside the inputs:
    in the records folder a pinned event log (`events`), a report (`report`, `.md`) and an event
    stream (`event_log`, `.log`, a bare name); a transcript under the projects folder (`transcript`),
    a brief in a folder of its own (`brief`), and a run-b.jsonl in another folder (`paths.report`) and
    in a subfolder of the records folder (`paths.transcript`, a relative path), each a record-like
    close of 99999 s. run-b.jsonl in the folder holds an independent 30 s episode. Returns the three
    files in the records folder and the four elsewhere, in that order (EXCLUDED_FIELDS)."""
    R = fx.sub("<R>")
    for d in (os.path.join(fx.dir, "briefs"), os.path.join(fx.dir, "outside"), os.path.join(fx.records, "sub")):
        os.makedirs(d)
    q = oc("Q", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", 99999)
    inside = [fx.write(PINNED[0], ['{"type": "thread.started", "thread_id": "t1"}']),
              fx.write("run-a-report-A.md", ["REPORT-MARKER"]),
              fx.write("run-a-events-A.log", ['{"type": "turn.completed"}'])]
    outside = [fx.write(UUID_NAME, ['{"type": "user", "message": "TRANSCRIPT-MARKER"}'], fx.projects),
               fx.write("brief-A.md", ["BRIEF-MARKER"], os.path.join(fx.dir, "briefs")),
               fx.write("run-b.jsonl", q, os.path.join(fx.dir, "outside")),
               fx.write("run-b.jsonl", q, os.path.join(fx.records, "sub"))]
    fx.write("run-a.jsonl", oc("A", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60,
                               events=R + "/" + PINNED[0], report=R + "/run-a-report-A.md",
                               event_log="run-a-events-A.log", transcript=os.path.realpath(outside[0]),
                               brief=os.path.realpath(outside[1]),
                               paths={"report": os.path.realpath(outside[2]), "transcript": "sub/run-b.jsonl"}))
    fx.write("run-b.jsonl", oc("B", "2026-10-06T10:00:00+0100", "2026-10-06T10:00:30+0100", 30))
    return inside, outside


# The fields of run-a's close in excluded_fixture, in the order of the files it returns.
EXCLUDED_FIELDS = (("events", "a pinned event log"), ("report", "a .md in the records folder"),
                   ("event_log", "a .log in the records folder"), ("transcript", "a transcript under the projects folder"),
                   ("brief", "a brief in a folder of its own"), ("paths.report", "a run-b.jsonl in another folder"),
                   ("paths.transcript", "a run-b.jsonl in a subfolder of the records folder"))


@case(5, "excluded-file-named-as-evidence-never-opened", b17=2)
def t5_excluded_named(ctx):
    # B17: "Excluded evidence files remain unopened, including through subprocesses"; spec-D19.md's
    # last section: excluded evidence stays "unopened and irrelevant to every figure". Every one of the
    # seven files run-a.jsonl names (excluded_fixture) is guarded in every run, and none is opened: the
    # reader opens run-a.jsonl and run-b.jsonl, once each. 60 + 30 = 90 s (1.5 min), complete, fixed
    # by hand. Changing all seven (each two record-like closes of 99999 s naming both records as
    # evidence) changes no byte of either report, and neither does removing the four that are not
    # entries of the records folder. Removing the three that are changes exactly the lines that list
    # the folder's own entries, fixed by hand: the candidates line and the pinned log's listing and the
    # count of other entries (main), and the pinned log's inventory row (detail). The folder's listing
    # makes those lines (spec-D19.md, "Scope": every candidate is inventoried), never a reference.
    fx = Fx(ctx.root, "t5-excluded-named", script=ctx.script)
    inside, outside = excluded_fixture(fx)
    guard = inside + outside
    code, err, opened, main, detail = fixed_run(ctx, fx, guard)
    expect(code == 0 and main and detail and "FORBIDDEN" not in err, "guarded exit %d %s" % (code, err.strip()[-300:]))
    expect(record_open_counts(fx, opened) == {"run-a.jsonl": 1, "run-b.jsonl": 1}, "record opens %s" % record_open_counts(fx, opened))
    expect(not set(opened) & set(os.path.realpath(p) for p in guard), "an excluded file was opened")
    e = compare_map(rows_of(main.decode("utf-8")), builder_rows(2, "90 s (1.5 min)", {"run-a": "60 s (1.0 min)", "run-b": "30 s (0.5 min)"},
                                                                {'run-a/"A"': "60 s (1.0 min)", 'run-b/"B"': "30 s (0.5 min)"}))
    expect(e is None, e)
    first = (main, detail)
    for p in guard:
        with open(p, "w") as h:
            for target in ("run-a.jsonl", "run-b.jsonl"):
                h.write(json.dumps({"ts": "2026-10-06T10:00:00+0100", "event": "lane-closed", "lane": "A", "duration_s": 99999,
                                    "events": fx.sub("<R>/" + target), "transcript": fx.sub("<R>/" + target)}) + "\n")
    for step, gone in (("changed", ()), ("removed, outside the folder's entries", outside)):
        for p in gone:
            os.unlink(p)
        code, err, opened, main, detail = fixed_run(ctx, fx, guard)
        expect(code == 0 and "FORBIDDEN" not in err, "%s: guarded exit %d %s" % (step, code, err.strip()[-300:]))
        expect(record_open_counts(fx, opened) == {"run-a.jsonl": 1, "run-b.jsonl": 1}, "%s: record opens %s"
               % (step, record_open_counts(fx, opened)))
        for name, got, want in (("main report", main, first[0]), ("detail", detail, first[1])):
            expect(bytes_differ(got, want) is None, "%s: the %s changed: %s" % (step, name, bytes_differ(got, want)))
    for p in inside:
        os.unlink(p)
    code, err, opened, main, detail = fixed_run(ctx, fx, guard)
    expect(code == 0 and "FORBIDDEN" not in err, "removed, in the folder: guarded exit %d %s" % (code, err.strip()[-300:]))
    lines = first[0].decode("utf-8").split("\n")
    i = lines.index(candidates_line(3, 2, 2, 1))
    expect(lines[i + 1:i + 3] == [pinned_line(1), "  - `%s`" % PINNED[0]], "the pinned log's listing: %s" % lines[i:i + 3])
    lines[i:i + 3] = [candidates_line(2, 2, 2, 0), "- Not admitted by name: 0."]
    lines[lines.index(others_line(3))] = others_line(1)
    expect(bytes_differ(main, "\n".join(lines).encode("utf-8")) is None,
           "removed, in the folder: the main report: %s" % bytes_differ(main, "\n".join(lines).encode("utf-8")))
    rows = first[1].decode("utf-8").split("\n")
    rows.remove("| %s | %s | - | - | - | - | - | - | - |" % (PINNED[0], NOT_ADMITTED_CELL))
    expect(bytes_differ(detail, "\n".join(rows).encode("utf-8")) is None,
           "removed, in the folder: the detail: %s" % bytes_differ(detail, "\n".join(rows).encode("utf-8")))


def follow_mutant(field, launch=False):
    """A planted defect at READ_ANCHOR: each counted close's FIELD (a key path) followed to the file it
    names (read from the record's own folder when relative) and opened, or, with LAUNCH, handed to a
    process that would open it (`/bin/cat`)."""
    body = '''
    for _ep in counted:
        _v = _ep.close.obj
        for _k in %r:
            _v = _v.get(_k) if isinstance(_v, dict) else None
        if isinstance(_v, str):
            _p = os.path.join(os.path.dirname(_ep.rec.path), _v)''' % (field.split("."),)
    if launch:
        body += '''
            import subprocess
            subprocess.run(["/bin/cat", _p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)'''
    else:
        body += '''
            open(_p, "rb").read()'''
    return (READ_ANCHOR, READ_ANCHOR + body)


@case(5, "planted-opens-of-excluded-files-caught", b17=3)
def t5_excluded_controls(ctx):
    # The detector's control on case (b)'s fixture. The reader as built passes under the guard with
    # none of the seven excluded files opened. Then, for each, a planted defect follows the close's
    # field naming it and opens it, and must be caught: exit 97, FORBIDDEN READ naming that file; and
    # another hands it to a process that would open it, caught at the launch (exit 98, FORBIDDEN
    # SUBPROCESS), before any process starts.
    fx = Fx(ctx.root, "t5-excluded-controls", script=ctx.script)
    inside, outside = excluded_fixture(fx)
    guard = inside + outside
    code, out, err, opened = guarded_run(ctx, fx, guard)
    expect(code == 0 and "FORBIDDEN" not in err, "the reader as built: exit %d %s" % (code, err.strip()[-300:]))
    expect(not set(opened) & set(os.path.realpath(p) for p in guard), "the reader as built opened an excluded file")
    missed = []
    for (field, what), path in zip(EXCLUDED_FIELDS, guard):
        reader = mutate(ctx.script, os.path.join(fx.dir, "read-%s.py" % field), [follow_mutant(field)])
        code, out, err, opened = guarded_run(ctx, fx, guard, script=reader)
        if not (code == 97 and "FORBIDDEN READ %s" % os.path.realpath(path) in err):
            missed.append("a planted open of %s (%s): exit %d %s" % (what, field, code, err.strip()[-160:]))
        spawner = mutate(ctx.script, os.path.join(fx.dir, "spawn-%s.py" % field), [follow_mutant(field, launch=True)])
        code, out, err, opened = guarded_run(ctx, fx, guard, script=spawner)
        if not (code == 98 and "FORBIDDEN SUBPROCESS" in err):
            missed.append("a planted process opening %s (%s): exit %d %s" % (what, field, code, err.strip()[-160:]))
    expect(not missed, "%d of 14 planted opens not caught: %s" % (len(missed), "; ".join(missed)))


@case(5, "reference-promise-as-the-contract-states", cr5=5)
def t5_reference_promise(ctx):
    # CR-WASTE5 finding 4: spec-D19.md's last section now says what a reference may and may not change (its
    # bullet "What a reference may and may not change"): a reference, and an excluded file named by one, change
    # no figure, no coverage status and no other substantive report content; the acquisition time, the measured
    # byte counts and the folder inventory are reported as they are. The documents beside the reader state that
    # promise in those words, and no longer the withdrawn one, that a reference changes "no line of either
    # report". (The cases above check more than the promise: byte identity on a fixed clock under substitutions
    # of equal length, and exactly which lines a removal changes.)
    here = os.path.dirname(os.path.abspath(ctx.script))
    for name in ("FIELDS.md", "README.md"):
        text = open(os.path.join(here, name), encoding="utf-8").read()
        expect("no line of either report" not in text, "%s still promises that a reference changes no line of either report" % name)
        missing = [w for w in ("no figure", "no coverage status", "no other substantive report content", "the acquisition time",
                               "the measured byte counts", "the folder inventory") if w not in text]
        expect(not missing, "%s does not state the contract's terms %s" % (name, missing))


@case(5, "any-run-id-admitted", cr3=1)
def t5_any_id(ctx):
    # Under the input contract the run id does not decide: an attended record without the run- prefix, ids holding
    # -events- (not pinned), a lone name and a session-transcript-shaped name in the records folder
    # are all run records, admitted and read: 10 + 20 + 30 + 40 + 50 + 60 = 210 s (3.5 min) over 6
    # closes. The pinned log beside them holds a 99999 s close and is never opened (guarded).
    fx = Fx(ctx.root, "t5-any-id", script=ctx.script)
    names = (("n163-attended-20260918.jsonl", 10), ("run-x-events-y.jsonl", 20), ("RH-1610.jsonl", 30),
             ("a-log.jsonl", 40), (UUID_NAME, 50), ("run-plain.jsonl", 60))
    for name, dur in names:
        fx.write(name, oc("A", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", dur))
    pin = fx.write(PINNED[2], oc("Q", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", 99999))
    code, out, err, opened = guarded_run(ctx, fx, [pin])
    expect(code == 0 and "FORBIDDEN" not in err, "guarded exit %d %s" % (code, err.strip()[-300:]))
    expect(record_opens(fx, opened) == sorted(n for n, d in names), "opened %s" % record_opens(fx, opened))
    main, detail = guarded_reports(fx)
    want = [candidates_line(7, 6, 6, 1), pinned_line(1), "  - `%s`" % PINNED[2], others_line(0),
            "- Records read: 6 with events in the interval, 0 outside it; 6 without run-open (counted like any other)."]
    got = section(main, "## Coverage by reason")[:len(want)]
    expect(got == want, "coverage:\n%s" % first_difference(got, want))
    expect(as_map(rows_of(main))[(H, "total")] == ("210 s (3.5 min)", "complete",
                                                   "6 closes: 6 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0),
           "total %r" % (as_map(rows_of(main))[(H, "total")],))


@case(5, "links-never-followed", cr3=1)
def t5_links(ctx):
    # A symbolic link among the candidates is never followed, whatever its target: one to a file
    # outside the records folder (a record-like close of 99999 s, guarded), one to a pinned event log
    # in the folder (guarded) and one to run-real.jsonl beside it. Each is named unreadable, not
    # opened, a named gap of its own run in every report. The pinned log itself is listed, and
    # run-real.jsonl is opened once (an open through the inner link would be a second). Helper time
    # is run-real's 60 s, a known subtotal beside the three gaps.
    fx = Fx(ctx.root, "t5-links", script=ctx.script)
    os.makedirs(os.path.join(fx.dir, "outside"))
    target = fx.write("target.jsonl", oc("Q", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", 99999),
                      os.path.join(fx.dir, "outside"))
    pin = fx.write(PINNED[0], oc("Q", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", 99999))
    real = fx.write("run-real.jsonl", oc("R", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60))
    for link, to in (("run-link.jsonl", target), ("run-pin-link.jsonl", pin), ("run-inner-link.jsonl", real)):
        os.symlink(to, os.path.join(fx.records, link))
    code, out, err, opened = guarded_run(ctx, fx, [target, pin])
    expect(code == 0 and "FORBIDDEN" not in err, "guarded exit %d %s" % (code, err.strip()[-300:]))
    recs = os.path.realpath(fx.records) + os.sep
    expect([o for o in opened if o.startswith(recs)] == [recs + "run-real.jsonl"], "opened %s" % [o for o in opened if o.startswith(recs)])
    main, detail = guarded_reports(fx)
    for link in ("run-inner-link.jsonl", "run-link.jsonl", "run-pin-link.jsonl"):
        expect("| %s | %s | - | - | - | - | - | - | - |" % (link, NOT_FOLLOWED_CELL) in detail, "inventory row of %s" % link)
    want = [candidates_line(5, 4, 1, 1, unreadable=3), pinned_line(1), "  - `%s`" % PINNED[0], others_line(0)]
    got = section(main, "## Coverage by reason")[:len(want)]
    expect(got == want, "coverage:\n%s" % first_difference(got, want))
    expect(section(detail, "## Named gaps and the figures they affect") == [
        "- %s · time unknown · record unreadable: a symbolic link, never followed (FIELDS.md, \"Admission\"); not opened · "
        "affects: every figure · named in every report" % link
        for link in ("run-inner-link.jsonl", "run-link.jsonl", "run-pin-link.jsonl")],
        "named gaps %s" % section(detail, "## Named gaps and the figures they affect"))
    expect(as_map(rows_of(main))[(H, "total")] == ("unknown; known subtotal 60 s (1.0 min)", "unknown",
                                                   "1 close: 1 timed, 0 not applicable, 0 unknown or invalid; 3 named gaps (detail)"),
           "total %r" % (as_map(rows_of(main))[(H, "total")],))


READ_ANCHOR = '''    counted = [ep for ep in an["episodes"] if start <= ep.close.ts < end]'''
READ_MUTANT = (READ_ANCHOR, READ_ANCHOR + '''
    for ep in counted:
        if isinstance(ep.close.obj.get("transcript"), str):
            try:
                open(ep.close.obj["transcript"]).read()
            except OSError:
                pass''')
SPAWN_MUTANT = (READ_ANCHOR, READ_ANCHOR + '''
    import subprocess
    for ep in counted:
        if isinstance(ep.close.obj.get("events"), str):
            subprocess.run(["/bin/cat", ep.close.obj["events"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)''')
SPAWN_PATTERN = re.compile(r"\bimport\s+(?:subprocess|pty|ctypes|multiprocessing)\b|\bfrom\s+(?:subprocess|pty|ctypes|multiprocessing)\s+import"
                           r"|\bsubprocess\.[A-Za-z_]|\bpty\.[A-Za-z_]|\bctypes\.[A-Za-z_]|\bos\.(?:system|popen|exec\w*|spawn\w*|posix_spawn\w*|fork\w*)\s*\(")


def mutate(src_path, dest, pairs):
    src = open(src_path, encoding="utf-8").read()
    for old, new in pairs:
        n = src.count(old)
        if n != 1:
            raise AssertionError("mutation anchor found %d times: %s" % (n, old[:60]))
        src = src.replace(old, new)
    with open(dest, "w", encoding="utf-8") as h:
        h.write(src)
    return dest


@case(5, "detector-controls-and-source-grep")
def t5_controls(ctx):
    fx = Fx(ctx.root, "t5-controls", script=ctx.script)
    refs = scene_a(fx)
    reader = mutate(ctx.script, os.path.join(fx.dir, "read-mutant.py"), [READ_MUTANT])
    code, out, err, opened = guarded_run(ctx, fx, refs, script=reader)
    expect(code == 97 and "FORBIDDEN READ %s" % os.path.realpath(refs[0]) in err,
           "the planted transcript read was not caught: %d %s" % (code, err[-200:]))
    spawner = mutate(ctx.script, os.path.join(fx.dir, "spawn-mutant.py"), [SPAWN_MUTANT])
    code, out, err, opened = guarded_run(ctx, fx, refs, script=spawner)
    expect(code == 98 and "FORBIDDEN SUBPROCESS" in err, "the planted subprocess was not caught: %d %s" % (code, err[-200:]))
    clean_hits = SPAWN_PATTERN.findall(open(ctx.script, encoding="utf-8").read())
    control_hits = SPAWN_PATTERN.findall(open(spawner, encoding="utf-8").read())
    expect(not clean_hits, "the reader's source names a process launcher: %s" % clean_hits)
    expect(control_hits, "the source probe missed the planted subprocess (control)")


# ------------------------------------------------------------------------ test 6 -----------

@case(6, "sandbox-refusals-with-zero-boundary-denials")
def t6_sandbox(ctx):
    # Two GPT-6 Astra closes with sandbox refusals 2 and 1 (3); the boundary's helper summary
    # (tool refusals only, handsoff.py:3354-3360) and its head fence count are 0 and 4.
    fx = Fx(ctx.root, "t6-sandbox", script=ctx.script)
    fx.write("run-s.jsonl", [{"ts": "2026-10-06T09:00:00+0100", "event": "run-open", "session": "h", "session_kind": "head"}]
             + oc("S1", "2026-10-06T10:00:00+0100", "2026-10-06T10:10:00+0100", 1, sandbox_denials=2,
                  denials={"tool": 0, "fence": 0, "sandbox": 2})
             + oc("S2", "2026-10-06T10:00:00+0100", "2026-10-06T10:20:00+0100", 1, sandbox_denials=1,
                  denials={"tool": 0, "fence": 0, "sandbox": 1})
             + [{"ts": "2026-10-06T11:00:00+0100", "event": "phase-boundary", "idle_min": 0, "idle_src": "transcript",
                 "denials": 0, "head_denials": 4, "over_cap_reports": 0, "rewrites": 0}])
    code, out, err, main, detail = fx.report()
    m = as_map(rows_of(main))
    two = "2 closes: 2 known, 0 not applicable, 0 unknown or invalid; " + GAPS0
    expect(m[(RF, "helper sandbox")] == ("3", "complete", two), "sandbox %r" % (m[(RF, "helper sandbox")],))
    expect(m[(RF, "helper tool")] == ("0", "complete", two), "tool")
    expect(m[(RF, "helper fence")] == ("0", "complete", two), "fence: the head's count is not added")
    expect(m[(RF, "head fence (boundaries)")][0] == "4", "head fence")
    expect(m[(RF, "boundary summary of helper tool refusals")][0] == "0", "summary")


@case(6, "reviewers-and-resumed-critic-make-no-rounds", cr1=5)
def t6_rounds(ctx):
    # Item x: critics C1, C2, C3 and C1 resumed, all after one allowed gate = 4 reviewing-class
    # episodes from 3 helpers in one positional candidate group: a cue, not a loop, rounds
    # unresolved, and no round number anywhere.
    fx = Fx(ctx.root, "t6-rounds", script=ctx.script)
    evs = [{"ts": "2026-10-06T09:00:00+0100", "event": "gate", "item": "x", "decision": "allow", "run_spend_usd": 1.0}]
    for lane, a, b in (("C1", "10:00", "10:10"), ("C2", "10:00", "10:20"), ("C3", "10:30", "10:40")):
        pair = oc(lane, "2026-10-06T%s:00+0100" % a, "2026-10-06T%s:00+0100" % b, 60)
        pair[0]["class"] = pair[1]["class"] = "critic"
        evs += pair
    again = oc("C1", "2026-10-06T11:00:00+0100", "2026-10-06T11:10:00+0100", 60)
    again[0]["event"] = "lane-resumed"
    again[0]["class"] = again[1]["class"] = "critic"
    fx.write("run-rv.jsonl", evs + again)
    code, out, err, main, detail = fx.report()
    expect('- run-rv · item x · 4 reviewing-class episodes from 3 helpers ("C1" critic, "C2" critic, "C3" critic) · gate line 1 · grouped by '
           "position, not an evidenced association · two or more: a cue for the Sunday walk-through, not an evidenced loop · "
           "rounds unresolved" in detail, "group line")
    rows = [r for r in rows_of(main) if r[0] == RV]
    expect(rows == [(RV, "reviewing-class episodes", "4", "complete", RVC_COV % ("0 closes", GAPS0)), EVID,
                    (RV, "positional candidate groups", "1", "complete", GROUPS_COV % GAPS0),
                    (RV, "reviewing-class episodes with no positional group", "0", "complete", NOGROUP_COV),
                    (RV, "candidate groups with two or more reviewing-class episodes", "1", "complete", MULTI_COV), ROUNDS],
           "review rows %r" % rows)
    pat = re.compile(r"\b\d+\s+rounds?\b|\bround\s+\d|\brounds?\s*[:=]\s*\d", re.I)
    expect(not pat.search(main) and not pat.search(detail), "a round count was rendered")
    expect("CUSTOMISATION.md's rules \"Rounds are judged by progress, not counted\" and \"Stopped designs\"" in main, "guidance names the rules")
    expect("Review activity by recorded item" not in detail and "· possible loop ·" not in detail, "old item wording rendered")


@case(6, "refused-gate-interleaved-work-and-probe", cr1=5)
def t6_proxies(ctx):
    # run-rv2.jsonl: after the allowed gate for item1, the critic CR-T and a one-word availability probe
    # P-ASTRA of class verifier (both reviewing-class by class alone; neither shown to be a review);
    # after the refused gate for item2, the critic CR-R (no positional group: the head did not
    # enter item2); after the allowed gate for item3, the critic CR-I, whose span holds the gate for
    # item4 (no positional group: interleaved); then non-review work, the builder B-W. Reviewing-
    # class episodes 4; one positional group (item1, 2 episodes); 2 with no group, which leaves the
    # group counts known subtotals; no evidenced association; rounds unresolved.
    fx = Fx(ctx.root, "t6-proxies", script=ctx.script)
    def g(ts, item, decision):
        return {"ts": ts, "event": "gate", "item": item, "decision": decision, "run_spend_usd": 1.0}
    def op(ts, lane, cls, **kw):
        return dict({"ts": ts, "event": "lane-open", "lane": lane, "class": cls, "harness": "codex"}, **kw)
    def cl(ts, lane, cls, dur):
        return oc(lane, "x", ts, dur, **{"class": cls})[1]
    fx.write("run-rv2.jsonl", [
        g("2026-10-06T09:00:00+0100", "item1", "allow"),
        op("2026-10-06T09:01:00+0100", "CR-T", "critic"),
        op("2026-10-06T09:02:00+0100", "P-ASTRA", "verifier", reason="(b) an availability probe; one-word reply"),
        cl("2026-10-06T09:02:05+0100", "P-ASTRA", "verifier", 5.0),
        cl("2026-10-06T09:30:00+0100", "CR-T", "critic", 1680),
        g("2026-10-06T09:40:00+0100", "item2", "refuse"),
        op("2026-10-06T09:41:00+0100", "CR-R", "critic"),
        cl("2026-10-06T09:50:00+0100", "CR-R", "critic", 540),
        g("2026-10-06T10:00:00+0100", "item3", "allow"),
        op("2026-10-06T10:01:00+0100", "CR-I", "critic"),
        g("2026-10-06T10:30:00+0100", "item4", "allow"),
        cl("2026-10-06T10:40:00+0100", "CR-I", "critic", 2340),
        op("2026-10-06T10:41:00+0100", "B-W", "builder"),
        cl("2026-10-06T10:50:00+0100", "B-W", "builder", 540),
    ])
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d %s" % (code, err))
    for needle in ('- run-rv2 "CR-R" (critic) · no positional group: the last gate before its opening (line 6) refused item item2',
                   '- run-rv2 "CR-I" (critic) · no positional group: a gate at line 11 lies between its opening and its close',
                   '- run-rv2 · item item1 · 2 reviewing-class episodes from 2 helpers ("CR-T" critic, "P-ASTRA" verifier) · gate line 1 · '
                   "grouped by position, not an evidenced association · two or more: a cue for the Sunday walk-through, not an "
                   "evidenced loop · rounds unresolved",
                   "- Evidenced item associations: none recorded.",
                   "- Reviewing-class episodes are counted by class alone (critic, verifier, gate-judge); a class is not evidence "
                   "that an episode reviewed anything."):
        expect(needle in detail, "detail lacks: %s" % needle)
    rows = [r for r in rows_of(main) if r[0] == RV]
    expect(rows == [(RV, "reviewing-class episodes", "4", "complete", RVC_COV % ("0 closes", GAPS0)), EVID,
                    (RV, "positional candidate groups", "unknown; known subtotal 1", "unknown", GROUPS_COV % GAPS0),
                    (RV, "reviewing-class episodes with no positional group", "2", "complete", NOGROUP_COV),
                    (RV, "candidate groups with two or more reviewing-class episodes", "unknown; known subtotal 1", "unknown", MULTI_COV),
                    ROUNDS], "review rows %r" % rows)
    expect('| run-rv2:"B-W":13 | builder |' in detail, "the builder's row")
    expect("item2" not in "\n".join(l for l in detail.split("\n") if l.startswith("- run-rv2 · item")), "the refused item formed a group")


@case(6, "non-completed-resumed-keeps-cost-no-verdict")
def t6_lost(ctx):
    # W closes at its limit after $3.00 and 100 s, is resumed on its session and completes 50 s later, its close
    # carrying the session's running total, $4.00 (haiku's one-off entry carried over unchanged, so the session
    # reads as running totals; FIELDS.md, "Priced spend"): $4.00 and 150 s stand, the non-completed pass's cost
    # inside them, one non-completed close later resumed, and no verdict on lost work.
    fx = Fx(ctx.root, "t6-lost", script=ctx.script)
    c = {"class": "builder", "cost_src": "result", "denials": {"tool": 0, "fence": 0, "fence_allows": 0}, "session_id": "s-w"}
    used = lambda opus: {"modelUsage": {"opus": entry(opus), "haiku": entry(Raw("0.10"))}, "calls": 1}
    fx.write("run-w.jsonl", [
        {"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "W", "class": "builder", "session_id": "s-w"},
        dict(c, ts="2026-10-06T10:02:00+0100", event="lane-closed", lane="W", exit_class="limit", duration_s=100,
             total_cost_usd=3.0, usage=used(Raw("2.90"))),
        {"ts": "2026-10-06T11:00:00+0100", "event": "lane-resumed", "lane": "W", "class": "builder", "session_id": "s-w"},
        dict(c, ts="2026-10-06T11:01:00+0100", event="lane-closed", lane="W", exit_class="completed", duration_s=50,
             total_cost_usd=4.0, usage=used(Raw("3.90")))])
    code, out, err, main, detail = fx.report()
    m = as_map(rows_of(main))
    expect(m[SP_T][:2] == ("$4.00", "complete"), "spend")
    expect(m[(H, "total")][0] == "150 s (2.5 min)", "time")
    expect(m[(F, "non-completed, later resumed")][0] == "1", "resumed")
    text = (main + detail).replace(
        "It does not measure avoidable time or certify that a week contained no waste.", "").replace(
        "no verdict on lost work", "")
    for word in ("lost work", "wasted", "avoidable", "waste-free", "no waste", "clean"):
        expect(word not in text.lower(), "verdict wording %r rendered" % word)


# ------------------------------------------------------------------------ test 8 -----------

@case(8, "store-survives-reruns-and-empty-intervals")
def t8_store(ctx):
    fx = Fx(ctx.root, "t8-store", script=ctx.script)
    scene_a(fx)
    code, out, err, main, detail = fx.report()
    expect(code == 0, "first run %d" % code)
    store = os.path.join(fx.tools, "dispositions.jsonl")
    code, out, err = fx.run("dispose", "refusals@2026-10-05..2026-10-12", "kept", "--note", "sandbox channel not recorded by lane.py")
    expect(code == 0, "dispose %d %s" % (code, err))
    snap = open(store, "rb").read()
    code, out, err, main, detail = fx.report()
    expect(code == 0 and "- refusals@2026-10-05..2026-10-12: listed by this report; disposed: kept (sandbox channel not recorded by lane.py)" in main,
           "rerun lost the disposition")
    expect(open(store, "rb").read().startswith(snap), "the store was rewritten, not appended")
    # No earlier interval's report precedes this rerun, so every disposition in the store is new.
    since = section(main, "## Dispositions")
    i = since.index("Recorded since the previous report:")
    expect(since[i + 1:i + 2] == ["- refusals@2026-10-05..2026-10-12: kept (sandbox channel not recorded by lane.py)"], "since %r" % since[i:])
    code, out, err = fx.run("dispose", "phase-boundaries@2026-10-05..2026-10-12", "registered", "--note", "known-issues entry")
    expect(code == 0, "second dispose %d %s" % (code, err))
    # An empty interval after it carries the open keys, and the disposed ones stay disposed; the
    # disposition recorded after the previous report is listed as such.
    code, out, err, main, detail = fx.report(since=None, until="2026-10-19")
    expect(code == 0, "empty interval %d %s" % (code, err))
    expect("- Interval: [2026-10-12 00:00 +0100, 2026-10-19 00:00 +0100), local time (GMT/BST)." in main, "since from the store")
    keys = dispositions_lines(main)
    want = ["- %s@2026-10-05..2026-10-12: open, carried from an earlier report" % k for k in
            ("coverage", "failed-closes", "helper-time", "priced-spend", "review-activity")]
    expect(keys[:5] == want, "carried keys %r" % keys[:5])
    expect("refusals@2026-10-05..2026-10-12: open" not in main and "phase-boundaries@2026-10-05..2026-10-12: open" not in main,
           "a disposed key reopened")
    since = section(main, "## Dispositions")
    i = since.index("Recorded since the previous report:")
    expect(since[i + 1:i + 2] == ["- phase-boundaries@2026-10-05..2026-10-12: registered (known-issues entry)"], "since %r" % since[i:])


@case(8, "missing-store-is-not-reinitialised")
def t8_missing(ctx):
    fx = Fx(ctx.root, "t8-missing", script=ctx.script)
    scene_a(fx)
    store = os.path.join(fx.tools, "dispositions.jsonl")
    os.unlink(store)
    code, out, err, main, detail = fx.report()
    expect(code == 1, "exit %d" % code)
    expect(not os.path.exists(store), "a missing store was recreated")
    expect(main.split("\n")[4].startswith("**Store continuity failure:** there is no store at"), "report does not open with the failure")
    code, out, err = fx.run("dispose", "refusals@2026-10-05..2026-10-12", "kept", "--note", "x")
    expect(code == 2 and not os.path.exists(store), "dispose on a missing store %d" % code)
    with open(store, "w") as h:
        h.write('{"kind": "init", "at": "2026-10-01T00:00:00+0100", "version": "x"}\nnot json\n')
    code, out, err, main, detail = fx.report()
    expect(code == 1 and "store-continuity@2026-10-05..2026-10-12: listed by this report; open" in main, "malformed store %d" % code)
    code, out, err = fx.run("init")
    expect(code == 2 and "never overwrites" in err, "init over an existing store %d %s" % (code, err))
    code, out, err = fx.run("init", tools=os.path.join(fx.dir, "no-such-folder"))
    expect(code == 2 and "PROBE FAILED: no tools folder" in err and not os.path.exists(os.path.join(fx.dir, "no-such-folder")),
           "init into a missing folder %d %s" % (code, err))


@case(8, "subcommand-refusals", finding=1, cr3=1)
def t8_refusals(ctx):
    fx = Fx(ctx.root, "t8-refuse", script=ctx.script)
    scene_a(fx)
    fx.write("run-openq.jsonl", [{"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "Q", "class": "builder"}])
    fx.write("run-broken.jsonl", [{"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "Q", "class": "builder"}, "nope"])
    os.symlink(os.path.join(fx.records, "run-openq.jsonl"), os.path.join(fx.records, "run-linked.jsonl"))
    fx.report()
    store = os.path.join(fx.tools, "dispositions.jsonl")
    before = open(store, "rb").read()
    for args, needle in (
        (("dispose", "refusal@2026-10-05..2026-10-12", "kept", "--note", "x"), "nearest: refusals@2026-10-05..2026-10-12"),
        (("dispose", "refusals@2026-10-05..2026-10-12", "kept", "--note", " "), "--note is empty"),
        (("dispose", "refusals@2026-10-05..2026-10-12", "maybe", "--note", "x"), "invalid choice"),
        (("abandon", "run-openq:Q:1", "--evidence", ""), "--evidence is empty"),
        (("abandon", "run-openq:Q:9", "--evidence", "pid gone"), "no open opening of Q at line 9"),
        (("abandon", "run-a:B1:3", "--evidence", "pid gone"), "is closed"),
        (("abandon", "run-broken:Q:1", "--evidence", "pid gone"), "holds 1 invalid or undated lines"),
        (("end-run", "run-a", "--evidence", "pid gone"), "is closed on its record"),
        (("end-run", "run-plain-b", "--evidence", "pid gone"), "has no run-open"),
        # A pinned event log is not admitted (the input contract): refused by name, never opened; so is a name with a
        # path in it. A link among the candidates is never followed (run-linked.jsonl names run-openq,
        # whose Q:1 is open: followed, the abandonment would be recorded).
        (("end-run", PINNED[3][:-len(".jsonl")], "--evidence", "pid gone"), "is not admitted as a run record by its name"),
        (("abandon", PINNED[3][:-len(".jsonl")] + ":N1:1", "--evidence", "pid gone"), "is not admitted as a run record by its name"),
        (("abandon", 'run-a/".."/' + PINNED[3][:-len(".jsonl")] + ":N1:1", "--evidence", "pid gone"),
         "is not admitted as a run record by its name"),
        (("abandon", "run-linked:Q:1", "--evidence", "pid gone"), "is a symbolic link, never followed, so it is never opened"),
    ):
        code, out, err = fx.run(*args)
        expect(code == 2 and needle in err, "%s: %d %s" % (" ".join(args), code, err.strip()))
    expect(open(store, "rb").read() == before, "a refusal wrote to the store")


def future_interval():
    since = time.strftime("%Y-%m-%d", time.localtime(time.time() + 8 * 86400))
    until = time.strftime("%Y-%m-%d", time.localtime(time.time() + 15 * 86400))
    return since, until


@case(8, "determinations-applied-voided-listed")
def t8_determinations(ctx):
    fx = Fx(ctx.root, "t8-determine", script=ctx.script)
    rec = fx.write("run-hang.jsonl", [
        {"ts": "2026-10-06T09:00:00+0100", "event": "run-open", "session": "h", "session_kind": "head"},
        {"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "Q", "class": "builder"}])
    code, out, err = fx.run("abandon", "run-hang:Q:2", "--evidence", "wrapper and lane pids gone, checked by ps")
    expect(code == 0, "abandon %d %s" % (code, err))
    code, out, err = fx.run("end-run", "run-hang", "--evidence", "head pid gone; no event since")
    expect(code == 0, "end-run %d %s" % (code, err))
    since, until = future_interval()
    code, out, err, main, detail = fx.report(since=since, until=until)
    expect('- run-hang:"Q":2 · open · opened' not in detail, "abandoned episode still listed after the determination")
    expect('abandoned "run-hang:Q:2" at' in main and "applied: left out of the open list" in main
           and "wrapper and lane pids gone, checked by ps" in main, "abandon not listed")
    expect("run-ended run-hang at" in main and "applied: the run is listed as ended" in main, "run-ended not listed")
    expect("Runs open at acquisition: 0." in main, "run still open")
    code, out, err, main, detail = fx.report()
    expect('- run-hang:"Q":2 · open · opened 2026-10-06 10:00:00 +0100 · no close on the record' in detail, "earlier interval drops the episode")
    expect("recorded, not yet applicable" in main, "earlier interval note")
    with open(rec, "a") as h:
        h.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() + 60)), "event": "observation"}) + "\n")
    code, out, err, main, detail = fx.report(since=since, until=until)
    expect('- run-hang:"Q":2 · open · opened' in detail and "void: an event after the determination" in main, "abandon not voided")
    expect("void: its record changed after the determination" in main, "run-ended not voided")


@case(8, "abandonment-voided-by-same-timestamp-append", cr1=7)
def t8_same_ts(ctx):
    # Writer timestamps have second resolution, so an appended event can carry the record's last
    # timestamp exactly. The determination holds its record's extent (2 lines), so that append
    # voids it, effect and evidence still listed; the unchanged record keeps it applied (control).
    fx = Fx(ctx.root, "t8-same-ts", script=ctx.script)
    rec = fx.write("run-hang2.jsonl", [
        {"ts": "2026-10-06T09:00:00+0100", "event": "run-open", "session": "h", "session_kind": "head"},
        {"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "Q", "class": "builder"}])
    code, out, err = fx.run("abandon", "run-hang2:Q:2", "--evidence", "lane pid gone, checked by ps")
    expect(code == 0, "abandon %d %s" % (code, err))
    since, until = future_interval()
    code, out, err, main, detail = fx.report(since=since, until=until)
    expect("applied: left out of the open list" in main and '- run-hang2:"Q":2 · open · opened' not in detail, "control: not applied")
    with open(rec, "a") as h:
        h.write(json.dumps({"ts": "2026-10-06T10:00:00+0100", "event": "observation", "what": "the same second"}) + "\n")
    code, out, err, main, detail = fx.report(since=since, until=until)
    expect('abandoned "run-hang2:Q:2" at' in main and "void: an event after the determination is on its record; the episode is named as open again. Evidence: lane pid gone, checked by ps" in main,
           "the same-timestamp append did not void the abandonment")
    expect('- run-hang2:"Q":2 · open · opened 2026-10-06 10:00:00 +0100 · no close on the record' in detail, "the episode is not named open again")


@case(8, "install-like-run-and-undo")
def t8_install(ctx):
    # Copy the files into a scratch vault's shipped skill folder, init there, run with no --tools-dir,
    # follow the report's link to its detail, dispose a key, re-run, then undo back to the prior tree.
    # The store goes to the run store and the reports to the vault's output/reports, never beside the
    # script, whose folder ships.
    fx = Fx(ctx.root, "t8-install", init=False, script=ctx.script)
    scene_a(fx)
    parent = os.path.join(fx.dir, "vault-root")
    os.makedirs(parent)
    with open(os.path.join(parent, "keep.txt"), "w") as h:
        h.write("an existing tool\n")
    before = tree_manifest(parent)
    target = os.path.join(parent, ".claude", "skills", "weekly-audit")
    os.makedirs(target)
    for name in ("weekly-waste.py", "FIELDS.md", "README.md", "test_weekly_waste.py"):
        src = ctx.script if name == "weekly-waste.py" else os.path.join(HERE, name)
        shutil.copy2(src, os.path.join(target, name))
    installed = os.path.join(target, "weekly-waste.py")
    env = dict(fx.env())
    store_tools = os.path.join(env["LLM_WIKI_STORE"], "tools", "weekly-waste")
    reports = os.path.join(parent, "output", "reports")
    os.makedirs(store_tools)   # setup.sh makes the store's folder and the skeleton holds output/
    os.makedirs(os.path.dirname(reports))
    p = subprocess.run([PY, "-I", "-B", installed, "init"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    expect(p.returncode == 0 and os.path.isfile(os.path.join(store_tools, "dispositions.jsonl")), "init %s" % p.stderr)
    expect(os.path.isdir(reports), "init made no reports folder")
    shipped = tree_manifest(target)
    p = subprocess.run([PY, "-I", "-B", installed, "--records", fx.records, "--since", SINCE, "--until", UNTIL],
                       env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    expect(p.returncode == 0, "report %s" % p.stderr)
    main = open(os.path.join(reports, "waste-report-2026-10-12.md"), encoding="utf-8").read()
    link = re.search(r"- Detail: \[([^\]]+)\]\(([^)]+)\)", main)
    expect(link and os.path.isfile(os.path.join(reports, link.group(2))), "the report's detail link is broken")
    expect_rows(main, SCENE_A_ROWS)
    p = subprocess.run([PY, "-I", "-B", installed, "dispose", "coverage@2026-10-05..2026-10-12", "registered", "--note", "known-issues entry"],
                       env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    expect(p.returncode == 0, "dispose %s" % p.stderr)
    expect(tree_manifest(target) == shipped, "a report or the store landed in the shipped skill folder")
    readme = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    for pin in ("python3 -B .claude/skills/weekly-audit/weekly-waste.py", "## Install", "## Undo",
                "CALENDAR.md", "check-lifecycle.md"):
        expect(pin in readme, "README lacks %r" % pin)
    shutil.rmtree(os.path.join(parent, ".claude"))
    shutil.rmtree(os.path.join(parent, "output"))
    shutil.rmtree(store_tools)
    expect(tree_manifest(parent) == before, "undo left the vault changed")


@case(8, "per-run-tables-linked-never-opened-bytes-unchanged", finding=5, cr3=4)
def t8_tables(ctx):
    # Finding 5 of CR-WASTE2 and finding 4 of CR-WASTE3: per-run waste tables in a folder of their own
    # (--tables-dir) are linked by path for the runs with events in the interval (run-ta, run-tb and,
    # under the input contract, the attended record n163-attended-20260918, whose run id lacks the run- prefix: three;
    # run-tc's only event is in September and run-zz has no record, so neither table is linked),
    # never opened (every table guarded under the audit hook, in two runs) and left byte for byte as
    # they were: sha256, size, mtime, ctime and inode of all five, before and after both runs.
    fx = Fx(ctx.root, "t8-tables", script=ctx.script)
    fx.write("run-ta.jsonl", oc("A", "2026-10-06T10:00:00+0100", "2026-10-06T10:01:00+0100", 60))
    fx.write("run-tb.jsonl", oc("B", "2026-10-07T10:00:00+0100", "2026-10-07T10:02:00+0100", 120))
    fx.write("run-tc.jsonl", oc("C", "2026-09-07T10:00:00+0100", "2026-09-07T10:03:00+0100", 180))
    fx.write("n163-attended-20260918.jsonl", oc("N", "2026-10-08T10:00:00+0100", "2026-10-08T10:01:00+0100", 60))
    tables = os.path.join(fx.dir, "tables")
    os.makedirs(tables)
    paths = [fx.write("%s-waste-table.md" % stem, ["| table | of %s |" % stem, "TABLE-MARKER"], tables)
             for stem in ("n163-attended-20260918", "run-ta", "run-tb", "run-tc", "run-zz")]
    sums = lambda: [(hashlib.sha256(open(p, "rb").read()).hexdigest(), os.stat(p).st_size, os.stat(p).st_mtime_ns,
                     os.stat(p).st_ctime_ns, os.stat(p).st_ino) for p in paths]
    before = sums()
    for n in (1, 2):
        code, out, err, opened = guarded_run(ctx, fx, paths, extra=("--tables-dir", tables))
        expect(code == 0 and "FORBIDDEN" not in err, "run %d: guarded exit %d %s" % (n, code, err.strip()[-300:]))
        expect(not [o for o in opened if o.startswith(os.path.realpath(tables) + os.sep)], "a table was opened: %s" % opened)
    expect(sums() == before, "a table changed: %s -> %s" % (before, sums()))
    main, detail = guarded_reports(fx)
    T = os.path.realpath(tables)
    want = ["- %s: [%s-waste-table.md](<%s/%s-waste-table.md>)" % (stem, stem, T, stem)
            for stem in ("n163-attended-20260918", "run-ta", "run-tb")]
    expect(section(detail, "## Per-run waste tables (linked by path, never read)") == want,
           "links %r" % section(detail, "## Per-run waste tables (linked by path, never read)"))
    expect("3 linked in the detail (each run's own table, by path, never regenerated or read)." in main.split("\n"), "link count")


# ------------------------------------------------------------------------ CR-WASTE6 ---------
# B-WASTE16's fold of the closed review CR-WASTE6. An episode is its (record, helper, opening line); the held
# format's episode string, `<record>:<helper>:<line>`, which a record or a helper holding ":" can make name
# several openings, applies only where it names one (finding 1). The held design's abandoned line, which has no
# line count, is read as that format writes it, the check it cannot make named (finding 2). The total row of each
# helper-time view is a label apart from every recorded run, class and helper (finding 3). Each finding's family
# is closed beside it (brief item 4): identities built from recorded values (family 1), labels against the
# recorded values that share their place (2), the formats the specification names (3), and the generated
# records (4, in test 4). Every expected line is fixed by hand from README.md and FIELDS.md, never by the reader.

OPENED = "2026-10-03T10:00:00+0100"           # an opening a determination names, before the interval
OPENED_TEXT = "2026-10-03 10:00:00 +0100"
DECIDED = "2026-10-04T12:00:00+0100"          # the determination: after the opening, before [2026-10-05, 2026-10-12)
EVIDENCE = "lane pid gone, checked by ps"
# The effects the main report names (README.md, "The dispositions store"), written out here. HELD_LIMIT is what
# a held-format line, with no line count of its record, leaves unchecked.
APPLIED = "applied: left out of the open list (this interval begins after the determination)"
VOIDED = "void: an event after the determination is on its record; the episode is named as open again"
PENDING = ("recorded, not yet applicable: this interval begins before the determination, so the episode stays "
           "named, incomplete, duration unknown")
HELD_LIMIT = ("; held format, with no line count of its record: an event added later at or before the record's "
              "last event then (the same second, or out of order) cannot be detected")
R_X = 'record \'r.jsonl\', helper "x:y", line 1'          # the two openings r:x:y:1 can name, each part by its repr
RX_Y = 'record \'r:x.jsonl\', helper "y", line 1'


def opening_only(lane, ts=OPENED):
    return [{"ts": ts, "event": "lane-open", "lane": lane, "class": "builder"}]


def abandoned(episode, at=DECIDED, last=OPENED, record_lines=None, evidence=EVIDENCE, **identity):
    """An abandoned store line: the held format's fields (episode, evidence, at, last_event, record_last_event),
    with the record's line count and the structured identity (record, helper, line) where given, as the
    reader's own `abandon` writes them."""
    line = {"kind": "abandoned", "episode": episode, "evidence": evidence, "at": at, "last_event": last,
            "record_last_event": last}
    if record_lines is not None:
        line["record_lines"] = record_lines
    line.update(identity)
    return line


def append_store_lines(fx, lines):
    with open(os.path.join(fx.tools, "dispositions.jsonl"), "a", encoding="utf-8") as h:
        for line in lines:
            h.write((line if isinstance(line, str) else json.dumps(line)) + "\n")


def open_entry(text, opened=OPENED_TEXT, why="no close on the record"):
    """An open episode's line in the detail."""
    key, sep, rest = text.partition(" (record ")
    if sep:
        text = (key if key.startswith('"') else json.dumps(key, ensure_ascii=True)) + sep + rest
    elif not re.search(r':".*":', key):
        stem, lane, number = key.rsplit(":", 2)
        text = stem + ":" + json.dumps(lane, ensure_ascii=True) + ":" + number
    return "- %s · open · opened %s · %s" % (text, opened, why)


def determination_entry(what, effect, at=DECIDED, evidence=EVIDENCE, kind="abandoned"):
    """A determination's line in the main report."""
    if kind == "abandoned":
        key, sep, rest = what.partition(" (record ")
        what = json.dumps(key, ensure_ascii=True) + (sep + rest if sep else "")
    return "- %s %s at %s: %s. Evidence: %s" % (kind, what, at, effect, evidence)


def open_count_line(n):
    return ("- Episodes open or unresolved at acquisition: %d (0 opened after the interval's end; 0 unresolved by "
            "an invalid close or opening), named in the detail; such an episode counts nowhere until a valid close "
            "resolves it." % n)


def last_store_line(fx):
    return json.loads(open(os.path.join(fx.tools, "dispositions.jsonl"), encoding="utf-8").read().splitlines()[-1])


@case(3, "colliding-episode-strings-hide-no-opening", cr6=1, family=1)
def t3_colliding_strings(ctx):
    # CR-WASTE6 finding 1, the review's overturn as a full-report fixture. r.jsonl opens the helper "x:y" and
    # r:x.jsonl the helper "y", each at line 1 on 3 October and each its record's only line, so both episode
    # strings are r:x:y:1. The review's own determination abandons r:x:y:1 on 4 October, before the interval, with
    # each record's extent (1 line, its last event the opening) and the line count the B-WASTE15 version required:
    # it could name either opening, so it applies to neither, and both stay open, each named with its record,
    # helper and line (3 open with late's V). Beside them: an ordinary determination applied (solo:Z:1, one
    # opening, left out); one voided by a later event (late:V:1, an observation on 6 October); and run-ok's K
    # (60 s, $0.50), closing in the interval, independent of all of them, its figures the whole table. Five
    # records, all read and listed, run-ok and late touching the interval: no record is excluded. Then the
    # structured identity: a line naming r:x.jsonl's y at line 1, as `abandon` writes it, applies to that opening
    # alone (2 open); an event appended to r:x.jsonl afterwards voids it, and both are open again (3).
    fx = Fx(ctx.root, "colliding-strings", script=ctx.script)
    fx.write("run-ok.jsonl", priced_episode("K", "2026-10-06T10:01:00+0100"))
    fx.write("r.jsonl", opening_only("x:y"))
    rx = fx.write("r:x.jsonl", opening_only("y"))
    fx.write("solo.jsonl", opening_only("Z"))
    fx.write("late.jsonl", opening_only("V") + [{"ts": "2026-10-06T09:00:00+0100", "event": "observation"}])
    review = "Only helper y in record r:x has ended."
    append_store_lines(fx, [abandoned("r:x:y:1", record_lines=1, evidence=review), abandoned("solo:Z:1", record_lines=1),
                            abandoned("late:V:1", record_lines=1)])
    code, out, err, main, detail = fx.report()
    expect(code == 0 and main is not None and detail is not None, "exit %d: %s" % (code, last_line(err)))
    expect_table_and_gaps(main, detail, priced_rows([("run-ok", "K")]), [])
    cov = section(main, "## Coverage by reason")
    for line in (candidates_line(5, 5, 5, 0), open_count_line(3),
                 "- Records read: 2 with events in the interval, 3 outside it; 5 without run-open (counted like any other)."):
        expect(line in cov, "coverage lacks: %s" % line)
    ambiguous = "ambiguous: its episode string could name 2 openings (%s; %s); it applies to none of them" % (R_X, RX_Y)
    want = [determination_entry("late:V:1", VOIDED), determination_entry("r:x:y:1", ambiguous, evidence=review),
            determination_entry("solo:Z:1", APPLIED)]
    got = section(main, "## Determinations applied")
    expect(got == want, "determinations:\n%s" % first_difference(got, want))
    want_open = [open_entry("late:V:1"), open_entry("r:x:y:1 (%s)" % R_X), open_entry("r:x:y:1 (%s)" % RX_Y)]
    got = section(detail, "## Episodes open or unresolved at acquisition")
    expect(got == want_open, "open episodes:\n%s" % first_difference(got, want_open))
    inventory = section(detail, "## Inventory: every candidate record")
    for name in ("r.jsonl", "r:x.jsonl"):
        row = "| %s | read | %d | 1 | %s | %s | no | 0 | ordered |" % (
            name, os.path.getsize(os.path.join(fx.records, name)), OPENED_TEXT, OPENED_TEXT)
        expect(row in inventory, "inventory lacks: %s" % row)
    # The structured identity names one opening, whatever its string could name.
    append_store_lines(fx, [abandoned("r:x:y:1", record_lines=1, record="r:x.jsonl", helper="y", line=1)])
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d with the structured line: %s" % (code, last_line(err)))
    want = [determination_entry("late:V:1", VOIDED), determination_entry("r:x:y:1 (%s)" % RX_Y, APPLIED),
            determination_entry("r:x:y:1", ambiguous, evidence=review), determination_entry("solo:Z:1", APPLIED)]
    got = section(main, "## Determinations applied")
    expect(got == want, "determinations with the structured line:\n%s" % first_difference(got, want))
    want_open = [open_entry("late:V:1"), open_entry("r:x:y:1 (%s)" % R_X)]
    got = section(detail, "## Episodes open or unresolved at acquisition")
    expect(got == want_open and open_count_line(2) in section(main, "## Coverage by reason"),
           "open episodes with the structured line:\n%s" % first_difference(got, want_open))
    # A later event on r:x.jsonl voids it: both are open again.
    with open(rx, "a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": "2026-10-06T09:30:00+0100", "event": "observation"}) + "\n")
    code, out, err, main, detail = fx.report()
    want[1] = determination_entry("r:x:y:1 (%s)" % RX_Y, VOIDED)
    got = section(main, "## Determinations applied")
    expect(code == 0 and got == want, "determinations after the later event:\n%s" % first_difference(got, want))
    want_open = [open_entry("late:V:1"), open_entry("r:x:y:1 (%s)" % R_X), open_entry("r:x:y:1 (%s)" % RX_Y)]
    got = section(detail, "## Episodes open or unresolved at acquisition")
    expect(got == want_open, "open episodes after the later event:\n%s" % first_difference(got, want_open))


@case(3, "string-whose-other-record-cannot-be-read-applies-nowhere", family=1)
def t3_unreadable_reading(ctx):
    # Family 1 (CR-WASTE6 finding 1): a reading of the string onto a record that cannot be read could name an
    # opening there, so the string names more than one. s.jsonl opens "t:u" at line 1; s:t.jsonl is a symbolic
    # link, never followed or opened (named unreadable). The string s:t:u:1 applies to neither reading, and s.jsonl's
    # opening stays open, named with its record, helper and line.
    fx = Fx(ctx.root, "unreadable-reading", script=ctx.script)
    fx.write("run-ok.jsonl", priced_episode("K", "2026-10-06T10:01:00+0100"))
    fx.write("s.jsonl", opening_only("t:u"))
    os.symlink(os.path.join(fx.records, "run-ok.jsonl"), os.path.join(fx.records, "s:t.jsonl"))
    append_store_lines(fx, [abandoned("s:t:u:1", record_lines=1)])
    code, out, err, main, detail = fx.report()
    expect(code == 0 and main is not None, "exit %d: %s" % (code, last_line(err)))
    s_t = 'record \'s.jsonl\', helper "t:u", line 1'
    want = [determination_entry("s:t:u:1", "ambiguous: its episode string could name 2 openings (%s; record "
                                           '\'s:t.jsonl\', helper "u", line 1); it applies to none of them' % s_t)]
    got = section(main, "## Determinations applied")
    expect(got == want, "determinations:\n%s" % first_difference(got, want))
    got = section(detail, "## Episodes open or unresolved at acquisition")
    expect(got == [open_entry("s:t:u:1 (%s)" % s_t)], "open episodes: %s" % got)


@case(3, "determination-extent-compared-as-an-instant", family=1)
def t3_extent_instant(ctx):
    # Family 1 (CR-WASTE6 finding 1): a determination's record extent was compared as text, the record's last event
    # rendered as a whole-second local time against the line's string. Now as an instant, in an interval after now:
    # zulu.jsonl's line writes the same instant in UTC (09:00:00Z for 10:00:00 +0100) and applies (the text voided
    # it); frac.jsonl's last event is half a second after its line's whole second, so the record is not as recorded
    # and the line is void (the text dropped the half second and applied it); and `abandon` on frac2.jsonl, whose
    # last event falls at a quarter of a second, writes that fraction, and its line applies.
    fx = Fx(ctx.root, "extent-instant", script=ctx.script)
    fx.write("run-ok.jsonl", priced_episode("K", "2026-10-06T10:01:00+0100"))
    fx.write("zulu.jsonl", opening_only("Q"))
    fx.write("frac.jsonl", opening_only("Q", ts="2026-10-03T10:00:00.5+0100"))
    fx.write("frac2.jsonl", opening_only("Q", ts="2026-10-03T10:00:00.25+0100"))
    append_store_lines(fx, [abandoned("zulu:Q:1", last="2026-10-03T09:00:00Z", record_lines=1),
                            abandoned("frac:Q:1", record_lines=1)])
    code, out, err = fx.run("abandon", "frac2:Q:1", "--evidence", EVIDENCE)
    expect(code == 0, "abandon frac2:Q:1: %d %s" % (code, err))
    written = last_store_line(fx)
    expect(written.get("record_last_event") == written.get("last_event") == "2026-10-03T10:00:00.25+0100",
           "the extent written: %s" % written)
    since, until = future_interval()
    code, out, err, main, detail = fx.report(since=since, until=until)
    want = [determination_entry("frac2:Q:1", APPLIED, at=written["at"]), determination_entry("frac:Q:1", VOIDED),
            determination_entry("zulu:Q:1", APPLIED)]
    got = section(main, "## Determinations applied")
    expect(code == 0 and got == want, "determinations:\n%s" % first_difference(got, want))
    got = section(detail, "## Episodes open or unresolved at acquisition")
    expect(got == [open_entry("frac:Q:1", opened="2026-10-03 10:00:00.5 +0100")], "open episodes: %s" % got)


@case(8, "abandon-names-an-opening-its-string-cannot", cr6=1, family=1)
def t8_abandon_structured(ctx):
    # CR-WASTE6 finding 1, the command. `abandon` reads the string every way it can and refuses r:x:y:1, which could
    # name r.jsonl's x:y or r:x.jsonl's y, writing nothing; --record, --helper and --line name one opening, must come
    # together and must spell the same string. The line written carries that identity beside the string; a report
    # of an interval after it leaves out that opening alone, the other still open and named; a later event on its
    # record voids it, and both are open again.
    fx = Fx(ctx.root, "abandon-structured", script=ctx.script)
    fx.write("run-ok.jsonl", priced_episode("K", "2026-10-06T10:01:00+0100"))
    fx.write("r.jsonl", opening_only("x:y"))
    rx = fx.write("r:x.jsonl", opening_only("y"))
    store = os.path.join(fx.tools, "dispositions.jsonl")
    before = open(store, "rb").read()
    for extra, needle in (
            ((), "could name 2 openings (%s; %s): give the one meant with --record, --helper and --line" % (R_X, RX_Y)),
            (("--record", "r.jsonl", "--helper", "y", "--line", "1"),
             'is not record \'r.jsonl\', helper "y", line 1 written as <record>:<helper>:<line>'),
            (("--record", "r:x.jsonl"), "--record, --helper and --line name an opening together")):
        code, out, err = fx.run("abandon", "r:x:y:1", "--evidence", EVIDENCE, *extra)
        expect(code == 2 and needle in err, "%s: %d %s" % (" ".join(extra) or "the string alone", code, err.strip()[-300:]))
    expect(open(store, "rb").read() == before, "a refusal wrote to the store")
    code, out, err = fx.run("abandon", "r:x:y:1", "--evidence", EVIDENCE, "--record", "r:x.jsonl", "--helper", "y", "--line", "1")
    expect(code == 0, "abandon with the structured identity: %d %s" % (code, err))
    written = last_store_line(fx)
    want = {"kind": "abandoned", "episode": "r:x:y:1", "record": "r:x.jsonl", "helper": "y", "line": 1,
            "evidence": EVIDENCE, "last_event": OPENED, "record_last_event": OPENED, "record_lines": 1}
    expect(dict((k, written.get(k)) for k in want) == want, "the line written: %s" % written)
    since, until = future_interval()
    code, out, err, main, detail = fx.report(since=since, until=until)
    got = section(main, "## Determinations applied")
    expect(code == 0 and got == [determination_entry("r:x:y:1 (%s)" % RX_Y, APPLIED, at=written["at"])], "determinations: %s" % got)
    got = section(detail, "## Episodes open or unresolved at acquisition")
    expect(got == [open_entry("r:x:y:1 (%s)" % R_X)], "open episodes: %s" % got)
    with open(rx, "a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() + 60)),
                            "event": "observation"}) + "\n")
    code, out, err, main, detail = fx.report(since=since, until=until)
    got = section(main, "## Determinations applied")
    expect(got == [determination_entry("r:x:y:1 (%s)" % RX_Y, VOIDED, at=written["at"])], "after the later event: %s" % got)
    got = section(detail, "## Episodes open or unresolved at acquisition")
    expect(got == [open_entry("r:x:y:1 (%s)" % R_X), open_entry("r:x:y:1 (%s)" % RX_Y)], "open after the later event: %s" % got)


@case(8, "held-format-abandoned-line-applied-its-limit-named", cr6=2)
def t8_held_abandoned(ctx):
    # CR-WASTE6 finding 2. hang.jsonl's Q is abandoned by a line in the held design's format (episode, evidence, at,
    # last_event, record_last_event; no line count), twin.jsonl's Q by the same line with the count the reader
    # writes. Both are read and applied, the store whole (exit 0, no continuity failure), the held line's effect
    # naming the check it cannot make. The limit as it stands: a line added within the second of each record's last
    # event leaves the held line applied, unseen as named, and voids the counted one. A later event voids either.
    fx = Fx(ctx.root, "held-abandoned", script=ctx.script)
    fx.write("run-ok.jsonl", priced_episode("K", "2026-10-06T10:01:00+0100"))
    hang = fx.write("hang.jsonl", opening_only("Q"))
    twin = fx.write("twin.jsonl", opening_only("Q"))
    append_store_lines(fx, [abandoned("hang:Q:1"), abandoned("twin:Q:1", record_lines=1)])
    code, out, err, main, detail = fx.report()
    expect(code == 0 and main is not None and "Store continuity failure" not in main,
           "exit %d, the store read whole: %s" % (code, [l for l in (main or "").split("\n") if "continuity" in l][:1]))
    want = [determination_entry("hang:Q:1", APPLIED + HELD_LIMIT), determination_entry("twin:Q:1", APPLIED)]
    got = section(main, "## Determinations applied")
    expect(got == want, "determinations:\n%s" % first_difference(got, want))
    expect(section(detail, "## Episodes open or unresolved at acquisition") == ["- none"]
           and open_count_line(0) in section(main, "## Coverage by reason"), "the abandoned episodes are still open")
    for path in (hang, twin):
        with open(path, "a", encoding="utf-8") as h:
            h.write(json.dumps({"ts": OPENED, "event": "observation", "what": "the same second"}) + "\n")
    code, out, err, main, detail = fx.report()
    want = [determination_entry("hang:Q:1", APPLIED + HELD_LIMIT), determination_entry("twin:Q:1", VOIDED)]
    got = section(main, "## Determinations applied")
    expect(code == 0 and got == want, "after a same-second line:\n%s" % first_difference(got, want))
    got = section(detail, "## Episodes open or unresolved at acquisition")
    expect(got == [open_entry("twin:Q:1")], "open after a same-second line: %s" % got)
    with open(hang, "a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": "2026-10-06T09:00:00+0100", "event": "observation"}) + "\n")
    code, out, err, main, detail = fx.report()
    want = [determination_entry("hang:Q:1", VOIDED), determination_entry("twin:Q:1", VOIDED)]
    got = section(main, "## Determinations applied")
    expect(got == want, "after a later event:\n%s" % first_difference(got, want))
    got = section(detail, "## Episodes open or unresolved at acquisition")
    expect(got == [open_entry("hang:Q:1"), open_entry("twin:Q:1")], "open after a later event: %s" % got)


@case(8, "held-format-store-lines-read-as-specified", cr6=2, family=3)
def t8_held_store(ctx):
    # Family 3 (CR-WASTE6 finding 2): a store written wholly in the held design's line format (its README, "The
    # dispositions store"), a line of each kind it names: init (at, version); report (interval, report, detail,
    # listed, not_seen); listed (key, class, name, interval), two of them; disposition (key, disposition, note);
    # abandoned (episode, evidence, at, last_event, record_last_event); none with the `at` the reader adds to its
    # own report, listed and disposition lines. Beside them the run-ended line, which the held design names (its
    # revision 11 rules) without a field list, as the reader writes it. Each is read as specified: the previous
    # report's end starts the interval; the listed key not disposed is carried, the disposed one is not, and its
    # disposition is listed as recorded since that report; the abandonment applies, its unchecked extent named;
    # the run is listed as ended. Exit 0, no continuity failure.
    fx = Fx(ctx.root, "held-store", script=ctx.script)
    fx.write("run-ok.jsonl", priced_episode("K", "2026-10-06T10:01:00+0100"))
    fx.write("hang.jsonl", opening_only("Q"))
    fx.write("ended.jsonl", [{"ts": "2026-10-03T09:00:00+0100", "event": "run-open", "session": "h", "session_kind": "head"}])
    prev = ["2026-09-28T00:00:00+0100", "2026-10-05T00:00:00+0100"]
    held = [{"kind": "init", "at": "2026-09-27T09:00:00+0100", "version": "held-design-11"},
            {"kind": "report", "interval": prev, "report": "waste-report-2026-10-05.md",
             "detail": "waste-detail-2026-10-05.md", "listed": 2, "not_seen": 0},
            {"kind": "listed", "key": "helper-time@2026-09-28..2026-10-05", "class": "helper-time", "name": "helper-time",
             "interval": prev},
            {"kind": "listed", "key": "refusals@2026-09-28..2026-10-05", "class": "refusals", "name": "refusals",
             "interval": prev},
            {"kind": "disposition", "key": "refusals@2026-09-28..2026-10-05", "disposition": "kept",
             "note": "sandbox channel not recorded"},
            abandoned("hang:Q:1"),
            {"kind": "run-ended", "run": "ended", "record": "ended.jsonl", "evidence": "head pid gone", "at": DECIDED,
             "record_last_event": "2026-10-03T09:00:00+0100", "record_lines": 1}]
    with open(os.path.join(fx.tools, "dispositions.jsonl"), "w", encoding="utf-8") as h:
        for line in held:
            h.write(json.dumps(line) + "\n")
    code, out, err, main, detail = fx.report(since=None)
    expect(code == 0 and main is not None and "Store continuity failure" not in main, "exit %d: %s" % (code, last_line(err)))
    expect("- Interval: [2026-10-05 00:00 +0100, 2026-10-12 00:00 +0100), local time (GMT/BST)." in main.split("\n"),
           "the interval does not start at the held report's end")
    keys = dispositions_lines(main)
    expect(keys[:1] == ["- helper-time@2026-09-28..2026-10-05: open, carried from an earlier report"]
           and not [k for k in keys if k.startswith("- refusals@2026-09-28")], "carried keys: %s" % keys)
    since = section(main, "## Dispositions")
    i = since.index("Recorded since the previous report:")
    expect(since[i + 1:] == ["- refusals@2026-09-28..2026-10-05: kept (sandbox channel not recorded)"], "since %r" % since[i:])
    want = [determination_entry("hang:Q:1", APPLIED + HELD_LIMIT),
            determination_entry("ended", "applied: the run is listed as ended, not open", evidence="head pid gone",
                                kind="run-ended")]
    got = section(main, "## Determinations applied")
    expect(got == want, "determinations:\n%s" % first_difference(got, want))
    expect("- Runs open at acquisition: 0." in main.split("\n") and section(detail, "## Runs open at acquisition") == [
        "- ended · last run-open or run-resume at 2026-10-03 09:00:00 +0100 (line 1) · ended by determination"],
        "the ended run: %s" % section(detail, "## Runs open at acquisition"))


def classed_episode(lane, cls, close_ts, secs):
    """A priced episode, as priced_episode writes one, whose opening and close both carry the class CLS."""
    ep = priced_episode(lane, close_ts, duration_s=secs)
    ep[0]["class"] = ep[1]["class"] = cls
    return ep


@case(1, "view-total-apart-from-recorded-all", cr6=3, family=(2, 3))
def t1_view_total(ctx):
    # CR-WASTE6 finding 3, the review's overturn as a full-report fixture: all.jsonl's A of class "all" (240 s) and
    # (all).jsonl's P of class "(all)" (120 s) beside run-ok's K of class builder (60 s), an independent
    # contribution; $0.50 each. Each view of the detail lists the recorded run, class and helper "all" as written,
    # the recorded "(all)" quoted, '(all)', as the label rule shows a recorded string in a label's shape, and below
    # them the total row, the label (all), over the three closes: 420 s (7.0 min). The main report's rows name them
    # the same way. The per-run tables of all and (all) are linked by path, never opened (family 3).
    fx = Fx(ctx.root, "view-total", script=ctx.script)
    fx.write("run-ok.jsonl", priced_episode("K", "2026-10-06T10:01:00+0100"))
    fx.write("all.jsonl", classed_episode("A", "all", "2026-10-06T10:04:00+0100", 240))
    fx.write("(all).jsonl", classed_episode("P", "(all)", "2026-10-06T10:02:00+0100", 120))
    for stem in ("all", "(all)"):
        fx.write("%s-waste-table.md" % stem, ["| table of %s |" % stem])
    code, out, err, main, detail = fx.report()
    expect(code == 0 and main is not None and detail is not None, "exit %d: %s" % (code, last_line(err)))
    s = lambda k: "%d s (%d.0 min)" % (60 * k, k)
    one = "1 close: 0 not applicable, 0 unknown or invalid; " + GAPS0
    want = priced_rows([("run-ok", "K"), ("all", "A"), ("(all)", "P")])
    for key in [k for k in want if k[0] == H]:
        del want[key]
    want[(H, "total")] = (s(7), "complete", "3 closes: 3 timed, 0 not applicable, 0 unknown or invalid; " + GAPS0)
    for part, k in (("run all", 4), ("run '(all)'", 2), ("run run-ok", 1), ("class all", 4), ("class '(all)'", 2),
                    ("class builder", 1), ('helper all/"A"', 4), ('helper \'(all)\'/"P"', 2), ('helper run-ok/"K"', 1)):
        want[(H, part)] = (s(k), "complete", one)
    expect_table_and_gaps(main, detail, want, [])
    total = "- (all): 420 s (7.0 min) over 3 closes (0 unknown or invalid; 0 named gaps (detail))"
    views = {"### By run": ["- '(all)': %s over 1 close%s" % (s(2), V0), "- all: %s over 1 close%s" % (s(4), V0),
                            "- run-ok: %s over 1 close%s" % (s(1), V0), total],
             "### By class": ["- '(all)': %s over 1 close%s" % (s(2), V0), "- all: %s over 1 close%s" % (s(4), V0),
                              "- builder: %s over 1 close%s" % (s(1), V0), total],
             "### By helper": ['- \'(all)\'/"P": %s over 1 close%s' % (s(2), V0), '- all/"A": %s over 1 close%s' % (s(4), V0),
                               '- run-ok/"K": %s over 1 close%s' % (s(1), V0), total]}
    lines = detail.split("\n")
    for head, want_lines in views.items():
        i = lines.index(head)
        got = lines[i + 1:i + 2 + len(want_lines)]
        expect(got == want_lines + [""], "%s:\n%s" % (head, first_difference(got, want_lines + [""])))
    R = os.path.realpath(fx.records)
    got = section(detail, "## Per-run waste tables (linked by path, never read)")
    expect(got == ["- (all): [(all)-waste-table.md](<%s/(all)-waste-table.md>)" % R,
                   "- all: [all-waste-table.md](<%s/all-waste-table.md>)" % R], "table links: %s" % got)


def paren_constants(src):
    """Every string constant of SRC in a label's shape, one parenthesised phrase "(...)", other than an argparse
    help text or a regular expression's pattern."""
    tree = ast.parse(src)
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "add_argument":
                skip.update(id(k.value) for k in node.keywords if k.arg == "help")
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "re" and node.args:
                skip.add(id(node.args[0]))
    return set(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and id(n) not in skip and re.fullmatch(r"\([^()]*\)", n.value))


@case(2, "labels-in-one-definition-the-suite-takes", cr6=3, family=2)
def t2_label_inventory(ctx):
    # CR-WASTE6 finding 3 and family 2: the reader under test keeps every label it prints where a recorded value can
    # stand in one definition, LABELS, and this suite takes its list of labels from it. LABELS holds the labels the
    # reader's own constants name (the class states, the unrecorded source, the unusable lane, the views' total, the
    # absent field) and those written out by hand here (HAND_LABELS), so none drops out unseen; it equals the list
    # the suite takes (READER_LABELS); each label, as a recorded string, is shown quoted, apart from the label; and
    # every string constant of the reader in a label's shape is in LABELS, so a label written elsewhere fails here
    # (positive control: the scan finds the labels; planted control: a constant added to the source is found).
    src = open(ctx.script, encoding="utf-8").read()
    mod = reader_module(ctx.script, "weekly_waste_under_test")
    labels = getattr(mod, "LABELS", None)
    expect(labels is not None, "the reader keeps no LABELS: its labels are in no one definition")
    named = [mod.CLASS_LABELS[k] for k in ("invalid", "conflicting", "unrecorded")] + [
        mod.UNRECORDED_SOURCE, mod.UNUSABLE_LANE, getattr(mod, "VIEW_TOTAL", None), getattr(mod, "ABSENT_FIELD", None)]
    expect(sorted(map(str, named)) == sorted(labels), "LABELS %s against the labels its constants name %s" % (labels, named))
    expect(set(HAND_LABELS) <= set(labels), "labels dropped from LABELS: %s" % sorted(set(HAND_LABELS) - set(labels)))
    expect(set(labels) == set(READER_LABELS), "the reader under test's LABELS %s against the suite's %s" % (labels, READER_LABELS))
    for label in labels:
        text = mod.shown(label)
        expect(text != label and text[:1] in "'\"", "the recorded string %r is shown as %r" % (label, text))
    found = paren_constants(src)
    expect(len(found) >= 6 and "(class invalid)" in found, "PROBE FAILED: the scan found %d constants in a label's shape (control)" % len(found))
    stray = sorted(found - set(labels))
    expect(not stray, "constants in a label's shape outside LABELS: %s" % stray)
    expect("(placeholder)" in paren_constants(src + '\nPLANTED = "(placeholder)"\n'),
           "PROBE FAILED: the scan misses a planted constant (control)")


@case(2, "recorded-line-break-starts-no-line", family=2)
def t2_line_breaks(ctx):
    # Family 2 (CR-WASTE6 finding 3): a recorded line break printed raw started a line of its own, and could print a
    # label's row. brk.jsonl's helper is "B", a line break and a whole total row; a held-format line abandons an
    # episode no record holds (void) with an evidence of "gone", a line break and "- none". Each is shown on one
    # line, its line break escaped: the helper view holds one total row, the reader's, and the determinations one line.
    fx = Fx(ctx.root, "line-breaks", script=ctx.script)
    forged = "- (all): 999 s (16.7 min) over 1 close (0 unknown or invalid; 0 named gaps (detail))"
    fx.write("run-ok.jsonl", priced_episode("K", "2026-10-06T10:01:00+0100"))
    fx.write("brk.jsonl", priced_episode("B\n" + forged, "2026-10-06T10:02:00+0100"))
    append_store_lines(fx, [abandoned("zz:Q:1", evidence="gone\n- none")])
    code, out, err, main, detail = fx.report()
    expect(code == 0 and main is not None and detail is not None, "exit %d: %s" % (code, last_line(err)))
    lines = detail.split("\n")
    i = lines.index("### By helper")
    want = ["- brk/%s: 60 s (1.0 min) over 1 close%s" % (json.dumps("B\n" + forged), V0), '- run-ok/"K": 60 s (1.0 min) over 1 close' + V0,
            "- (all): 120 s (2.0 min) over 2 closes (0 unknown or invalid; 0 named gaps (detail))", ""]
    expect(lines[i + 1:i + 5] == want, "the helper view:\n%s" % first_difference(lines[i + 1:i + 5], want))
    expect(sum(1 for l in lines if l.startswith("- (all): ")) == 3, "rows reading as a total: %d, want one per view"
           % sum(1 for l in lines if l.startswith("- (all): ")))
    got = section(main, "## Determinations applied")
    expect(got == [determination_entry("zz:Q:1", "void: the episode is no longer open on its record", evidence="gone\\n- none")],
           "determinations: %s" % got)


@case(8, "disposition-keys-name-one-interval", family=1)
def t8_dispose_keys(ctx):
    # Family 1 (CR-WASTE6 finding 1; the dispose keys): an interval's label dropped a start's seconds, so a start a
    # store line set at 10:00:30 and one given as 10:00 shared their keys, and disposing of one disposed of the
    # other. The store's previous report (a held-format line) ends at 10:00:30 on 5 October: the report with no
    # --since starts there, labelled to the second with its offset; its helper-time key is disposed; a report
    # from 10:00 lists its own key, open. Each Interval line names its start exactly.
    fx = Fx(ctx.root, "dispose-keys", script=ctx.script)
    fx.write("run-ok.jsonl", priced_episode("K", "2026-10-06T10:01:00+0100"))
    append_store_lines(fx, [{"kind": "report", "interval": ["2026-09-28T00:00:00+0100", "2026-10-05T10:00:30+0100"],
                             "report": "waste-report-x.md", "detail": "waste-detail-x.md", "listed": 0, "not_seen": 0}])
    code, out, err, main, detail = fx.report(since=None)
    first = "helper-time@2026-10-05T10:00:30+0100..2026-10-12"
    expect(code == 0 and "- %s: listed by this report; open" % first in dispositions_lines(main),
           "keys from a start at 10:00:30: %s" % dispositions_lines(main))
    expect("- Interval: [2026-10-05 10:00:30 +0100, 2026-10-12 00:00 +0100), local time (GMT/BST)." in main.split("\n"),
           "the interval line drops the start's seconds")
    code, out, err = fx.run("dispose", first, "kept", "--note", "reviewed on Sunday")
    expect(code == 0, "dispose %d %s" % (code, err))
    code, out, err, main, detail = fx.report(since="2026-10-05T10:00")
    keys = dispositions_lines(main)
    expect("- helper-time@2026-10-05T10:00..2026-10-12: listed by this report; open" in keys, "keys from 10:00: %s" % keys)
    expect("- Interval: [2026-10-05 10:00 +0100, 2026-10-12 00:00 +0100), local time (GMT/BST)." in main.split("\n"),
           "the interval line from 10:00")


@case(8, "subcommands-name-records-exactly", family=1)
def t8_exact_names(ctx):
    # Family 1 (CR-WASTE6 finding 1; names compared exactly): a record a subcommand names is matched against the
    # folder's listing, never opened by a path the file system may match in another case or form. On a
    # case-insensitive file system (macOS's default, and this lane's scratch) the B-WASTE15 version opened
    # run-hang.jsonl for RUN-HANG and wrote a determination for a run no report has. Both subcommands refuse it,
    # writing nothing; the exact name is accepted, its line naming the record (the control).
    fx = Fx(ctx.root, "exact-names", script=ctx.script)
    fx.write("run-hang.jsonl", [{"ts": "2026-10-06T09:00:00+0100", "event": "run-open", "session": "h", "session_kind": "head"},
                                {"ts": "2026-10-06T10:00:00+0100", "event": "lane-open", "lane": "Q", "class": "builder"}])
    store = os.path.join(fx.tools, "dispositions.jsonl")
    before = open(store, "rb").read()
    insensitive = os.path.exists(os.path.join(fx.records, "RUN-HANG.jsonl"))
    for args in (("end-run", "RUN-HANG", "--evidence", "head pid gone"), ("abandon", "RUN-HANG:Q:2", "--evidence", EVIDENCE)):
        code, out, err = fx.run(*args)
        expect(code == 2 and "there is no record named 'RUN-HANG.jsonl'" in err and open(store, "rb").read() == before,
               "%s (case-insensitive file system: %s): %d %s" % (" ".join(args[:2]), insensitive, code, err.strip()[-300:]))
    code, out, err = fx.run("end-run", "run-hang", "--evidence", "head pid gone")
    written = last_store_line(fx)
    expect(code == 0 and written.get("run") == "run-hang" and written.get("record") == "run-hang.jsonl",
           "end-run run-hang: %d %s %s" % (code, err, written))


# Every record field the reader reads or renders, and the store fields it reads; FIELDS.md must
# name each record field with its writer (finding 8), and the reader may read no other field.
RECORD_FIELDS = ("event", "ts", "lane", "class", "duration_s", "exit_class", "denials", "sandbox_denials",
                 "fence_denials_transcript", "cost_src", "total_cost_usd", "usage", "usage_state",
                 "usage_complete", "input_tokens", "output_tokens", "calls", "item", "decision", "idle_min",
                 "idle_src", "over_cap_reports", "rewrites", "rewrites_total", "head_denials",
                 "head_denials_src", "run_spend_usd", "spent_usd", "spend_usd", "shape", "from", "to",
                 "tool", "fence", "sandbox", "session_id", "modelUsage", "costUSD", "inputTokens", "outputTokens",
                 "cacheReadInputTokens", "cacheCreationInputTokens")
RECORD_FIELDS += ("models", "cache_read_input_tokens", "cache_creation_input_tokens")
STORE_FIELDS = ("kind", "at", "interval", "key", "disposition", "note", "episode", "evidence", "run",
                "record_lines", "record_last_event", "record", "helper", "line")


@case(8, "fields-contract-names-every-read-field", cr1=8)
def t8_fields(ctx):
    src = open(ctx.script, encoding="utf-8").read()
    # Reads of a record line (obj, o, c, d, usage, ln.obj, g.obj) or a store line (rec), and the
    # declared snapshot fields.
    read = set(re.findall(r'\b(?:obj|o|c|d|usage|ln\.obj|g\.obj|rec)\.get\("([A-Za-z_]+)"', src))
    read |= set(re.findall(r'\(\("([a-z_]+)", P_', src))
    # Control: the scan finds fields, among them two any version of the reader reads by `.get`.
    expect(len(read) >= 30 and "head_denials_src" in read and "exit_class" in read,
           "PROBE FAILED: the source scan found %d fields (control)" % len(read))
    stray = sorted(read - set(RECORD_FIELDS) - set(STORE_FIELDS))
    expect(not stray, "the reader reads fields no list here declares: %s" % stray)
    fields = open(os.path.join(os.path.dirname(os.path.abspath(ctx.script)), "FIELDS.md"), encoding="utf-8").read()
    missing = [f for f in RECORD_FIELDS if "`%s`" % f not in fields and ".%s`" % f not in fields]
    expect(not missing, "FIELDS.md does not name: %s" % missing)
    for cite in ("handsoff.py:5215-5217", "handsoff.py:6136-6138", "handsoff.py:3385-3387", "handsoff.py:3252-3290",
                 "handsoff.py:4357"):
        expect(cite in fields, "FIELDS.md lacks the writer citation %s" % cite)


# ------------------------------------------------------------------------ test 7 -----------

# The admitted records another read record names: a string anywhere in one of its lines whose last path
# component is the record's name (a record naming itself aside). The input contract's planted defects
# restore R1's reading of references with it, written into the function that holds `recs`.
NAMED_RECORDS = '''
    _named = set()
    for _r in recs:
        for _ln in _r.lines:
            _stack = [_ln.obj] if isinstance(_ln.obj, dict) else []
            while _stack:
                _v = _stack.pop()
                if isinstance(_v, dict):
                    _stack.extend(_v.values())
                elif isinstance(_v, list):
                    _stack.extend(_v)
                elif isinstance(_v, str) and os.path.basename(_v) != _r.name:
                    _named.add(os.path.basename(_v))
    _named = set(_r.name for _r in recs if _r.admitted and _r.name in _named)'''

# Retained acceptance mutations, re-anchored to the guarded source without changing their defects.
MUTANTS = [
    ('missing-as-zero', [('        return "unknown", None, "duration_s is not on the close"', '        return "known", Decimal(0), None')]),
    ('drop-record-without-run-open', [('            if rec.status != "read":\n                continue\n            # lane -> {"kind"', '            if rec.status != "read" or not rec.has_run_open:\n                continue\n            # lane -> {"kind"')]),
    ('double-count-resumed-episode', [('                    out["episodes"].append(ep)', '                    out["episodes"].extend([ep, ep] if opening.kind == "lane-resumed" else [ep])')]),
    ('swap-two-gap-associations', [('                n_unknown += 1\n                field_gap(ep, P_H, note)', '                n_unknown += 1\n                field_gap(ep, P_F, note)'), ('                resumed_unsure += 1 if ep.resumed_later else 0\n                field_gap(ep, P_F, note)', '                resumed_unsure += 1 if ep.resumed_later else 0\n                field_gap(ep, P_H, note)')]),
    ('change-a-rendered-number', [('    return "%s s (%d.%d min)" % (fmt_dec(d), tenths // 10, tenths % 10)', '    return "%s s (%d.%d min)" % (fmt_dec(d), tenths // 10 + 1, tenths % 10)')]),
    ('suppress-incomplete-status', [('    if state == "missing":\n        return state, "no usage reported", tokens', '    if state == "incomplete":\n        state = "complete"\n    if state == "missing":\n        return state, "no usage reported", tokens')]),
    ('change-the-run-close-snapshot-amount', [('                                              "%s %s" % (field, val) if st == "known"', '                                              "%s %s" % (field, 999 if ln.kind == "run-close" and field == "run_spend_usd" else val) if st == "known"')]),
    ('add-a-rendered-figure', [('    return {"rows": fig.rows, "summary": fig.summary,', '    fig.add(HELPER, "median", "1 s", "complete", "added")\n    return {"rows": fig.rows, "summary": fig.summary,')]),
    ('spend-usd-missing-as-zero', [('        return "unknown", None, "%s is not on the event" % field', '        return ("known", 0, None) if field == "spend_usd" else ("unknown", None, "%s is not on the event" % field)'), ('        return "unknown", None, "%s is recorded as null" % field', '        return ("known", 0, None) if field == "spend_usd" else ("unknown", None, "%s is recorded as null" % field)')]),
    ('restore-the-spawn-failure-sandbox-shortcut', [('        return {"tool": na, "fence": na,\n                "sandbox": na if b is MISSING else count_value(b, "sandbox_denials")}', '        return {"tool": na, "fence": na, "sandbox": na}')]),
    ('admit-a-pinned-event-log', [('    return name.endswith(".jsonl") and name not in PINNED_EVENT_LOGS', '    return name.endswith(".jsonl")')]),
    ('event-of-another-kind-aborts-the-report', [('    ev = obj.get("event", MISSING)\n    if not isinstance(ev, str):', '    ev = obj.get("event", MISSING)\n    if ev not in KNOWN_EVENTS and not isinstance(ev, str):')]),
    ('a-reference-followed-to-open-its-target', [('    counted = [ep for ep in an["episodes"] if start <= ep.close.ts < end]', '    counted = [ep for ep in an["episodes"] if start <= ep.close.ts < end]\n    for _r in recs:\n        for _ln in _r.lines:\n            _stack = [_ln.obj] if isinstance(_ln.obj, dict) else []\n            while _stack:\n                _v = _stack.pop()\n                if isinstance(_v, dict):\n                    _stack.extend(_v.values())\n                elif isinstance(_v, list):\n                    _stack.extend(_v)\n                elif isinstance(_v, str) and _v.strip("./"):\n                    _p = os.path.join(os.path.dirname(_r.path), os.path.expanduser(_v))\n                    if os.path.isfile(_p):\n                        open(_p, "rb").read()')]),
    ('a-referenced-admitted-record-skipped', [('        acq_end = time.time()\n', '        acq_end = time.time()\n        _named = set()\n        for _r in recs:\n            for _ln in _r.lines:\n                _stack = [_ln.obj] if isinstance(_ln.obj, dict) else []\n                while _stack:\n                    _v = _stack.pop()\n                    if isinstance(_v, dict):\n                        _stack.extend(_v.values())\n                    elif isinstance(_v, list):\n                        _stack.extend(_v)\n                    elif isinstance(_v, str) and os.path.basename(_v) != _r.name:\n                        _named.add(os.path.basename(_v))\n        _named = set(_r.name for _r in recs if _r.admitted and _r.name in _named)\n        recs = [_r for _r in recs if _r.name not in _named]\n')]),
    ('a-reference-marks-a-figure-partial', [('        res = guarded("compute", GLOBAL_OWNER, sources, ALL_PARTS,\n                      lambda: compute(recs, an, Fraction(start), Fraction(end)), empty_result)\n', '        res = guarded("compute", GLOBAL_OWNER, sources, ALL_PARTS,\n                      lambda: compute(recs, an, Fraction(start), Fraction(end)), empty_result)\n\n        _named = set()\n        for _r in recs:\n            for _ln in _r.lines:\n                _stack = [_ln.obj] if isinstance(_ln.obj, dict) else []\n                while _stack:\n                    _v = _stack.pop()\n                    if isinstance(_v, dict):\n                        _stack.extend(_v.values())\n                    elif isinstance(_v, list):\n                        _stack.extend(_v)\n                    elif isinstance(_v, str) and os.path.basename(_v) != _r.name:\n                        _named.add(os.path.basename(_v))\n        _named = set(_r.name for _r in recs if _r.admitted and _r.name in _named)\n        if _named:\n            res["rows"] = [(f, p, v, "partial" if s == "complete" else s, c) for f, p, v, s, c in res["rows"]]\n')]),
    ('a-reference-names-a-breach', [('    lines += [\n        "- Other entries in the records folder:', '    _named = set()\n    for _r in recs:\n        for _ln in _r.lines:\n            _stack = [_ln.obj] if isinstance(_ln.obj, dict) else []\n            while _stack:\n                _v = _stack.pop()\n                if isinstance(_v, dict):\n                    _stack.extend(_v.values())\n                elif isinstance(_v, list):\n                    _stack.extend(_v)\n                elif isinstance(_v, str) and os.path.basename(_v) != _r.name:\n                    _named.add(os.path.basename(_v))\n    _named = set(_r.name for _r in recs if _r.admitted and _r.name in _named)\n    if _named:\n        lines.append("- Naming-contract breaches: %d (%s)." % (len(_named), ", ".join(sorted(_named))))\n    lines += [\n        "- Other entries in the records folder:')]),
    ('range-less-reading', [('def beyond(v):', 'def beyond(v):\n    return None\n\n\ndef _range_rule_unused(v):')]),
    ('decimal-literal-unguarded', [('                     parse_float=_decimal)', '                     parse_float=Decimal)')]),
    ('timestamp-fraction-unbounded', [('    if not m or (m.group(7) and len(m.group(7)) > TS_FRACTION_DIGITS):', '    if not m:')]),
    ('unpaired-surrogates-read', [('    if SURROGATE_ESCAPE.search(text):\n        lone = unpaired_surrogate(obj)', '    if False:\n        lone = unpaired_surrogate(obj)'), ('                if SURROGATE_ESCAPE.search(text) and unpaired_surrogate(rec) is not None:', '                if False:')]),
    ('store-recursion-uncaught', [('            except (UnicodeDecodeError, ValueError, RecursionError):', '            except (UnicodeDecodeError, ValueError):')]),
    ('store-determination-keyed-by-any-field', [('                cands, group = None, ("run-ended", rec["run"])', '                cands, group = None, ("run-ended", rec.get("episode") or rec.get("run"))')]),
    ('a-recorded-class-read-as-an-internal-label', [('            if ep.cls[0] != "known":', '            if ep.cls[0] != "known" or ep.cls[1].startswith("("):'), ('    return g.reason.group if isinstance(g.reason, Reason) else g.reason', '    r = g.reason\n    for prefix in ("record ", "not JSON", "not UTF-8", "not a JSON object", "no event name",\n                   "an event name outside", "no usable timestamp", "no usable lane",\n                   "a close with no opening", "a close timed before", "a close after"):\n        if r.startswith(prefix):\n            return prefix.strip()\n    return re.sub(r"[0-9]+", "N", re.sub(r"\'[^\']*\'", "\'…\'", r))')]),
    ('a-recorded-idle-source-read-as-the-unrecorded-group', [('    return ("recorded", src) if isinstance(src, str) and src.strip() else None', '    return ("unrecorded", None) if src == UNRECORDED_SOURCE else ("recorded", src) if isinstance(src, str) and src.strip() else None')]),
    ('sums-rounded-to-28-digits', [('    low = min(a.as_tuple().exponent, b.as_tuple().exponent)\n    with localcontext() as ctx:\n        ctx.prec = max(a.adjusted(), b.adjusted()) - low + 2\n        ctx.traps[Inexact] = ctx.traps[Rounded] = True\n        return a + b', '    return a + b')]),
    ('minutes-rounded-twice', [('    tenths = round(Fraction(Decimal(d)) / 6)', '    tenths = int((Decimal(d) / 6).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))')]),
    ('sub-microsecond-fractions-dropped', [('        digits = format(Decimal(frac.numerator) / Decimal(frac.denominator), "f")', '        digits = str(Decimal(frac.numerator) / Decimal(frac.denominator))')]),
    ('an-episode-string-read-back-as-its-identity', [('                    cands = key_identities(rec["episode"], by_stem)', '                    cands = [c for c in key_identities(rec["episode"], by_stem) if c[0].stem == rec["episode"].rsplit(":", 2)[0]]'), ('                    left_out.add((r.name, lane, n))', '                    left_out.update((o[0].name, o[1], o[2].n) for o in an["open"] if episode_key(o[0].stem, o[1], o[2].n) == rec["episode"])')]),
    ('an-abandoned-line-without-its-line-count-refused', [('        if not (text("episode") and text("evidence") and parse_ts(rec.get("at")) is not None):', '        if not (text("episode") and text("evidence") and parse_ts(rec.get("at")) is not None and isint(rec.get("record_lines"))):')]),
    ('the-view-total-printed-as-all', [('                     % (VIEW_TOTAL, value, plural(n, "close"), unk, gaps_note(res["s_h"])))', '                     % ("all", value, plural(n, "close"), unk, gaps_note(res["s_h"])))')]),
    ('a-run-name-in-the-views-as-written', [('        return (shown(key) if view == "run" else class_text(key) if view == "class"', '        return (key if view == "run" else class_text(key) if view == "class"')]),
    ('an-extent-compared-as-local-text', [('                        or parse_ts(rec.get("record_last_event")) != r.last_ts):', '                        or iso_local(r.last_ts) != rec.get("record_last_event")):')]),
    ('an-interval-label-to-the-minute', [('        if t % 1 == 0 and lt.tm_sec == 0 and wall_epochs(*lt[:6]) == {t}:', '        if True:')]),
    ('a-record-name-matched-by-the-file-system', [('    if stem + ".jsonl" not in names:', '    if False:')]),
    ('a-recorded-line-break-starts-a-line', [('    return LINE_ENDS.sub(lambda m: repr(m.group())[1:-1], text)', '    return text')]),
    # The three defects of B-WW1's fold, each restored: every priced line summed again (each its own session); the
    # keep-awake line read as a name outside the known list; the command checker's read log admitted as a record.
    ('every-priced-line-summed-again', [('        if s.key not in seqs:\n', '        s = s._replace(key=("line", s.ln.n))\n        if s.key not in seqs:\n')]),
    ('lane-awake-outside-the-known-names', [('install lane-aborted lane-awake lane-close lane-closed', 'install lane-aborted lane-close lane-closed')]),
    ('a-command-checker-read-log-admitted', [('    if read_log(name, names):\n        return False\n', '')]),
    # The defects CR-WW1 found in that fold, each restored (B-WW2's fold): finding 1, a session that records per-pass
    # costs read as running totals, and one read as neither counted as running totals; 2, a line lost to a session
    # ignored; 3, a line naming no session counted as a session of its own; 4, an unusable model value resetting the
    # comparison; 5, the last close overriding a later beat as the terminal; 6, a read log's name left out without its
    # run's record beside it. And B-WW1's first proposed hunk undone: stop-requested a name outside the known list.
    ('a-per-pass-session-read-as-running-totals', [('    if drop and not carry:\n        return "per-pass", evidence_text(drop)',
                                                   '    if drop and not carry:\n        return "running", evidence_text(drop)')]),
    ('a-session-of-neither-reading-counted-as-running-totals', [('    return "unclassified", ("no model\'s entry is carried over unchanged to a later close and none is dropped from a close or beat"\n                            + NEITHER)', '    return "running", ("assumed running totals", "")')]),
    ('a-line-lost-to-a-session-ignored', [('        gone = next((x for x in lost if could_be(x, key)), None)', '        gone = None')]),
    ('a-line-naming-no-session-counted-alone', [('        if s.state != "known":\n            if s.basis not in RESULT_BASES:', '        if s.state == "none":\n            s = s._replace(state="known", key=("line", s.ln.n))\n        if s.state != "known":\n            if s.basis not in RESULT_BASES:')]),
    ('an-unusable-model-value-treated-as-zero', [('            values.append(v if ok and v >= 0 and not beyond(v) else None)', '            values.append(v if ok and v >= 0 and not beyond(v) else 0)')]),
    ('a-later-beat-overridden-by-the-last-close', [(
        '                spend = xadd(priced[-1].amount, Decimal(base.amount if base else 0).copy_negate())',
        '                spend = xadd(([s for s in priced if s.kind == "close"] or priced)[-1].amount, '
        'Decimal(base.amount if base else 0).copy_negate())')]),
    ('a-read-log-left-out-without-its-run-record', [('    return (READ_LOG_NAME.fullmatch(name) is not None\n'
                                                    '            and name[:-len(READ_LOG_SUFFIX)] + ".jsonl" in names)',
                                                    '    return READ_LOG_NAME.fullmatch(name) is not None')]),
    ('stop-requested-outside-the-known-names', [('stop-condition stop-requested successor-aborted', 'stop-condition successor-aborted')]),
    # And the mirror of finding 5 at the start: a beat before the start ignored for the session's total there.
    ('a-beat-before-the-start-ignored-for-the-baseline', [('        base = before[-1] if before else None\n',
                                                          '        base = ([s for s in before if s.kind == "close"] or [None])[-1]\n')]),
    # CR-WW2: restore each integrity/classification error independently. The loss mutants also
    # discard the orphan's evidence, as the second build did before it classified a session.
    ('an-empty-inventory-read-as-a-model-drop', [(
        '    if not isinstance(models, dict) or not models:\n', '    if not isinstance(models, dict):\n')]),
    ('per-pass-loss-check-bypassed', [(
        '        gone = next((x for x in lost if could_be(x, key)), None)',
        '        gone = next((x for x in lost if could_be(x, key)), None)\n'
        '        if classify(seq)[0] == "per-pass":\n            gone = None'), (
        '            by_rec.setdefault(ln.rec, []).append((ln, "close", ln.lane))\n', '')]),
    ('a-superseded-loss-exempted', [(
        '        gone = next((x for x in lost if could_be(x, key)), None)',
        '        gone = next((x for x in lost if could_be(x, key) and (base is None or x.ln.n > base.ln.n)), None)'), (
        '            by_rec.setdefault(ln.rec, []).append((ln, "close", ln.lane))\n', '')]),
    ('a-terminal-estimate-dropped-from-the-session', [(
        '        if s.basis == "na":\n            continue\n',
        '        if s.basis not in RESULT_BASES:\n            continue\n'), (
        '        elif s.basis != "na":\n', '        elif False:\n')]),
    ('beat-evidence-ignored-during-classification', [(
        '    for s in seq:\n        if s.basis == "priced":\n',
        '    for s in seq:\n        if s.kind == "beat":\n            continue\n        if s.basis == "priced":\n')]),
    ('beat-aggregate-falls-ignored', [(
        '                if fall is None and vb < va:\n', '                if False:\n')]),
    ('every-close-beat-pair-declared-unknown', [(
        '    if len(seq) == 1:\n        return "one", None\n',
        '    if len(seq) == 1:\n        return "one", None\n'
        '    if len(seq) == 2 and any(s.kind == "beat" for s in seq):\n'
        '        return "unclassified", "close/beat pair assumed unknown"\n')]),
    ('an-empty-beat-inventory-accepted', [(
        '        if (not isinstance(models, list) or not models or not all(usable_name(m) for m in models)\n',
        '        if (not isinstance(models, list) or not all(usable_name(m) for m in models)\n')]),
    ('a-missing-beat-count-read-as-zero', [(
        '        values = tuple(usage.get(field) for field in BEAT_COUNTS)\n',
        '        values = tuple(usage.get(field, 0) for field in BEAT_COUNTS)\n')]),
    ('a-session-with-only-losses-inside-omitted', [(
        '        if not inside:\n            # An unfinished or damaged pass inside the interval still depends on the session\'s\n',
        '        if not inside:\n            continue\n            # An unfinished or damaged pass inside the interval still depends on the session\'s\n')]),
    ('contradictory-opening-session-identity-ignored', [(
        '            if usable_name(opened_sid) and usable_name(closed_sid) and opened_sid != closed_sid:\n',
        '            if False:\n')]),
    # B-WW4's fold, the reconciliation rule: N1's fault restored (an inventory never reconciled with its total, so a
    # whole model entry left out reads as a model dropped); the tolerance taken away (exact equality, so the harness's
    # own rounding reads as an omission); the difference taken one way only (costs above the total pass); and the
    # bound read as exclusive (a difference of exactly the tolerance rejected).
    ('an-inventory-left-unreconciled-with-its-total', [('        if off > RECONCILE_TAU:\n', '        if False:\n')]),
    ('an-inventory-reconciled-exactly', [('RECONCILE_TAU = Decimal("1E-9")\n', 'RECONCILE_TAU = Decimal(0)\n')]),
    ('an-inventory-reconciled-one-way', [(
        '        off = xadd(spent, Decimal(total).copy_negate()).copy_abs()\n',
        '        off = xadd(Decimal(total), spent.copy_negate())\n')]),
    ('the-reconciliation-bound-exclusive', [('        if off > RECONCILE_TAU:\n', '        if off >= RECONCILE_TAU:\n')]),
]


# Each mutant's acceptance (every case outside test 7, including containment in test 9;
# test 8 joined in B-WASTE16's fold, whose
# determination and disposition cases are installation acceptance) runs as this suite in a process of its own, its
# fixtures under the mutant's own folder, a few mutants at once (set by judgement, unmeasured: four keeps the
# leg within a quarter of an hour on a laptop without crowding it).
WORKERS = 4


@case(7, "restored-defects-fail-acceptance", cr3=(1, 2, 3), cr4=1, b17=(1, 2), cr6=(1, 2, 3), family=(1, 2, 4))
def t7_mutants(ctx):
    names = [c[0] for c in CASES if c[1] != 7]
    pending, running, results = [], [], {}
    here = os.path.dirname(os.path.abspath(ctx.script))
    for name, pairs in MUTANTS:
        d = tempfile.mkdtemp(prefix="mutant-%s-" % name, dir=ctx.root)
        pending.append((name, d, mutate(ctx.script, os.path.join(d, "weekly-waste.py"), pairs)))
        # The build with one defect restored: its documents beside it, so a case reading FIELDS.md or
        # README.md beside the reader fails only on the defect.
        for doc in ("FIELDS.md", "README.md"):
            if os.path.isfile(os.path.join(here, doc)):
                shutil.copy2(os.path.join(here, doc), os.path.join(d, doc))
    while pending or running:
        while pending and len(running) < WORKERS:
            name, d, path = pending.pop(0)
            log = open(os.path.join(d, "acceptance.out"), "w")
            p = subprocess.Popen([PY, "-B", os.path.abspath(__file__), "--script", path] + names,
                                 stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ))
            running.append((name, d, p, log))
        time.sleep(0.5)
        for item in list(running):
            name, d, p, log = item
            if p.poll() is None:
                continue
            log.close()
            running.remove(item)
            out = open(os.path.join(d, "acceptance.out"), encoding="utf-8", errors="replace").read().split("\n")
            verdict = [l for l in out if re.match(r"(PASS|FAIL) [0-9]+/[0-9]+\Z", l)]
            if ctx.mutation_logs:
                shutil.copyfile(os.path.join(d, "acceptance.out"), os.path.join(ctx.mutation_logs, name + ".txt"))
            results[name] = ([l.split()[1] for l in out if l.startswith("FAIL ") and " · " in l], verdict[-1:], p.returncode)
            print("    mutation %d/%d %s: %s (exit %d)" %
                  (len(results), len(MUTANTS), name, verdict[-1] if verdict else "NO VERDICT", p.returncode), flush=True)
    lines = []
    for name, pairs in MUTANTS:
        fails, verdict, code = results[name]
        expect(verdict, "PROBE FAILED: the mutant %s run gave no verdict" % name)
        expect(code == 1 and verdict == ["FAIL %d/%d" % (len(fails), len(names))],
               "PROBE FAILED: the mutant %s did not complete its full acceptance" % name)
        lines.append("mutant %-42s %3d failing cases: %s" % (name, len(fails), ", ".join(fails[:6])))
        expect(fails, "mutant %s passed acceptance" % name)
    ctx.sensitivity = lines


@case(7, "tmp-and-private-tmp-agree")
def t7_aliases(ctx):
    fx = Fx(ctx.root, "t7-alias", script=ctx.script)
    scene_a(fx)
    rec = fx.records
    if rec.startswith("/private/tmp/"):
        alt = rec[len("/private"):]
    elif rec.startswith("/tmp/"):
        alt = "/private" + rec
    else:
        # The configured TMPDIR need not itself be under the alias. A private throwaway copy is.
        alias_root = tempfile.mkdtemp(prefix="ww-alias-", dir=os.environ.get("WASTE_ALIAS_TMPDIR", "/tmp"))
        try:
            clone = Fx(alias_root, "alias", script=ctx.script)
            scene_a(clone)
            code1, out1, err1, main1, det1 = clone.report(records=clone.records)
            alias = "/private" + clone.records if clone.records.startswith("/tmp/") else clone.records[len("/private"):]
            code2, out2, err2, main2, det2 = clone.report(records=alias)
            expect(code1 == code2 == 0 and mask(main1) == mask(main2) and det1 == det2,
                   "alias outputs disagree")
            expect_rows(main2, SCENE_A_ROWS)
        finally:
            shutil.rmtree(alias_root)
        return
    expect(os.path.isdir(alt), "PROBE FAILED: no alias %s" % alt)
    code1, out1, err1, main1, det1 = fx.report(records=rec)
    code2, out2, err2, main2, det2 = fx.report(records=alt)
    expect(code1 == code2 == 0, "exits %d %d" % (code1, code2))
    expect(mask(main1) == mask(main2) and det1 == det2, "/tmp and /private/tmp runs disagree")
    expect_rows(main2, SCENE_A_ROWS)


# ------------------------------------------------------------------------ read-only leg ----

@case(8, "writes-only-its-outputs")
def t8_readonly(ctx):
    # Checksums before and after: the records, the referenced files and the per-run table are
    # unchanged; the tools folder gains only reports/ files and store lines. The source probe for
    # write calls finds exactly the reader's write helpers (its positive control).
    fx = Fx(ctx.root, "t8-readonly", script=ctx.script)
    refs = scene_a(fx)
    rec_before = tree_manifest(os.path.join(fx.dir, "store"))
    proj_before = tree_manifest(fx.projects)
    store_before = open(os.path.join(fx.tools, "dispositions.jsonl"), "rb").read()
    code, out, err, main, detail = fx.report()
    expect(code == 0, "exit %d" % code)
    expect(tree_manifest(os.path.join(fx.dir, "store")) == rec_before, "the records folder changed")
    expect(tree_manifest(fx.projects) == proj_before, "the transcripts changed")
    after = sorted(os.path.relpath(p, fx.tools) for p in tree_manifest(fx.tools))
    expect(after == ["dispositions.jsonl", "reports", "reports/waste-detail-2026-10-12.md", "reports/waste-report-2026-10-12.md"],
           "tools folder: %s" % after)
    expect(open(os.path.join(fx.tools, "dispositions.jsonl"), "rb").read().startswith(store_before), "store not append-only")
    src = open(ctx.script, encoding="utf-8").read()
    writes = re.findall(r"open\([^)]*[\"'][wa]b?[\"']|os\.open\(|os\.replace\(|os\.rename\(|os\.remove\(|os\.unlink\(|os\.mkdir\(|os\.makedirs\(|shutil\.|os\.rmdir\(", src)
    # os.open three times: the store's append (O_WRONLY | O_APPEND), init's exclusive create, and
    # the record read, which opens read-only and follows no link (its flags checked below).
    expect(sorted(writes) == sorted(['open(temp, "wb"', 'os.replace(', 'os.open(', 'os.open(', 'os.open(', 'os.mkdir(']),
           "write calls in the reader: %s" % writes)
    opens = re.findall(r"os\.open\(([^)]*\))", src)
    reads = [o for o in opens if "O_RDONLY" in o]
    expect(len(reads) == 1 and not re.search(r"O_WRONLY|O_RDWR|O_CREAT|O_APPEND|O_TRUNC", reads[0])
           and "O_NOFOLLOW" in reads[0], "the record read's flags: %s" % opens)



# ---------------------------------------------------------------- containment acceptance ---
# D cases use existing source sites on the base, never absence of a newly introduced hook.
# All totals below come from this small fixture: 60 + 30 + 11 seconds; 2 boundaries;
# priced closes 2 + 3 + 5 dollars and one 2-dollar beat. A separate old open record supplies
# exclusion/ending candidates without contributing any interval consumption.

def con_fixture(ctx, name):
    fx = Fx(ctx.root, name, script=ctx.script)
    stamp = "2026-10-06T10:00:00+0100"
    def event(kind, **kw):
        return dict(ts=stamp, event=kind, **kw)
    def closing(lane, duration, cost, cls="builder", status="completed"):
        return event("lane-closed", lane=lane, **{"class": cls}, duration_s=duration,
                     exit_class=status, denials={"tool": 1, "fence": 2, "sandbox": 3},
                     cost_src="result", total_cost_usd=cost, session_id="s-" + lane, usage=fixture_inventory(cost))
    boundary = event("phase-boundary", idle_min=7, idle_src="recorded", over_cap_reports=2,
                     rewrites=3, rewrites_total=9, head_denials=4, denials=5, run_spend_usd=6)
    r = [event("run-open"), event("gate", item="item", decision="allow", run_spend_usd=1),
         event("lane-open", lane="worker", **{"class": "critic"}),
         closing("worker", 60, 2, "critic", "failed"), boundary,
         event("hold-beat", lane="held", session_id="s-held", cost_src="result", total_cost_usd=2, usage=fixture_beat_usage()),
         event("lane-open", lane="other", **{"class": "builder"}), closing("other", 30, 3),
         dict(event="lane-resumed", ts="2026-10-13T10:00:00+0100", lane="worker", **{"class": "critic"}),
         dict(event="lane-spawned", ts="2026-10-13T10:00:00+0100", lane="worker")]
    safe = [event("lane-open", lane="safe", **{"class": "builder"}), closing("safe", 11, 5), dict(boundary)]
    old = [{"event": "run-open", "ts": "2026-10-03T10:00:00+0100"},
           {"event": "lane-open", "ts": "2026-10-03T10:00:00+0100", "lane": "open", "class": "builder"}]
    fx.write("r.jsonl", r); fx.write("s.jsonl", safe); fx.write("z.jsonl", old)
    pair = ["2026-09-28T00:00:00+0100", "2026-10-05T00:00:00+0100"]
    append_store_lines(fx, [
        {"kind": "report", "interval": pair},
        {"kind": "listed", "interval": pair, "key": "carried@old"},
        {"kind": "disposition", "key": "carried@old", "disposition": "fixed", "note": "earlier"},
        {"kind": "abandoned", "episode": "z:open:2", "evidence": "recorded", "at": "2026-10-04T10:00:00+0100",
         "record_last_event": old[-1]["ts"], "record_lines": 2},
        {"kind": "run-ended", "run": "z", "evidence": "recorded", "at": "2026-10-04T10:00:00+0100",
         "record_last_event": old[-1]["ts"], "record_lines": 2},
        {"kind": "disposition", "key": "helper-time@2026-10-05..2026-10-12", "disposition": "fixed", "note": "rerun"}])
    return fx


CON_ALL_RECORDS = tuple(("record", ordinal, n) for ordinal, length in ((1, 11), (2, 4), (3, 3))
                        for n in range(1, length + 1))
CON_R = tuple(("record", 1, n) for n in range(1, 12))
CON_EP = tuple(("record", 1, n) for n in (2, 3, 4, 9))
CON_STORES = tuple(("store", 0, n) for n in range(1, 9))

# name, route, owner, declared supplier oracle, effect oracle, existing base function/site
CON_CASES = [
    ("record-before-blank", "record-blank", ("record",1,11), (("record",1,11),), "record-all", "read_record", "if not raw.strip():"),
    ("record-decode", "record-decode", ("record",1,4), (("record",1,4),), "record-all", "read_record", 'obj = loads_strict(raw.decode("utf-8"))'),
    ("record-kind", "record-kind", ("record",1,4), (("record",1,4),), "record-all", "read_record", 'line.ts = parse_ts(obj.get("ts"))'),
    ("undated-reach", "record-time", ("record",1,4), (("record",1,4),), "record-all", "read_record", 'if line.kind in ALL_OPENINGS or line.kind in ALL_CLOSES:'),
    ("record-metadata", "record-metadata", ("anchor",1,0), CON_R, "record-all", "read_record", 'rec.ordered = all(a <= b for a, b in zip(dated, dated[1:]))'),
    ("record-pair-transaction", "analysis-line", ("record",1,4), CON_R, "episode", "analyse", 'ep = Episode(rec, ln.lane, opening, ln, st["gate"],'),
    ("later-opening", "analysis-line", ("record",1,9), CON_R, "episode", "analyse", 'ep.resumed_later = True'),
    ("gate-reach", "analysis-line", ("record",1,2), CON_R, "gate", "analyse", 'gates.append(ln.n)'),
    ("marker-vocabulary", "analysis-line", ("record",1,10), CON_R, "marker", "analyse", 'if ln.lane is None or not (ln.kind in ALL_OPENINGS or ln.kind in ALL_CLOSES):'),
    ("value-duration", "episode-duration", ("record",1,3), CON_EP, "episode", "compute", 'n_known += 1'),
    ("value-exit", "episode-exit", ("record",1,3), CON_EP, "episode", "compute", 'ep.exit = (st, v, note)'),
    ("value-review", "episode-review", ("record",1,3), CON_EP, "episode", "compute", 'ep.item, ep.item_note = positional(ep)'),
    ("value-denials", "episode-denials", ("record",1,3), CON_EP, "episode", "compute", 'ep.denials = denial_values(ep.close.obj)'),
    ("value-spend", "episode-spend", ("record",1,3), CON_EP, "episode", "compute", 'ep.spend, ep.plan = (basis, v, note), None'),
    ("boundary-independent", "boundary-value", ("record",1,5), (("record",1,5),), "boundary", "compute", 'key = idle_source(o)'),
    ("boundary-refusals", "boundary-refusals", ("record",1,5), (("record",1,5),), "boundary", "compute", 'hf += n'),
    ("value-beat", "beat-value", ("record",1,6), (("record",1,6),), "beat", "compute", 'b_n += 1'),
    ("value-snapshot", "snapshot-value", ("record",1,5), (("record",1,5),), "boundary", "compute", 'snaps.append((ln, field, st, v, note))'),
    ("late-main-row", "main-row-helper-time", ("global",0,0), CON_ALL_RECORDS, "global-episode", "render_rows", 'out.append("| " + " | ".join(cell(x) for x in r) + " |")'),
    ("late-detail-episode", "detail-episode", ("record",1,3), CON_EP, "episode", "render", 'sp = ep.spend'),
    ("late-helper-view", "detail-view", ("global",0,0), CON_ALL_RECORDS, "global-episode", "render", 'text = lambda key, view=view: res["view_text"](view, key)'),
    ("late-review-group", "detail-group", ("record",1,3), CON_EP, "episode", "render", 'gate_lines = sorted(set(e.gate.n for e in eps))'),
    ("late-inventory", "detail-inventory", ("anchor",1,0), CON_R, "record-all", "render", 'status = r.status + (": " + r.reason if r.reason else "")'),
    ("late-exact-spend", "detail-exact", ("record",1,3), CON_EP, "episode", "render", 'exact = xadd(exact, ep.spend[1])'),
    ("late-sort-key", "sort-key", ("global",0,0), CON_ALL_RECORDS, "global-episode", "view_text", 'return (shown(key) if view == "run" else class_text(key) if view == "class"'),
    ("late-stdout", "stdout", ("global",0,0), CON_ALL_RECORDS, "global-all", "cmd_report", '# The rows compute marked for the summary, never found by their text, which can quote a record.'),
    ("late-encoding-main", "encode-main", ("global",0,0), CON_ALL_RECORDS+CON_STORES, "global-all-store", "write_atomic", 'handle.write(text)'),
    ("late-encoding-detail", "encode-detail", ("global",0,0), CON_ALL_RECORDS+CON_STORES, "global-all-store", "write_atomic", 'handle.write(text)'),
    ("late-encoding-stdout", "encode-stdout", ("global",0,0), CON_ALL_RECORDS+CON_STORES, "global-all-store", "cmd_report", 'print("  %s · %s: %s [%s]" % (figure, part, value, status))'),
    ("late-outgoing", "outgoing", ("global",0,0), CON_ALL_RECORDS+CON_STORES, "persistence", "append_store", 'data = "".join(json.dumps(r, sort_keys=True) + "\\n" for r in records).encode("utf-8")'),
]
CON_CASES += [
    ("record-identity", "record-identity", ("record",1,4), (("record",1,4),), "episode", "read_record", "line.lane = lane"),
    ("value-class", "episode-duration", ("record",1,3), CON_EP, "episode", "class_of", "b, pb = class_value(ep.opening.obj)"),
    ("value-plan", "episode-spend", ("record",1,3), CON_EP, "episode", "compute", "ep.plan = (st, pnote, toks)"),
    ("gate-between", "analysis-line", ("record",1,3), CON_R, "gate", "analyse", "gates.append(ln.n)"),
    ("undated-ordered-neighbours", "record-time", ("record",1,5), (("record",1,5),), "record-all", "read_record", "if line.kind in ALL_OPENINGS or line.kind in ALL_CLOSES:"),
    ("undated-unordered-neighbours", "record-time", ("record",1,5), (("record",1,5),), "record-all", "read_record", "if line.kind in ALL_OPENINGS or line.kind in ALL_CLOSES:"),
    ("marker-respawned", "analysis-line", ("record",1,10), CON_R, "marker", "analyse", "if ln.lane is None or not (ln.kind in ALL_OPENINGS or ln.kind in ALL_CLOSES):"),
    ("marker-swapped", "analysis-line", ("record",1,10), CON_R, "marker", "analyse", "if ln.lane is None or not (ln.kind in ALL_OPENINGS or ln.kind in ALL_CLOSES):"),
    ("marker-pre-kind", "record-decode", ("record",1,10), (("record",1,10),), "record-all", "read_record", 'obj = loads_strict(raw.decode("utf-8"))'),
    ("late-key", "main-key", ("global",0,0), CON_ALL_RECORDS+CON_STORES, "global-all-store", "render", 'lines.append("- %s: %s" % (key, status))'),
    ("late-gap", "detail-gap-2", ("record",1,5), (("record",1,5),), "boundary", "render", 'g.where, fmt_local(g.when) if g.when is not None else "time unknown", g.reason,'),
    # Priced spend by session (FIELDS.md, "Priced spend"): r.jsonl's sessions are one collection, its anchor the
    # owner and its result-basis lines (worker's close 4, the beat 6, other's close 8) the suppliers; a failure
    # withdraws r.jsonl's priced closes and beats, s.jsonl's $5.00 kept.
    ("value-session", "spend-session", ("anchor",1,0), (("record",1,4), ("record",1,6), ("record",1,8)), "spend",
     "session_spend", 'record_sessions(rec, lines, record_losses(lines, unpaired.get(rec, ()), damaged), start, out)'),
]
for _n, _kind in enumerate(("init", "report", "listed", "disposition", "abandoned", "run-ended"), 1):
    CON_CASES.append(("store-"+_kind, "store-validate", ("store",0,_n), (("store",0,_n),), "store-"+_kind,
                      "read_store", 'why = store_line_problem(rec)'))
for _name, _route, _n, _effect, _func, _site in (
        ("default-start-diagnostic", "store-select", 2, "diagnostic", "cmd_report", 'e = parse_ts(rec["interval"][1])'),
        ("store-history", "store-history", 3, "store-listed", "cmd_report", 'listed.setdefault(rec["key"], rec)'),
        ("store-chronology", "store-history", 2, "store-report", "cmd_report", 'prev_report = n'),
        ("late-selector-diagnostic", "store-history", 2, "diagnostic", "cmd_report", 'prev_report = n'),
        ("store-disposition-supersession", "store-history", 7, "store-disposition", "cmd_report", 'disposed[rec["key"]] = rec'),
        ("store-abandonment-supersession", "store-validate", 3, "store-abandoned", "read_store", 'why = store_line_problem(rec)'),
        ("store-run-ending-supersession", "store-validate", 3, "store-run-ended", "read_store", 'why = store_line_problem(rec)'),
        ("store-pre-kind-union", "store-kind", 7, "store-union", "read_store", 'why = store_line_problem(rec)'),
        ("late-store-presentation", "main-determination", 5, "store-abandoned", "render", 'rec["kind"], what, rec["at"], effect, rec.get("evidence")))')):
    CON_CASES.append((_name,_route,("store",0,_n),(("store",0,_n),),_effect,_func,_site))


def con_invoke(mod, fx, default=False):
    args = ["--records",fx.records,"--tools-dir",fx.tools,"--until",UNTIL]
    if not default:
        args += ["--since",SINCE]
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = mod.main(args)
    reports = os.path.join(fx.tools,"reports")
    main = open(os.path.join(reports,"waste-report-"+UNTIL+".md"),encoding="utf-8").read()
    detail = open(os.path.join(reports,"waste-detail-"+UNTIL+".md"),encoding="utf-8").read()
    return code,out.getvalue(),err.getvalue(),main,detail


def con_fault(ctx, definition, exception=NameError):
    name,route,owner,sources,effect,fn,site = definition
    fx = con_fixture(ctx,"con-"+name)
    if name in ("store-abandonment-supersession", "store-run-ending-supersession"):
        store_path = os.path.join(fx.tools, "dispositions.jsonl")
        entries = [json.loads(l) for l in open(store_path)]
        kind = "abandoned" if name == "store-abandonment-supersession" else "run-ended"
        # No carried figure keys: earlier applicable authority, then a later unidentified entry.
        entries = [entries[0], next(l for l in entries if l["kind"] == kind), {"kind": kind}]
        with open(store_path, "w") as handle:
            handle.write("".join(json.dumps(l) + "\n" for l in entries))
    rpath = os.path.join(fx.records, "r.jsonl")
    records = [json.loads(l) for l in open(rpath)]
    changed = True
    if name == "gate-between":
        records.insert(2, records.pop(1))
    elif name.startswith("undated-") and name.endswith("neighbours"):
        records.insert(3, "not JSON before")
        records.insert(5, "not JSON after")
        if "unordered" in name:
            records[0]["ts"] = "2026-10-09T10:00:00+0100"
    elif name in ("marker-respawned", "marker-swapped"):
        records[9]["event"] = "lane-respawned" if name == "marker-respawned" else "lane-swapped"
    elif name == "value-plan":
        records[3].pop("total_cost_usd")
        records[3].update(cost_src="codex-plan", usage_state="complete", usage={"input_tokens":12,"output_tokens":3})
    elif name == "late-gap":
        records[4].pop("head_denials")
    else:
        changed = False
    if changed:
        fx.write("r.jsonl", records)
    mod = reader_module(ctx.script,"con_reader")
    mod.test_expected_ledger = None
    before = open(os.path.join(fx.tools,"dispositions.jsonl"),"rb").read()
    reached = []
    recoveries = []
    def fault(message):
        return UnicodeEncodeError("utf-8", "\ud800", 0, 1, message) if exception is UnicodeEncodeError else exception(message)
    if hasattr(mod,"Recovery"):
        def hook(r,o,phase):
            if r == route and o == owner and phase == ("before" if name=="record-before-blank" else "after"):
                reached.append((r,o))
                recoveries.append(mod._ACTIVE)
                raise fault("PRIVATE-EXCEPTION-TEXT")
        mod.boundary_hook=hook
        if name in ("value-class", "value-plan"):
            mod.boundary_hook=lambda *args: None
            function = "class_of" if name == "value-class" else "plan_usage"
            original = getattr(mod, function)
            def failing_value(value):
                result = original(value)
                target = value.rec.name == "r.jsonl" if name == "value-class" else value.get("usage_state") == "complete"
                if target:
                    reached.append((route,owner));recoveries.append(mod._ACTIVE)
                    raise fault("PRIVATE-EXCEPTION-TEXT")
                return result
            setattr(mod,function,failing_value)
    else:
        source = open(ctx.script,encoding="utf-8").read().splitlines()
        hits=[i+1 for i,l in enumerate(source) if l.strip()==site.strip()]
        # A comment is not a trace event; the next executable summary loop is the target instead.
        if name=="late-stdout":
            hits=[i+1 for i,l in enumerate(source) if l.strip()=='for figure, part, value, status, _ in res["summary"]:']
        expect(hits,"PROBE FAILED: base site missing for "+name)
        def trace(frame,event,arg):
            if event!='line' or frame.f_code.co_name!=fn or frame.f_lineno not in hits or reached:
                return trace
            loc=frame.f_locals
            if owner[0]=='record':
                line=loc.get('ln') or loc.get('line')
                rec=getattr(line,'rec',None) if line is not None else loc.get('rec')
                ep=loc.get('ep')
                episode_route=route.startswith('episode-') or route in ('detail-episode','detail-exact')
                if ep is not None and episode_route: rec=ep.rec
                if fn=='render' and name=='late-review-group':
                    rec=loc['eps'][0].rec
                if fn=='render' and name=='late-gap':
                    if loc['g'].where!='r.jsonl:'+str(owner[2]):return trace
                    rec=None
                if rec is not None and rec.name!='r.jsonl':return trace
                number=loc.get('n') if fn=='read_record' else getattr(line,'n',None)
                if fn=='read_record' and number!=owner[2]:return trace
                if fn in ('analyse','compute') and line is not None and not episode_route and number!=owner[2]:return trace
            if owner[0]=='store' and fn in ('read_store','cmd_report') and loc.get('n')!=owner[2]:return trace
            reached.append((fn,frame.f_lineno))
            raise fault("BASE-CAUSAL-INJECTION "+name)
        sys.settrace(trace)
    try:
        result=con_invoke(mod,fx,effect=="diagnostic")
    finally:
        sys.settrace(None)
    code,out,err,main,detail=result
    expect(len(reached)==1,"injection was not reached exactly once: %r" % reached)
    expected=[(route,owner,tuple(sources),exception.__name__)]
    expect(mod.test_ledger==expected,"ledger differs: got %r, want %r" % (mod.test_ledger,expected))
    expect(code==(1 if effect.startswith('store-') or effect in ('diagnostic','persistence','global-all-store') else 0),"exit %s" % code)
    expect('PRIVATE-EXCEPTION-TEXT' not in main+detail+out+err,'exception message leaked')
    for report in (main,detail):
        expect(route in report and exception.__name__ in report,'missing failure ledger')
        for source in sources:
            label=('store line '+str(source[2]) if source[0]=='store' else
                   ('r.jsonl','s.jsonl','z.jsonl')[source[1]-1]+':'+str(source[2]))
            expect(label in report,'lost physical provenance '+label)
    after=open(os.path.join(fx.tools,"dispositions.jsonl"),"rb").read()
    if effect in ('diagnostic','persistence'):
        expect(before==after,'a no-append branch changed history')
    if effect=='diagnostic':
        expect('start unresolved' in main+detail and 'known subtotal' not in main+detail,'invented diagnostic interval')
        expect('helper-time@' not in main+detail and 'no interval was recorded' in out,'diagnostic advanced a normal interval')
    else:
        rows=as_map(rows_of(main))
        duration=rows[(H,'total')][:2]
        if effect in ('episode','record-all'):
            expect(duration==('unknown; known subtotal 11 s (0.2 min)','unknown'),'withdrawal: '+repr(duration))
            expect(rows[(H,'helper s/"safe"')][:2]==('11 s (0.2 min)','complete'),'independent helper changed')
        elif effect=='global-episode':
            # The whole helper-view collection has all episode suppliers; boundaries are disjoint.
            expect(rows[(B,'boundary events')][:2]==('2','complete'),'disjoint boundaries changed')
        elif not effect.startswith('global-all'):
            expect(duration==('101 s (1.7 min)','complete'),'independent episode consumption changed: '+repr(duration))
        if effect=='episode':
            expect(rows[(B,'boundary events')][:2]==('2','complete'),'episode failure reached boundaries')
            expect(rows[(F,'non-completed, later resumed')][1]=='unknown','resumed status remained definite')
            expect(rows[SP_PC][1]=='unknown' and rows[SP_TCI][1]=='unknown','plan/basis uncertainty lost')
            expect('unknown; known subtotal $5.00' in detail,'exact subtotal stayed known or retained withdrawn dollars')
        if effect=='boundary':
            expect(rows[(B,'boundary events')][:2]==('unknown; known subtotal 1','unknown'),'boundary withdrawal wrong')
            expect(rows[(RF,'helper sandbox')][:2]==('9','complete'),'helper refusal lost')
        if effect=='marker':
            expect(rows[(F,'non-completed, later resumed')][:2]==('1','complete'),'marker changed resumed status')
        if effect=='spend':
            expect(rows[SP_T][:2]==('unknown; known subtotal $5.00','unknown'),'session withdrawal: '+repr(rows[SP_T]))
            expect(rows[(B,'boundary events')][:2]==('2','complete'),'session failure reached boundaries')
            expect('unknown; known subtotal $5.00 over' in detail,'the detail kept withdrawn session dollars')
        if name=='late-key':
            expect('carried@old: undetermined' in main,'terminal key row lost an observed carried key')
        if name=='late-inventory':
            expect(any(l.startswith('| r.jsonl | unknown |') for l in section(detail,'## Inventory: every candidate record')),'terminal inventory lost the candidate')
        if name.startswith('undated-') and name.endswith('neighbours'):
            expect('r.jsonl:4' in detail and 'r.jsonl:6' in detail,'invalid neighbour lost')
        if effect=='gate':
            expect(rows[(RV,'reviewing-class episodes')][:2]==('1','complete'),'gate lost reviewing-class count')
            expect(rows[(RV,'positional candidate groups')][1]=='unknown','gate reach stayed known')
        if effect=='store-disposition':
            expect('carried@old: undetermined' in main and 'listed by this report; undetermined' in main,'authoritative fallback')
        if effect=='store-abandoned':
            expect('exclusion authority unknown' in main and 'helper "open", line 2' in main,'exclusion candidate lost')
        if effect=='store-run-ended':expect('adjusted run coverage unknown' in main,'ending became definitely open')
        if effect=='store-listed':expect('carried-key inventory incomplete' in main,'inventory claimed complete')
        if effect not in ('persistence',):
            appended=[json.loads(l) for l in after[len(before):].splitlines()]
            expect(appended and appended[0]['kind']=='report','no final report entry')
            # Every append-capable containment path shares this publication invariant.
            retained = {entry["key"] for entry in appended if entry["kind"] == "listed"}
            if name not in ("store-listed", "store-abandonment-supersession", "store-run-ending-supersession"):
                retained.add("carried@old")
            for report in (main, detail):
                for key in retained:
                    expect(any(line.startswith("- " + key + ":") for line in report.splitlines()),
                           "contained path appended history but lost key " + key)
            if not effect.startswith('store-'):
                expect(any(l.get('key','').startswith('coverage@') for l in appended),'late gap missed coverage key')
    if recoveries:
        recovery=recoveries[-1]
        expect(recovery.generations<=len(recovery.failed)+1,'replay count exceeded monotone bound')
        expect(len(recovery.failed)<=len(mod.ROUTES)*len(recovery.owners),'slot bound exceeded')
    print('    D reached=1 ledger=1; source/affected/independent/persistence checks',flush=True)


for _definition in CON_CASES:
    def _test(ctx, definition=_definition):
        con_fault(ctx,definition)
    case(9,'CON-'+_definition[0])(_test)


@case(9,'CON-exception-policy')
def con_exception_policy(ctx):
    for cls in (ValueError,AssertionError):
        con_fault(ctx,CON_CASES[9],cls)
    # These are control signals, including invalid-data signals accidentally escaping their handler.
    for name in ('Probe','Bad','NotOpened','KeyboardInterrupt','SystemExit','GeneratorExit'):
        fx=con_fixture(ctx,'policy-'+name);m=reader_module(ctx.script,'policy')
        typ=getattr(m,name,None) or getattr(__import__('builtins'),name)
        reached=[]
        def hook(route,owner,phase):
            if route=='episode-duration' and owner==('record',1,3):
                reached.append(1);raise typ('control')
        m.boundary_hook=hook
        out=io.StringIO()
        try:
            with contextlib.redirect_stdout(out),contextlib.redirect_stderr(out):
                code=m.main(['--records',fx.records,'--tools-dir',fx.tools,'--since',SINCE,'--until',UNTIL])
            expect(name=='Probe' and code==2,'control was swallowed')
        except typ:
            expect(name!='Probe','Probe should use main exit-2 route')
        expect(reached and not m.test_ledger,'control entered the unexpected ledger')
        expect(not os.listdir(os.path.join(fx.tools,'reports')),'control signal published output')


@case(9,'CON-failure-creates-failure')
def con_chain(ctx):
    fx=con_fixture(ctx,'chain');m=reader_module(ctx.script,'chain');m.test_expected_ledger=None
    hits=[];states=[]
    def hook(route,owner,phase):
        if phase=='after' and ((route=='episode-duration' and owner==('record',1,3)) or
                               (route=='detail-gap-1' and len(hits)==1)):
            hits.append((route,owner));states.append(m._ACTIVE);raise NameError('chain')
    m.boundary_hook=hook
    code,out,err,main,detail=con_invoke(m,fx)
    expect(code==0 and len(hits)==2 and len(m.test_ledger)==2,'containment-created failure did not finish')
    expect(all(route in main and route in detail for route,_ in hits),'late ledger not refreshed')
    expect(as_map(rows_of(main))[(H,'helper s/"safe"')][:2]==('11 s (0.2 min)','complete'),'independent record lost')
    expect(states[-1].generations==3,'chain did not take failures plus one generations')
    expect(as_map(rows_of(main))[(B,'boundary events')][:2]==('2','complete'),'gap presentation contaminated disjoint boundaries')
    report=[json.loads(l) for l in open(os.path.join(fx.tools,'dispositions.jsonl')) if json.loads(l)['kind']=='report'][-1]
    gap_line=next(l for l in main.splitlines() if l.startswith('- Named gaps affecting'))
    expect(str(report['not_seen']) in gap_line,'append gap count stale')


@case(9,'CON-zero-and-control')
def con_zero(ctx):
    zero=Fx(ctx.root,'zero',script=ctx.script)
    zero.write('r.jsonl',[{'event':'observation','ts':'2026-09-01T00:00:00Z'}])
    code,out,err,main,detail=zero.report()
    expect(code==0 and as_map(rows_of(main))[(H,'total')][:2]==('0 s (0.0 min)','complete'),'clean zero wrong')
    positive=con_fixture(ctx,'positive');code,out,err,main,detail=positive.report()
    expect(code==0 and as_map(rows_of(main))[(H,'total')][:2]==('101 s (1.7 min)','complete'),'positive control failed')


@case(9,'CR7-suffix')
def cr7_suffix(ctx):
    fx=con_fixture(ctx,'suffix')
    bad=['9'*5000,'0','-1','01','١','1x']
    append_store_lines(fx,[{'kind':'abandoned','episode':'z:open:'+tail,'evidence':'named','at':'2026-10-04T10:00:00+0100'} for tail in bad])
    code,out,err,main,detail=fx.report()
    expect(code==1 and main is not None and detail is not None,'oversized suffix aborted reports')
    expect(main.count('invalid opening-line suffix')==len(bad),'bad suffix not named')
    expect(as_map(rows_of(main))[(H,'total')][:2]==('101 s (1.7 min)','complete'),'suffix changed independent figures')


@case(9,'CR7-suffix-controls')
def cr7_suffix_controls(ctx):
    m=reader_module(ctx.script,'suffix_controls')
    expect(m.positive_line_number(str(sys.maxsize))==sys.maxsize,'derived bound rejected')
    expect(m.positive_line_number(str(sys.maxsize+1)) is None,'over-bound accepted')
    expect(m.positive_line_number(10**5000) is None,'structured huge integer converted')
    fx=con_fixture(ctx,'suffix-cli');before=tree_manifest(fx.tools)
    code,out,err=fx.run('abandon','z:open:'+'9'*5000,'--evidence','named')
    expect(code==2 and tree_manifest(fx.tools)==before,'CLI oversized suffix wrote')
    code,out,err=fx.run('abandon','z:open:2','--record','z.jsonl','--helper','open','--line','9'*5000,'--evidence','named')
    expect(code==2 and tree_manifest(fx.tools)==before,'structured CLI wrote')


@case(9,'CR7-exact-start')
def cr7_exact_start(ctx):
    fx=Fx(ctx.root,'exact-start',script=ctx.script)
    events=[]
    for lane,stamp in [('before','2026-10-05T10:00:00.25+0100'),('at','2026-10-05T10:00:00.5+0100'),('end','2026-10-12T00:00:00+0100')]:
        pair_events=priced_episode(lane,stamp)
        pair_events[0]["ts"]=stamp
        events+=pair_events
    fx.write('r.jsonl',events)
    pair=['2026-09-28T00:00:00+0100','2026-10-05T10:00:00.5+0100']
    append_store_lines(fx,[{'kind':'report','interval':pair},{'kind':'listed','key':'old@fraction','interval':pair}])
    code,out,err,main,detail=fx.report(since=None)
    expect(code==0,'fraction report aborted')
    expect(as_map(rows_of(main))[(H,'total')][:2]==('60 s (1.0 min)','complete'),'fraction membership wrong')
    expect('old@fraction: open, carried' in main,'carried key lost')
    expect('2026-10-05 10:00:00.5 +0100' in main and '10:00:00.5+0100..' in main,'exact start label lost')
    report=[json.loads(l) for l in open(os.path.join(fx.tools,'dispositions.jsonl')) if json.loads(l)['kind']=='report'][-1]
    expect(report['interval'][0]==pair[1],'stored start truncated')


@case(9,'CR7-exact-endpoints')
def cr7_exact_endpoints(ctx):
    m=reader_module(ctx.script,'exact')
    values=['2026-10-05T10:00:00.5+0100','2026-10-05T10:00:00.75+0100','2026-10-05T10:00:00.000000001+0100']
    instants=[m.parse_ts(v) for v in values]
    labels=[m.interval_label(t,m.parse_ts('2026-10-12T00:00:00+0100')) for t in instants]
    expect(len(set(labels))==3,'fractional interval identities collided')
    expect(all(m.parse_ts(m.iso_exact(t))==t for t in instants),'exact serialiser lost precision')
    expect(m.parse_ts('2026-10-05T09:00:00.5Z')==instants[0],'equivalent offset differs')
    fx=con_fixture(ctx,'fraction-end');original=m.parse_day
    m.parse_day=lambda text,what: instants[1] if what=='--until' else original(text,what)
    code,out,err,main,detail=con_invoke_fraction(m,fx)
    report=[json.loads(l) for l in open(os.path.join(fx.tools,'dispositions.jsonl')) if json.loads(l)['kind']=='report'][-1]
    expect(m.parse_ts(report['interval'][1])==instants[1],'stored end truncated')


def con_invoke_fraction(m,fx):
    out=io.StringIO()
    with contextlib.redirect_stdout(out):
        code=m.main(['--records',fx.records,'--tools-dir',fx.tools,'--since',SINCE,'--until',UNTIL])
    files=os.listdir(os.path.join(fx.tools,'reports'))
    expect(len(files)==2 and code==0,'fractional-end report missing')
    return code,out.getvalue(),'','',''


@case(9,'CR7-helper-labels')
def cr7_helper_labels(ctx):
    fx=Fx(ctx.root,'helper-labels',script=ctx.script)
    names=['A\nB','A\\nB','A B']
    events=[]
    for name in names:events+=priced_episode(name,'2026-10-06T10:01:00+0100')
    fx.write('r.jsonl',events)
    code,out,err,main,detail=fx.report()
    expect(code==0,'helper labels aborted')
    expect(as_map(rows_of(main))[(H,'total')][:2]==('180 s (3.0 min)','complete'),'helper quoting changed totals')
    lines=detail.splitlines();i=lines.index('### By helper')
    view=lines[i+1:i+1+len(names)]
    for name in names:
        label=json.dumps(name,ensure_ascii=True)
        expect(sum(l.startswith('- r/'+label+': ') for l in view)==1,'missing or ambiguous helper '+label)
        expect('r:'+label.replace('|','\\|')+':' in detail,'episode helper representation differs')
        expect('helper r/'+label.replace('|','\\|') in main,'main helper representation differs')
    expect(len(set(view))==len(names),'helper rows collide')



@case(9,'CON-detector-controls')
def con_detector(ctx):
    src=open(ctx.script,encoding='utf-8').read()
    # Both mutants return otherwise plausible reports; assertions run outside reader containment.
    planted='    try:\n        raise NameError("planted")\n    except Exception:\n        containment_observer(("planted", ("global", 0, 0), (), "NameError"))\n'
    mutant=os.path.join(ctx.root,'observed-mutant.py')
    mutate(ctx.script,mutant,[('def compute(recs, an, start, end):\n','def compute(recs, an, start, end):\n'+planted)])
    caught=[]
    for path in ('subprocess','direct'):
        fx=con_fixture(ctx,'detector-'+path)
        try:
            if path=='subprocess':fx.report(script=mutant)
            else:
                m=reader_module(mutant,'mutant');con_invoke(m,fx)
        except AssertionError as exc:
            expect('unexpected containment ledger' in str(exc),'detector failed for an unrelated reason: '+str(exc))
            caught.append(path)
    expect(caught==['subprocess','direct'],'zero-fire detector missed broad catch')
    silent=os.path.join(ctx.root,'silent-mutant.py')
    mutate(ctx.script,silent,[('        containment_observer(event)','        pass  # planted silent catch')])
    child=Ctx(ctx.root,silent)
    try:con_fault(child,CON_CASES[9])
    except AssertionError as exc:expect('ledger differs' in str(exc),'silent detector failed for wrong reason')
    else:raise AssertionError('silent catch evaded reached/expected-ledger assertions')
    def broad_catches(text):
        tree=ast.parse(text);found=[]
        for fn in tree.body:
            if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)):
                for node in ast.walk(fn):
                    if isinstance(node,ast.ExceptHandler) and (node.type is None or
                        isinstance(node.type,ast.Name) and node.type.id in ('Exception','BaseException')):
                        if fn.name!='boundary':found.append((fn.name,node.lineno))
        return found
    expect(not broad_catches(src),'new broad input catch bypasses the primitive')
    expect(broad_catches(open(mutant).read()),'source audit missed planted bypass')
    print('    C detector positives: subprocess, direct, silent-ledger mutant, source-bypass mutant',flush=True)


@case(9,'CON-terminal-bound')
def con_bound(ctx):
    fx=con_fixture(ctx,'terminal-bound');m=reader_module(ctx.script,'bound');m.test_expected_ledger=None
    attempts={};states=[]
    def hook(route,owner,phase):
        if phase=='after':
            slot=(route,owner);attempts[slot]=attempts.get(slot,0)+1;states.append(m._ACTIVE)
            raise NameError('every reached slot')
    m.boundary_hook=hook
    code,out,err,main,detail=con_invoke(m,fx)
    state=states[-1]
    expect(code==1 and len(attempts)>10,'terminal control traversed no useful routes')
    expect(all(n==1 for n in attempts.values()),'a terminal callable was retried')
    expect(len(m.test_ledger)==len(attempts)==len(state.failed),'terminal ledger lost a failure')
    expect(state.generations<=len(state.failed)+1 and len(state.failed)<=len(m.ROUTES)*len(state.owners),'finite bound violated')
    for route,owner,sources,token in m.test_ledger:
        expect(route in main and route in detail,'terminal emitter lost ledger entry')
    hostile='pipe|slash\\tick`newline\n\ud800\u2028'
    encoded=m.terminal_text(hostile)
    expect(encoded.isascii() and '\n' not in encoded and '|' not in encoded,'terminal encoding is unsafe')
    print('    C terminal slots=%d generations=%d bound=%d' % (len(state.failed),state.generations,len(m.ROUTES)*len(state.owners)),flush=True)


@case(9,'CON-readonly-and-source-controls')
def con_readonly(ctx):
    fx=con_fixture(ctx,'readonly')
    fx.write('r-waste-table.md',['table bytes'])
    before=tree_manifest(fx.records)
    for path in before:
        if os.path.isfile(path):os.chmod(path,0o444)
    os.chmod(fx.records,0o555)
    before=tree_manifest(fx.records)
    try:
        code,out,err,main,detail=fx.report()
        expect(code==0 and tree_manifest(fx.records)==before,'read-only input manifest changed')
    finally:os.chmod(fx.records,0o755)
    src=open(ctx.script,encoding='utf-8').read()
    pattern=re.compile(r'open\([^\n]*(?:["\x27][wa][b]?["\x27]|O_WRONLY|O_RDWR|O_CREAT|O_APPEND|O_TRUNC)|os\.(?:replace|rename|unlink|remove|mkdir|makedirs|rmdir)\(')
    def prohibited(text):
        tree=ast.parse(text);lines=text.splitlines();hits=[]
        for fn in tree.body:
            if isinstance(fn,ast.FunctionDef) and fn.name not in ('append_store','write_atomic','cmd_init'):
                body='\n'.join(lines[fn.lineno-1:fn.end_lineno])
                hits+=pattern.findall(body)
        return hits
    expect(not prohibited(src),'input writer in source')
    expect(prohibited(src+'\ndef planted(rec):\n    open(rec.path, "w")\n'),'source grep missed planted input write')
    expect(SPAWN_PATTERN.findall(src+'\nimport subprocess\n'),'process grep positive failed')
    expect(not SPAWN_PATTERN.findall(src),'production process launcher added')
    m=reader_module(ctx.script,'frozen');value=m.immutable_json({'nested':[{'value':1}]})
    try:value['nested'][0]['value']=2
    except TypeError:pass
    else:raise AssertionError('input envelope payload remained mutable')
    print('    C read-only manifest unchanged; input-write/process source positives hit; immutable payload mutation refused',flush=True)



@case(9,'CON-diagnostic-repeat-repair')
def con_diagnostic_repeat(ctx):
    fx=con_fixture(ctx,'diagnostic-repeat')
    before=open(os.path.join(fx.tools,'dispositions.jsonl'),'rb').read()
    for attempt in range(2):
        m=reader_module(ctx.script,'diagnostic_repeat');m.test_expected_ledger=None
        calls=[]
        for name in ('compute','determinations'):
            original=getattr(m,name)
            def spy(*a,_original=original,_name=name,**kw):
                calls.append(_name);return _original(*a,**kw)
            setattr(m,name,spy)
        def hook(route,owner,phase):
            if route=='store-validate' and owner==('store',0,2) and phase=='after':raise NameError('report line')
        m.boundary_hook=hook
        code,out,err,main,detail=con_invoke(m,fx,True)
        expect(code==1 and not calls,'unresolved generation evaluated an interval')
        expect(open(os.path.join(fx.tools,'dispositions.jsonl'),'rb').read()==before,'diagnostic advanced history')
        expect(len(m.test_ledger)==1,'unexpected extra diagnostic catch')
    # The same fault with an explicit start permits truthful figures and append.
    code,out,err,main,detail=con_invoke(m,fx,False)
    expect(code==1 and as_map(rows_of(main))[(H,'total')][:2]==('101 s (1.7 min)','complete'),'explicit start did not recover figures')
    m=reader_module(ctx.script,'repaired')
    code,out,err,main,detail=con_invoke(m,fx,True)
    expect(code==0 and 'start unresolved' not in main,'repaired selector did not recover')


@case(9,'CON-encoding-exceptions')
def con_encoding_exceptions(ctx):
    for definition in CON_CASES:
        if definition[0] in ('late-encoding-main','late-encoding-detail','late-encoding-stdout'):
            con_fault(ctx,definition,UnicodeEncodeError)



@case(9,'CON-unencodable-label')
def con_unencodable_label(ctx):
    fx=Fx(ctx.root,'filename',script=ctx.script)
    fx.write('safe.jsonl',priced_episode('safe','2026-10-06T10:01:00+0100'))
    m=reader_module(ctx.script,'filename');acquire=m.acquire
    def labelled(path):
        recs,others,volume=acquire(path)
        # A filesystem-independent acquisition double: no non-UTF-8 pathname is written.
        recs[0].name='bad-\udcff.jsonl'
        recs[0].stem='bad-\udcff'
        for source in recs[0].sources:
            m._ACTIVE.register(source,recs[0].name+':'+str(source[2]),recs[0].name)
        return recs,others,volume
    m.acquire=labelled
    code,out,err,main,detail=con_invoke(m,fx)
    expect(code==0 and '\\udcff' in detail,'unencodable filename not represented safely')
    expect(as_map(rows_of(main))[(H,'total')][:2]==('60 s (1.0 min)','complete'),'filename changed measured consumption')


@case(9,'CR7-helper-edge-labels')
def cr7_helper_edges(ctx):
    fx=Fx(ctx.root,'helper-edges',script=ctx.script)
    names=['A"B','A|B','A\\|B','A\rB','A\u2028B','ordinary']
    events=[]
    for name in names:events+=priced_episode(name,'2026-10-06T10:01:00+0100')
    fx.write('r.jsonl',events)
    code,out,err,main,detail=fx.report()
    expect(code==0 and as_map(rows_of(main))[(H,'total')][:2]==('360 s (6.0 min)','complete'),'edge-name totals changed')
    for name in names:
        label=json.dumps(name,ensure_ascii=True)
        expect('- r/'+label+': ' in detail and 'r:'+label.replace('|','\\|')+':' in detail,'edge helper representation differs')
    expect(sum(l.startswith('| r:') for l in detail.splitlines())==len(names),'helper forged a table row')



@case(9,'CON-runtime-includes-recovery')
def con_runtime(ctx):
    fx=con_fixture(ctx,'runtime');m=reader_module(ctx.script,'runtime');m.test_expected_ledger=None
    original=m.time.time;clock=[original()];start=clock[0];hits=[]
    def hook(route,owner,phase):
        if route=='episode-duration' and owner==('record',1,3) and phase=='after':
            hits.append(1)
            clock[0]+=11  # Expected runtime is derived from this controlled eleven-second advance.
            raise NameError('timed recovery')
    m.boundary_hook=hook;m.time.time=lambda:clock[0]
    try:code,out,err,main,detail=con_invoke(m,fx)
    finally:m.time.time=original
    expect(code==0 and len(hits)==1 and len(m.test_ledger)==1,'runtime fixture missed its fault')
    expect('- Runtime: 11.00 s;' in main,'runtime omitted completed recovery work')


@case(9,'CR7-local-minute-label')
def cr7_local_minute(ctx):
    m=reader_module(ctx.script,'local_minute')
    # A historical local offset need not be a whole minute. The label tests the local second,
    # not the epoch's residue modulo sixty; its fraction still precludes omitting seconds.
    instant=m.parse_ts('1800-01-01T00:00:00Z')
    local=m.time.localtime(int(instant))
    expected=(local.tm_sec!=0 or m.wall_epochs(*local[:6])!={instant})
    expect(m.endpoint_seconds(instant)==expected,'local minute criterion differs from the clock')
    expect(m.endpoint_seconds(instant+m.Fraction(1,2)),'fractional minute omitted seconds')



@case(9,'CON-exception-value-error')
def con_value_error(ctx):
    con_fault(ctx,CON_CASES[9],ValueError)


@case(9,'CON-exception-assertion-error')
def con_assertion_error(ctx):
    con_fault(ctx,CON_CASES[9],AssertionError)


@case(9,'CON-marker-history-vocabulary')
def con_marker_history(ctx):
    fx=Fx(ctx.root,'marker-history',script=ctx.script)
    openings=('lane-resume','spawn','probe-open','lane-open')
    closes=('lane-close','close-out','close-out-2','probe-closed')
    events=[]
    for i,(opening,close) in enumerate(zip(openings,closes)):
        pair=priced_episode('L'+str(i),'2026-10-06T10:01:00+0100')
        pair[0]['event']=opening;pair[1]['event']=close
        events.append(pair[0])
        if i==0:
            for kind in ('lane-spawned','lane-respawned','lane-swapped','terminated','stalled','lane-aborted'):
                events.append({'event':kind,'ts':'2026-10-06T10:00:30+0100','lane':'L0'})
        events.append(pair[1])
    fx.write('vocabulary.jsonl',events)
    code,out,err,main,detail=fx.report()
    rows=as_map(rows_of(main))
    expect(code==0 and rows[(H,'total')][:2]==('240 s (4.0 min)','complete'),'historical vocabulary changed consumption')
    expect(rows[(F,'closes')][:2]==('4','complete'),'markers created closes')
    expect(rows[(F,'non-completed, later resumed')][:2]==('0','complete'),'markers created resumed status')
    expect('- Lines under a historical event name (FIELDS.md): 10,' in main,'historical aliases not inventoried')


# Closed-review regressions exercise the previous implementation's actual operations as well
# as the repaired routes. Every fault has a clean invocation over the same fixture first.
def cr8_fixture(ctx, name):
    fx = con_fixture(ctx, "cr8-" + name)
    return fx, reader_module(ctx.script, "cr8_" + name.replace("-", "_"))


def cr8_control(m, fx, check):
    before = tree_manifest(fx.records)
    result = con_invoke(m, fx)
    expect(result[0] == 0 and m.test_ledger == [], "clean companion failed")
    check(result[3], result[4])
    expect(tree_manifest(fx.records) == before, "clean companion wrote its inputs")
    return before


def cr8_store_fault(ctx, site, default=False):
    fx, m = cr8_fixture(ctx, "store-" + site + ("-default" if default else ""))
    records = cr8_control(m, fx, lambda main, detail: expect(
        as_map(rows_of(main))[(H, "total")][:2] == ("101 s (1.7 min)", "complete"),
        "clean independent measurements differ"))
    before = open(os.path.join(fx.tools, "dispositions.jsonl"), "rb").read()
    reached, stores = [], []
    read_store = m.read_store
    def observed_store(path):
        value = read_store(path)
        stores.append(value)
        return value
    m.read_store = observed_store
    m.test_expected_ledger = None
    if site == "construction":
        constructor = m.StoreEntry
        def faulty_entry(value, source):
            entry = constructor(value, source)
            if source == ("store", 0, 2):
                reached.append(source)
                raise NameError("CR8-CAUSAL store construction")
            return entry
        m.StoreEntry = faulty_entry
    else:
        source = open(ctx.script, encoding="utf-8").read().splitlines()
        anchors = ('st.lines.append((n, StoreEntry(rec, source)))',
                   'st.lines, st.observed_keys = previous_lines + [(n, entry)], keys')
        hits = [i + 1 for i, line in enumerate(source) if line.strip() in anchors]
        expect(len(hits) == 1, "PROBE FAILED: publication site is not unique")
        def trace(frame, event, arg):
            if (event == "line" and frame.f_code.co_name == "read_store"
                    and frame.f_lineno in hits and frame.f_locals.get("n") == 2 and not reached):
                reached.append(("store", 0, 2))
                raise NameError("CR8-CAUSAL store publication")
            return trace
        sys.settrace(trace)
    try:
        code, out, err, main, detail = con_invoke(m, fx, default)
    finally:
        sys.settrace(None)
    expect(reached == [("store", 0, 2)], "store fault was not reached exactly once")
    expect(m.test_ledger == [("store-entry", ("store", 0, 2), (("store", 0, 2),), "NameError")],
           "store candidate did not have a line-owned boundary")
    expect(code == 1 and all("store line 2" in text for text in (main, detail)), "store locator/completion lost")
    expect(stores and all(n != 2 for n, entry in stores[-1].lines), "failed entry was published")
    expect("CR8-CAUSAL" not in main + detail + out + err, "exception text leaked")
    after = open(os.path.join(fx.tools, "dispositions.jsonl"), "rb").read()
    if default:
        expect(before == after and "start unresolved" in main + detail and "no interval was recorded" in out,
               "uncertain report authority selected or persisted a default interval")
    else:
        expect(as_map(rows_of(main))[(H, "total")][:2] == ("101 s (1.7 min)", "complete"),
               "store failure withdrew independent record measurements")
        expect(len(after) > len(before) and "since-previous chronology unknown" in main,
               "explicit-start authority/append policy differs")
    expect(tree_manifest(fx.records) == records, "store fault wrote its record inputs")
    print("    D CR8 store %s: reached=1 ledger=1; both reports; independent figures; authority and publication checked"
          % site, flush=True)
    if site == "publication":
        # Fault after the assignment as well: both the entry and its cached key must roll back.
        fx2, m2 = cr8_fixture(ctx, "store-after-publication")
        m2.test_expected_ledger = None
        captures, attempts = [], []
        original = m2.read_store
        def capture(path):
            value = original(path); captures.append(value); return value
        def after(route, owner, phase):
            if route == "store-entry" and owner == ("store", 0, 3) and phase == "after":
                attempts.append(owner)
                raise NameError("CR8-CAUSAL after publication")
        m2.read_store, m2.boundary_hook = capture, after
        code, out, err, main, detail = con_invoke(m2, fx2)
        expect(code == 1 and attempts == [("store", 0, 3)], "after-publication fault not contained")
        expect(all(n != 3 for n, entry in captures[-1].lines) and "carried@old" not in captures[-1].observed_keys,
               "after-publication failure left a committed entry or key")
        expect(m2.test_ledger == [("store-entry", ("store", 0, 3), (("store", 0, 3),), "NameError")],
               "after-publication ledger differs")


@case(9, "CR8-store-construction")
def cr8_construction(ctx):
    cr8_store_fault(ctx, "construction")


@case(9, "CR8-store-construction-default")
def cr8_construction_default(ctx):
    cr8_store_fault(ctx, "construction", True)


@case(9, "CR8-store-publication")
def cr8_publication(ctx):
    cr8_store_fault(ctx, "publication")


@case(9, "CR8-terminal-key-history")
def cr8_keys(ctx):
    fx, m = cr8_fixture(ctx, "keys")
    append_store_lines(fx, [
        {"kind": "listed", "interval": ["2026-09-28T00:00:00+0100", "2026-10-05T00:00:00+0100"], "key": "carried@unresolved"},
        {"kind": "listed", "interval": ["2026-10-12T00:00:00+0100", "2026-10-19T00:00:00+0100"], "key": "observed@later"},
        {"kind": "listed", "interval": ["2026-09-28T00:00:00+0100", "2026-10-05T00:00:00+0100"], "key": "carried@old"}])
    records = cr8_control(m, fx, lambda main, detail: expect(
        "- carried@unresolved: open, carried" in main
        and "- carried@old:" not in main.split("Recorded since the previous report:", 1)[0],
        "clean history control did not distinguish open and disposed keys"))
    original, reached = m.prepare_history, []
    def fault(*args):
        original(*args)
        reached.append(True)
        raise NameError("CR8-CAUSAL combined history")
    m.prepare_history = fault
    m.test_expected_ledger = None
    code, out, err, main, detail = con_invoke(m, fx)
    expect(code == 1 and reached == [True] and len(m.test_ledger) == 1
           and m.test_ledger[0][:2] == ("keys", ("global", 0, 0)), "history fault/terminal bypass differs")
    print("    D CR8-CAUSAL combined history reached=1 ledger=1", flush=True)
    # Six current figure identities, plus every observed listed identity regardless of its
    # former disposition or now-undecidable interval membership.
    current = ("helper-time", "failed-closes", "review-activity", "phase-boundaries", "refusals", "priced-spend")
    expected = ("carried@old", "carried@unresolved", "observed@later") + tuple(
        key + "@" + SINCE + ".." + UNTIL for key in current)
    for key in expected:
        rows = [line for line in section(main, "## Dispositions") if line.startswith("- " + key + ":")]
        expect(len(rows) == 1 and "undetermined" in rows[0] and "membership unknown" in rows[0],
               "terminal history lost or decided observed key " + key)
        expect(any(line.startswith("- " + key + ":") for line in detail.splitlines()),
               "terminal detail lost observed key " + key)
    expect("- unknown: key history preparation unavailable" in main, "empty history claimed after failure")
    expect(tree_manifest(fx.records) == records, "key fallback wrote record inputs")
    print("    D CR8 keys: reached=1 ledger=1; observed carried/current keys retained with unknown membership/status", flush=True)


@case(9, "CR8-uncertain-run-state")
def cr8_runs(ctx):
    fx, m = cr8_fixture(ctx, "runs")
    r = [json.loads(line) for line in open(os.path.join(fx.records, "r.jsonl"))]
    r.append({"event": "run-close", "ts": "2026-10-14T10:00:00+0100", "run_spend_usd": 8})
    fx.write("r.jsonl", r)
    records = cr8_control(m, fx, lambda main, detail: expect(
        "- Runs open at acquisition: 0." in main
        and not any(line.startswith("- r ·") for line in section(detail, "## Runs open at acquisition"))
        and any(line.startswith("- z ·") for line in section(detail, "## Runs open at acquisition")),
        "clean close did not close the run"))
    reached = []
    def fault(route, owner, phase):
        if route == "analysis-line" and owner == ("record", 1, 11) and phase == "after":
            reached.append(owner)
            raise NameError("CR8-CAUSAL run close")
    m.boundary_hook, m.test_expected_ledger = fault, None
    code, out, err, main, detail = con_invoke(m, fx)
    expect(code == 0 and reached == [("record", 1, 11)] and len(m.test_ledger) == 1, "run-close fault differs")
    print("    D CR8-CAUSAL run close reached=1 ledger=1", flush=True)
    candidates = [line for line in section(detail, "## Runs open at acquisition") if line.startswith("- r ·")]
    expect(len(candidates) == 1 and "state unknown" in candidates[0], "failed close became a definite open run")
    expect("- Run r: state unknown;" in main and "- Runs open at acquisition: unknown;" in main,
           "main and detail do not consume the uncertain state")
    expect(as_map(rows_of(main))[(H, "total")][:2] == ("101 s (1.7 min)", "complete"),
           "run-state failure changed independent episode measurements")
    expect(tree_manifest(fx.records) == records, "run-state recovery wrote record inputs")
    print("    D CR8 run close: reached=1 ledger=1; candidate state unknown in both reports; 101 seconds retained", flush=True)


@case(9, "CR8-independent-groups")
def cr8_groups(ctx):
    fx, m = cr8_fixture(ctx, "groups")
    safe = [json.loads(line) for line in open(os.path.join(fx.records, "s.jsonl"))]
    safe[0]["class"] = safe[1]["class"] = "critic"
    safe.insert(0, {"event": "gate", "ts": "2026-10-06T10:00:00+0100", "item": "safe-item", "decision": "allow"})
    fx.write("s.jsonl", safe)
    records = cr8_control(m, fx, lambda main, detail: expect(
        "- r · item item ·" in detail and "- s · item safe-item ·" in detail
        and as_map(rows_of(main))[(RV, "positional candidate groups")][:2] == ("2", "complete"),
        "two independent groups were not established"))
    reached = []
    def fault(route, owner, phase):
        if route == "detail-group" and phase == "after" and m._ACTIVE.current_sources[0][1] == 1:
            reached.append(owner)
            raise NameError("CR8-CAUSAL first group")
    m.boundary_hook, m.test_expected_ledger = fault, None
    code, out, err, main, detail = con_invoke(m, fx)
    expect(code == 0 and len(reached) == len(m.test_ledger) == 1, "group fault differs")
    print("    D CR8-CAUSAL first group reached=1 ledger=1", flush=True)
    expect("- s · item safe-item · 1 reviewing-class episode" in detail, "independent group detail was suppressed")
    expect(as_map(rows_of(main))[(RV, "positional candidate groups")][:2]
           == ("unknown; known subtotal 1", "unknown"), "group subtotal disagrees with surviving detail")
    expect(m.test_ledger[0] == ("detail-group", ("record", 1, 3), CON_EP, "NameError"),
           "group does not have its own source owner")
    expect(tree_manifest(fx.records) == records, "group recovery wrote record inputs")
    print("    D CR8 groups: reached=1 ledger=1; independent group detail and known subtotal 1 agree", flush=True)


@case(9, "CR8-rendered-link-count")
def cr8_links(ctx):
    fx, m = cr8_fixture(ctx, "links")
    fx.write("r-waste-table.md", ["a table whose contents are never read"])
    records = cr8_control(m, fx, lambda main, detail: expect(
        "1 linked in the detail" in main and "- r: [r-waste-table.md]" in detail, "clean link control failed"))
    reached = []
    def fault(route, owner, phase):
        if route == "detail-table" and phase == "after":
            reached.append(owner)
            raise NameError("CR8-CAUSAL table link")
    m.boundary_hook, m.test_expected_ledger = fault, None
    code, out, err, main, detail = con_invoke(m, fx)
    expect(code == 0 and len(reached) == len(m.test_ledger) == 1, "link fault differs")
    print("    D CR8-CAUSAL table link reached=1 ledger=1", flush=True)
    expect("0 linked in the detail" in main and "[r-waste-table.md]" not in detail
           and "link presentation unavailable; 0 rendered" in detail, "terminal link count contradicts rendered links")
    expect(as_map(rows_of(main))[(H, "total")][:2] == ("101 s (1.7 min)", "complete"), "link failure changed measurements")
    expect(tree_manifest(fx.records) == records, "link recovery wrote record/table inputs")
    print("    D CR8 links: reached=1 ledger=1; zero rendered links in both reports; table manifest unchanged", flush=True)


CR9_KEY_ROUTES = ("analysis", "compute", "determinations", "tables", "render", "stdout",
                  "encode-main", "encode-detail", "encode-stdout", "main-key", "main-history")


def cr9_key_case(ctx, route):
    fx, m = cr8_fixture(ctx, "terminal-keys-" + route)
    append_store_lines(fx, [
        {"kind": "listed", "interval": ["2026-09-28T00:00:00+0100", "2026-10-05T00:00:00+0100"],
         "key": "carried@unresolved"},
        {"kind": "listed", "interval": ["2026-10-12T00:00:00+0100", "2026-10-19T00:00:00+0100"],
         "key": "observed@future"}])
    records = cr8_control(m, fx, lambda main, detail: expect(
        "- carried@unresolved: open, carried" in main
        and as_map(rows_of(main))[(H, "total")][:2] == ("101 s (1.7 min)", "complete"),
        "clean key and independent-value controls failed"))
    before = open(os.path.join(fx.tools, "dispositions.jsonl"), "rb").read()
    reached = []
    def fault(r, owner, phase):
        if r == route and phase == "after" and not reached:
            reached.append(owner)
            raise NameError("CR9-CAUSAL " + route)
    m.boundary_hook, m.test_expected_ledger = fault, None
    code, out, err, main, detail = con_invoke(m, fx)
    expect(code in (0, 1) and len(reached) == len(m.test_ledger) == 1
           and m.test_ledger[0][0] == route, "terminal fault was not reached exactly once")
    print("    D CR9-CAUSAL %s reached=1 ledger=1" % route, flush=True)
    after = open(os.path.join(fx.tools, "dispositions.jsonl"), "rb").read()
    appended = [json.loads(line) for line in after[len(before):].splitlines()]
    expect(appended and appended[0]["kind"] == "report", "established terminal path did not append its history")
    persisted = {line["key"] for line in appended if line["kind"] == "listed"}
    current = {key + "@" + SINCE + ".." + UNTIL for key in
               ("helper-time", "failed-closes", "review-activity", "phase-boundaries", "refusals", "priced-spend")}
    expect(current <= persisted and appended[0]["listed"] == len(persisted), "current history identities differ")
    observed = {"carried@old", "carried@unresolved", "observed@future"} | current | persisted
    for report in (main, detail):
        for key in observed:
            rows = [line for line in report.splitlines() if line.startswith("- " + key + ":")]
            expect(rows, "terminal %s lost key %s" % (route, key))
    # Observation retention does not decide disposition authority. Record-only failures retain
    # the fixture's independent current disposition; combined store failures revoke it.
    if route in ("analysis", "compute", "tables", "stdout"):
        expect("listed by this report; disposed: fixed (rerun)" in main,
               "record-only terminal route discarded the independent disposition")
    else:
        expect("listed by this report; disposed: fixed (rerun)" not in main,
               "failed disposition authority retained its winner")
    expect("CR9-CAUSAL" not in main + detail + out + err, "exception message leaked")
    expect(tree_manifest(fx.records) == records, "terminal key recovery wrote record inputs")


for _route in CR9_KEY_ROUTES:
    def _cr9_keys(ctx, route=_route):
        cr9_key_case(ctx, route)
    case(9, "CR9-keys-" + _route)(_cr9_keys)


@case(9, "CR9-nonappending-terminal-paths")
def cr9_no_append(ctx):
    # These routes cannot establish or publish history; the alternative to retaining current
    # identities is an explicit no-append result. The combined-history route has its CR8 case.
    for route in ("outgoing", "prepare", "diagnostic"):
        fx, m = cr8_fixture(ctx, "no-append-" + route)
        cr8_control(m, fx, lambda main, detail: expect("carried@old: fixed" in main, "clean history control absent"))
        before = open(os.path.join(fx.tools, "dispositions.jsonl"), "rb").read()
        reached = []
        def fault(r, owner, phase):
            if phase != "after":
                return
            if route == "diagnostic" and r == "store-validate" and owner == ("store", 0, 2):
                raise NameError("enter diagnostic")
            if r == route:
                reached.append(owner)
                raise NameError("CR9-CAUSAL " + route)
        m.boundary_hook, m.test_expected_ledger = fault, None
        code, out, err, main, detail = con_invoke(m, fx, route == "diagnostic")
        expect(code == 1 and len(reached) == 1, "no-append terminal route not exercised")
        expect(open(os.path.join(fx.tools, "dispositions.jsonl"), "rb").read() == before,
               "unavailable history was appended")
        expect("nothing appended" in main.lower() + detail.lower() + out.lower(), "no-append status omitted")
        expect(len(m.test_ledger) == (2 if route == "diagnostic" else 1), "no-append ledger differs")
    print("    C terminal outgoing, prepare and diagnostic paths append no history", flush=True)


def cr9_invalid_case(ctx, route):
    fx, m = cr8_fixture(ctx, "invalid-section-" + route)
    rows = [json.loads(line) for line in open(os.path.join(fx.records, "r.jsonl"))]
    fx.write("r.jsonl", rows + ["not JSON"])
    heading = "## Records holding invalid or undated lines (named in every report)"
    records = cr8_control(m, fx, lambda main, detail: expect(
        any("r.jsonl:11" in line for line in section(detail, heading)), "clean invalid-line control absent"))
    owner = ("anchor", 1, 0) if route == "detail-inventory" else ("record", 1, 11)
    reached = []
    def fault(r, o, phase):
        if r == route and o == owner and phase == "after":
            reached.append(o)
            raise NameError("CR9-CAUSAL invalid section")
    m.boundary_hook, m.test_expected_ledger = fault, None
    code, out, err, main, detail = con_invoke(m, fx)
    expect(code == 0 and reached == [owner] and len(m.test_ledger) == 1, "invalid-section fault differs")
    print("    D CR9-CAUSAL %s reached=1 ledger=1" % route, flush=True)
    invalid = section(detail, heading)
    expect("- none" not in invalid and any("unknown" in line and "unavailable" in line for line in invalid),
           "unavailable invalid-line inventory claimed clean")
    if route == "detail-invalid":
        expect(any("r.jsonl:11" in line for line in invalid), "terminal invalid row lost its physical locator")
    expect(tree_manifest(fx.records) == records, "invalid presentation wrote record inputs")


for _route in ("detail-invalid", "detail-inventory"):
    def _cr9_invalid(ctx, route=_route):
        cr9_invalid_case(ctx, route)
    case(9, "CR9-invalid-" + _route)(_cr9_invalid)


@case(9, "CR9-table-selection")
def cr9_tables(ctx):
    fx, m = cr8_fixture(ctx, "table-selection")
    fx.write("r-waste-table.md", ["contents are not an input"])
    records = cr8_control(m, fx, lambda main, detail: expect(
        "1 linked in the detail" in main and "[r-waste-table.md]" in detail, "clean table selection failed"))
    reached = []
    def fault(route, owner, phase):
        if route == "tables" and phase == "after":
            reached.append(owner)
            raise NameError("CR9-CAUSAL table selection")
    m.boundary_hook, m.test_expected_ledger = fault, None
    code, out, err, main, detail = con_invoke(m, fx)
    expect(code == 0 and len(reached) == len(m.test_ledger) == 1, "selection fault differs")
    print("    D CR9-CAUSAL table selection reached=1 ledger=1", flush=True)
    tables = section(detail, "## Per-run waste tables (linked by path, never read)")
    expect("- none found" not in tables and any("table selection unavailable; 0 rendered" in line for line in tables),
           "failed selection became a definite empty selection")
    expect("0 linked in the detail" in main and "Table selection unknown" in main,
           "main does not distinguish selection availability from rendered count")
    expect(tree_manifest(fx.records) == records, "selection recovery wrote record/table inputs")
    empty, clean = cr8_fixture(ctx, "empty-table-selection")
    cr8_control(clean, empty, lambda main, detail: expect(
        "0 linked in the detail" in main
        and "- none found" in section(detail, "## Per-run waste tables (linked by path, never read)"),
        "genuinely empty successful selection lost its clean result"))


@case(9, "CR9-committed-key-after-kind-failure")
def cr9_committed_key(ctx):
    for phase_to_fail in ("before", "after"):
        fx, m = cr8_fixture(ctx, "committed-key-" + phase_to_fail)
        records = cr8_control(m, fx, lambda main, detail: expect(
            as_map(rows_of(main))[(H, "total")][:2] == ("101 s (1.7 min)", "complete"),
            "clean fixture's 60 + 30 + 11 seconds differ"))
        reached, stores = [], []
        original = m.read_store
        def capture(path):
            value = original(path)
            stores.append(value)
            return value
        def fault(route, owner, phase):
            if route == "store-kind" and owner == ("store", 0, 3) and phase == phase_to_fail and not reached:
                reached.append(owner)
                raise NameError("CR9-CAUSAL kind before publication")
        m.read_store, m.boundary_hook, m.test_expected_ledger = capture, fault, None
        before = open(os.path.join(fx.tools, "dispositions.jsonl"), "rb").read()
        code, out, err, main, detail = con_invoke(m, fx)
        expect(code == 1 and len(reached) == len(m.test_ledger) == 1, "kind fault not reached exactly once")
        print("    D CR9-CAUSAL store-kind %s: reached=1 ledger=1" % phase_to_fail, flush=True)
        expect(any(n == 3 and entry.get("key") == "carried@old" for n, entry in stores[-1].lines),
               "the separately validated entry was not published")
        for report in (main, detail):
            expect(any(line.startswith("- carried@old:") for line in report.splitlines()),
                   "published listed identity was lost after kind extraction failed")
        expect("carried@old: undetermined" in main, "uncertain disposition acquired a winner")
        appended = [json.loads(line) for line in open(os.path.join(fx.tools, "dispositions.jsonl"), "rb").read()[len(before):].splitlines()]
        expect(appended and appended[0]["kind"] == "report", "explicit interval history absent")
        expect(tree_manifest(fx.records) == records, "kind recovery wrote its inputs")


# The original table-link regression and the other terminal families share an independent
# history oracle: the fixture has one earlier disposition and one current rerun disposition.
# Authority expectations below follow the supplier kinds, never the reader's computed result.
CR10_ALL_AUTHORITIES = {"init", "report", "listed", "disposition", "abandoned", "run-ended"}
CR10_HISTORY_ROUTES = [
    ("detail-table", None, set()),
    ("analysis", None, set()), ("compute", None, set()), ("tables", None, set()),
    ("stdout", None, set()), ("outgoing", None, set()),
    ("determinations", None, CR10_ALL_AUTHORITIES),
    ("render", None, CR10_ALL_AUTHORITIES),
    ("encode-main", None, CR10_ALL_AUTHORITIES),
    ("encode-detail", None, CR10_ALL_AUTHORITIES),
    ("encode-stdout", None, CR10_ALL_AUTHORITIES),
    ("main-key", None, CR10_ALL_AUTHORITIES),
    ("main-history", ("store", 0, 4), {"disposition"}),
    ("main-determination", ("store", 0, 5), {"abandoned"}),
    ("store-group", ("store", 0, 5), {"abandoned"}),
    ("store-apply", ("store", 0, 5), {"abandoned"}),
    ("store-blank", ("store", 0, 1), CR10_ALL_AUTHORITIES),
    ("store-decode", ("store", 0, 1), CR10_ALL_AUTHORITIES),
    ("store-kind", ("store", 0, 1), CR10_ALL_AUTHORITIES),
    ("store-validate", ("store", 0, 1), {"init"}),
    ("store-entry", ("store", 0, 1), {"init"}),
    ("store-history", ("store", 0, 2), {"report"}),
    ("store-history", ("store", 0, 3), {"listed"}),
    ("store-history", ("store", 0, 4), {"disposition"}),
    ("sort-store", None, {"abandoned", "run-ended"}),
]
CR10_HISTORY_ROUTES += [(route, None, set()) for route in (
    "record-blank", "record-decode", "record-kind", "record-time", "record-identity",
    "record-metadata", "analysis-final", "analysis-line", "structural", "episode-duration",
    "episode-exit", "episode-review", "episode-denials", "episode-spend",
    "boundary-value", "boundary-refusals", "snapshot-value", "beat-value",
    "main-row-helper-time", "main-gap", "detail-inventory", "detail-open", "detail-run",
    "detail-episode", "detail-view", "detail-group", "detail-review", "detail-boundary",
    "detail-snapshot", "detail-exact", "detail-beat", "spend-session", "sort-key", "sort-gap",
    "sort-view", "sort-idle", "detail-invalid", "detail-history", "detail-gap-2",
    "gap-presentation", "unknown-presentation")]


def cr10_history(ctx, route, target, authorities):
    suffix = route + ("-" + str(target[2]) if target else "")
    fx, m = cr8_fixture(ctx, "history-" + suffix)
    fx.write("r-waste-table.md", ["unchanged table"])
    if route in ("detail-invalid", "main-gap", "sort-gap", "detail-gap-2", "structural"):
        rows = [json.loads(line) for line in open(os.path.join(fx.records, "r.jsonl"))]
        if route in ("main-gap", "detail-gap-2"):
            del rows[4]["idle_min"]
        else:
            rows.append("not JSON")
        fx.write("r.jsonl", rows)
    if route == "detail-history":
        rows = [json.loads(line) for line in open(os.path.join(fx.records, "r.jsonl"))]
        rows[2]["event"] = "spawn"
        fx.write("r.jsonl", rows)
    current = "helper-time@" + SINCE + ".." + UNTIL
    records = cr8_control(m, fx, lambda main, detail: expect(
        current + ": listed by this report; disposed: fixed (rerun)" in main
        and "- carried@old: fixed (earlier)" in main,
        "clean disposition/history positive control absent"))
    store_path = os.path.join(fx.tools, "dispositions.jsonl")
    before = open(store_path, "rb").read()
    for path in records:
        if os.path.isfile(path):
            os.chmod(path, 0o444)
    os.chmod(fx.records, 0o555)
    records = tree_manifest(fx.records)
    # Physical positions are counted from the planted bytes; suppliers come from the fixture's
    # three records, episode chain (gate/open/close/later opening), or named store lines.
    record_sources = tuple(("record", ordinal, n)
                           for ordinal, name in enumerate(("r.jsonl", "s.jsonl", "z.jsonl"), 1)
                           for n in range(1, len(open(os.path.join(fx.records, name), "rb").read().split(b"\n")) + 1))
    r_sources = tuple(source for source in record_sources if source[1] == 1)
    stores = tuple(("store", 0, n) for n in range(1, len(before.split(b"\n")) + 1))
    global_owner = ("global", 0, 0)
    expected_owner, suppliers = global_owner, record_sources
    if target is not None:
        expected_owner, suppliers = target, (target,)
    elif route in ("determinations",):
        suppliers = stores
    elif route in ("render", "encode-main", "encode-detail", "encode-stdout", "main-key", "outgoing"):
        suppliers = record_sources + stores
    elif route == "sort-store":
        suppliers = (("store", 0, 5), ("store", 0, 6))
    elif route in ("record-blank", "record-decode", "record-kind", "record-time", "record-identity"):
        expected_owner = ("record", 1, 1)
        suppliers = (expected_owner,)
    elif route in ("record-metadata", "analysis-final", "detail-inventory"):
        expected_owner, suppliers = ("anchor", 1, 0), r_sources
    elif route in ("analysis-line", "detail-run", "detail-open"):
        expected_owner, suppliers = ("record", 1, 9 if route == "detail-open" else 1), r_sources
    elif route == "spend-session":
        expected_owner, suppliers = ("anchor", 1, 0), (("record", 1, 4), ("record", 1, 6), ("record", 1, 8))
    elif route.startswith("episode-") or route in ("detail-episode", "detail-group", "detail-review", "detail-exact"):
        expected_owner, suppliers = ("record", 1, 3), CON_EP
    elif route in ("boundary-value", "boundary-refusals", "detail-boundary", "detail-gap-2"):
        expected_owner = ("record", 1, 5)
        suppliers = (expected_owner,)
    elif route in ("snapshot-value", "detail-snapshot", "beat-value", "detail-beat", "detail-history",
                   "detail-invalid", "structural"):
        number = (2 if route in ("snapshot-value", "detail-snapshot") else
                  6 if route in ("beat-value", "detail-beat") else 3 if route == "detail-history" else 11)
        expected_owner = ("record", 1, number)
        suppliers = (expected_owner,)
    expected_ledger = [(route, expected_owner, suppliers, "NameError")]
    if route in ("gap-presentation", "unknown-presentation"):
        expected_ledger.insert(0, ("detail-table", global_owner, record_sources, "NameError"))
    prepared, reached = [], []
    original = m.prepare_history
    def history(*args):
        value = original(*args)
        prepared.append((set(m._ACTIVE.authorities), len(value[1])))
        return value
    def fault(r, owner, phase):
        if phase != "after":
            return
        seed = route in ("gap-presentation", "unknown-presentation") and r == "detail-table" and not reached
        selected = r == route and (target is None or owner == target) and not any(x[0] == route for x in reached)
        if seed or selected:
            reached.append((r, owner))
            raise NameError("CR10-CAUSAL history preservation")
    m.prepare_history, m.boundary_hook, m.test_expected_ledger = history, fault, None
    try:
        code, out, err, main, detail = con_invoke(m, fx)
        expected_routes = ["detail-table", route] if route in ("gap-presentation", "unknown-presentation") else [route]
        expect([r for r, owner in reached] == expected_routes and m.test_ledger == expected_ledger,
               "history injection/ledger differs: got %r, want %r" % (m.test_ledger, expected_ledger))
        expect(prepared and prepared[-1] == (authorities, 2),
               "fixture's two historical entries or independent authorities changed: %r" % (prepared,))
        expect(code == (1 if authorities or route == "outgoing" else 0), "history recovery exit differs")
        print("    D CR10-CAUSAL %s reached=%d ledger=%d prepared-history=2 authorities=%s" %
              (suffix, len(reached), len(m.test_ledger), ",".join(sorted(authorities)) or "none"), flush=True)
        expect("key history preparation unavailable" not in main + detail,
               "successful independent history falsely reported unavailable")
        expected_status = "undetermined" if "disposition" in authorities else "disposed: fixed (rerun)"
        if route != "main-key":
            expect(current + ": listed by this report; " + expected_status in main,
                   "prepared current disposition lost or overridden")
        expect("- " + current + ": fixed (rerun)" in main, "independent rerun history entry lost")
        if route == "main-history":
            expect("- carried@old: unknown (history presentation unavailable)" in main,
                   "failed history row silently omitted")
        else:
            expect("- carried@old: fixed (earlier)" in main, "independent earlier history entry lost")
        if route in ("render", "encode-main", "encode-detail"):
            terminal = (main, detail) if route == "render" else (main if route == "encode-main" else detail,)
            for report in terminal:
                expect("- " + current + ": fixed (rerun)" in report and "- carried@old: fixed (earlier)" in report,
                       "terminal emitter discarded successfully prepared history")
        if route == "detail-table":
            expect(prepared == [(set(), 2), (set(), 2)], "CR10-F did not prepare history twice")
            expect(as_map(rows_of(main))[(H, "total")][:2] == ("101 s (1.7 min)", "complete"),
                   "CR10-F lost the independent 60 + 30 + 11 seconds")
            expect("0 linked in the detail" in main and "link presentation unavailable; 0 rendered" in detail,
                   "CR10-F did not retain the local table-link failure")
        after = open(store_path, "rb").read()
        if route == "outgoing":
            expect(before == after and "nothing appended" in out, "outgoing failure appended history")
        else:
            appended = [json.loads(line) for line in after[len(before):].splitlines()]
            listed = [entry["key"] for entry in appended if entry["kind"] == "listed"]
            expect(appended[0]["kind"] == "report" and appended[0]["listed"] == len(listed) and current in listed,
                   "history recovery did not append its final identities")
            for report in (main, detail):
                for key in listed + ["carried@old"]:
                    expect(any(line.startswith("- " + key + ":") for line in report.splitlines()),
                           "history preservation lost observed identity " + key)
        expect("CR10-CAUSAL" not in main + detail + out + err, "exception message leaked")
        expect(tree_manifest(fx.records) == records, "history recovery wrote read-only records/tables")
    finally:
        os.chmod(fx.records, 0o755)
    if route == "detail-table":
        empty = Fx(ctx.root, "history-empty-control", script=ctx.script)
        empty.write("empty.jsonl", [{"event": "run-open", "ts": "2026-10-03T10:00:00+0100"}])
        clean = reader_module(ctx.script, "history_empty")
        result = con_invoke(clean, empty)
        expect(result[0] == 0 and clean.test_ledger == []
               and "Recorded since the previous report:\n\n- none" in result[3],
               "clean empty history lost its zero result")
        print("    C empty history=0 ledger=0; same-run positive history=2; read-only manifest unchanged", flush=True)


for _route, _target, _authorities in CR10_HISTORY_ROUTES:
    def _cr10(ctx, route=_route, target=_target, authorities=_authorities):
        cr10_history(ctx, route, target, authorities)
    _suffix = _route + ("-" + str(_target[2]) if _target else "")
    case(9, "CR10-F" if _route == "detail-table" else "CR10-history-" + _suffix)(_cr10)


def cr10_empty_history(ctx, site):
    fx = Fx(ctx.root, "empty-history-" + site, script=ctx.script)
    fx.write("r.jsonl", [{"event": "run-open", "ts": "2026-10-06T10:00:00+0100"}])
    fx.write("r-waste-table.md", ["unchanged table"])
    m = reader_module(ctx.script, "empty_history_" + site.replace("-", "_"))
    store_path = os.path.join(fx.tools, "dispositions.jsonl")
    initial = open(store_path, "rb").read()
    current = "helper-time@" + SINCE + ".." + UNTIL
    disposition = {"kind": "disposition", "key": current, "disposition": "fixed", "note": "sole history"}
    append_store_lines(fx, [disposition])
    positive = con_invoke(m, fx)
    expect(positive[0] == 0 and m.test_ledger == []
           and "- " + current + ": fixed (sole history)" in positive[3], "non-zero history control absent")
    # Reset only the disposable fixture store, retaining the init bytes, then establish a
    # genuinely empty history. The report it appends supplies the report-kind fault target.
    with open(store_path, "wb") as handle:
        handle.write(initial)
    clean = con_invoke(m, fx)
    expect(clean[0] == 0 and m.test_ledger == []
           and "Recorded since the previous report:\n\n- none" in clean[3], "empty clean control differs")
    if site == "disposition":
        target_number = len(open(store_path, "rb").read().splitlines()) + 1
        append_store_lines(fx, [disposition])
    else:
        target_number = 1 if site == "init" else 2
    before_store = open(store_path, "rb").read()
    for path in tree_manifest(fx.records):
        if os.path.isfile(path):
            os.chmod(path, 0o444)
    os.chmod(fx.records, 0o555)
    before_records = tree_manifest(fx.records)
    route = "detail-table" if site == "record" else "store-entry" if site in ("init", "report", "disposition") else site
    owner = ("store", 0, target_number) if route == "store-entry" else ("global", 0, 0)
    record_sources = (("record", 1, 1), ("record", 1, 2))
    store_sources = tuple(("store", 0, n) for n in range(1, len(before_store.split(b"\n")) + 1))
    suppliers = (owner,) if route == "store-entry" else record_sources if site == "record" else record_sources + store_sources
    authorities = set() if site == "record" else {site} if route == "store-entry" else CR10_ALL_AUTHORITIES
    prepared, reached = [], []
    original = m.prepare_history
    def history(*args):
        value = original(*args)
        prepared.append((set(m._ACTIVE.authorities), len(value[1])))
        return value
    def fault(r, o, phase):
        if r == route and o == owner and phase == "after" and not reached:
            reached.append(o)
            raise NameError("CR10-CAUSAL empty history")
    m.prepare_history, m.boundary_hook, m.test_expected_ledger = history, fault, None
    try:
        code, out, err, main, detail = con_invoke(m, fx)
        expect(reached == [owner] and m.test_ledger == [(route, owner, suppliers, "NameError")],
               "empty-history injection/ledger differs")
        expect(prepared and prepared[-1] == (authorities, 0), "empty history was not prepared successfully")
        expect(code == (0 if site == "record" else 1), "empty-history exit differs")
        print("    D CR10-CAUSAL empty-%s reached=1 ledger=1 prepared-history=0; clean=0 positive=1" % site, flush=True)
        expect("key history preparation unavailable" not in main + detail, "prepared empty history claimed unavailable")
        expected = ("- none" if site in ("record", "init") else
                    "- unknown: no complete since-previous disposition history")
        expect(expected in section(main, "## Dispositions"), "empty history confused uncertainty with a known zero")
        if site in ("render", "encode-detail"):
            expect(expected in section(detail, "## Dispositions"), "terminal detail lost empty-history authority")
        if site == "disposition":
            expect(current + ": listed by this report; undetermined" in main
                   and "fixed (sole history)" not in main + detail, "lost disposition retained its winner")
        after_store = open(store_path, "rb").read()
        appended = [json.loads(line) for line in after_store[len(before_store):].splitlines()]
        expect(appended and appended[0]["kind"] == "report"
               and appended[0]["listed"] == sum(line["kind"] == "listed" for line in appended),
               "empty-history report/listed batch differs")
        expect(tree_manifest(fx.records) == before_records, "empty-history recovery wrote read-only inputs")
        expect("CR10-CAUSAL" not in main + detail + out + err, "exception text leaked")
    finally:
        os.chmod(fx.records, 0o755)


for _site in ("record", "init", "report", "disposition", "render", "encode-main", "encode-detail", "encode-stdout"):
    def _cr10_empty(ctx, site=_site):
        cr10_empty_history(ctx, site)
    case(9, "CR10-empty-" + _site)(_cr10_empty)


# ------------------------------------------------------------------------ main -------------

class Ctx(object):
    def __init__(self, root, script):
        self.root, self.script, self.sensitivity = root, script, None
        self.mutation_logs = None


def main(argv):
    script = SCRIPT
    mutation_logs = None
    run_mutants = False
    if argv[:1] == ["--mutants"]:
        run_mutants, argv = True, argv[1:]
    if argv[:1] == ["--mutation-logs"]:
        if len(argv) < 2 or not os.path.isdir(argv[1]):
            print("PROBE FAILED: --mutation-logs needs an existing directory")
            return 2
        mutation_logs, argv = os.path.abspath(argv[1]), argv[2:]
    if argv[:1] == ["--script"]:
        script, argv = os.path.abspath(argv[1]), argv[2:]
    names = [c[0] for c in CASES]
    for flag, store in (("--b17", B17_CASES), ("--route", ROUTE_CASES), ("--cr4-finding", CR4_CASES),
                        ("--cr3-finding", CR3_CASES), ("--finding", FINDING_CASES), ("--cr1-finding", CR1_CASES),
                        ("--cr5-finding", CR5_CASES), ("--cr6-finding", CR6_CASES), ("--cr6-family", CR6_FAMILIES)):
        if argv[:1] == [flag]:
            if len(argv) < 2 or not argv[1].isdigit() or int(argv[1]) not in store:
                sys.stderr.write("%s takes one of %s\n" % (flag, sorted(store)))
                return 2
            argv = store[int(argv[1])] + argv[2:]
    for a in argv:
        if a not in names:
            sys.stderr.write("unknown case %r; the cases are:\n  %s\n" % (a, "\n  ".join(names)))
            return 2
    selected = [c for c in CASES if not argv or c[0] in argv]
    if not argv and not run_mutants and mutation_logs is None:
        left_out = [c[0] for c in selected if c[0].endswith("restored-defects-fail-acceptance")]
        if len(left_out) != 1:
            print("PROBE FAILED: %d cases name the mutant acceptance leg, 1 expected" % len(left_out))
            return 2
        selected = [c for c in selected if c[0] != left_out[0]]
        print("left out: %s (run it with --mutants; it takes hours)" % left_out[0], flush=True)
    os.environ["TZ"] = TZ
    time.tzset()
    root = tempfile.mkdtemp(prefix="ww-suite-")
    ctx = Ctx(root, script)
    ctx.mutation_logs = mutation_logs
    print("suite: %d of %d cases · script %s · fixtures %s" % (len(selected), len(CASES), script, root), flush=True)
    failed = 0
    t0 = time.time()
    try:
        for name, test, fn in selected:
            t = time.time()
            try:
                fn(ctx)
                print("ok   %-58s %6.2f s" % (name, time.time() - t), flush=True)
            except Exception as exc:
                failed += 1
                print("FAIL %-58s %6.2f s · %s" % (name, time.time() - t, str(exc)[:600]), flush=True)
        if ctx.sensitivity:
            print("sensitivity leg:")
            for line in ctx.sensitivity:
                print("  " + line)
    finally:
        for base, dirs, files in os.walk(root):
            for d in dirs:
                try:
                    os.chmod(os.path.join(base, d), 0o755)
                except OSError:
                    pass
        shutil.rmtree(root, ignore_errors=True)
    print("runtime %.1f s" % (time.time() - t0))
    n = len(selected)
    print("PASS %d/%d" % (n, n) if not failed else "FAIL %d/%d" % (failed, n))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
