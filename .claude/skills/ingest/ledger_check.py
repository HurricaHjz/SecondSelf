#!/usr/bin/env python3
"""ledger_check.py - the mechanical check on an ingest run ledger's self-reported clock and
configuration. Compare the ledger with independent clocks and the written model/effort slots
(known-issues 2026-09-01); a prose mandate alone does not establish either claim.

Checks:
  future-ts  an event's `ts` later than the wall clock now, later than the ledger file's mtime (no
             line can be written after the file last changed), or later than the `ts` of a line
             appended after it by more than ORDER_TOLERANCE
  config     a `model` or `effort` string on lane L's event that is not the model/effort slot on
             the first line of L's brief (brief-compile: copy the slots verbatim or omit the field)
A lane's brief: `--brief LANE=PATH` (repeatable), else a `brief` field on its lane_open event.

Usage:
  python3 ledger_check.py <ledger.jsonl | run-id> [--brief LANE=PATH ...] [--no-config]
A bare run id resolves to ~/.llm-wiki/ingest-runs/<run-id>.jsonl.
Output: OFFENCE and UNCHECKED lines, then a summary line and a controls line.
Exit 0 = every event checked, no offence; 1 = offences; 2 = PROBE FAILED (ledger unreadable or
without events, a planted control not caught, or no offence but something left unchecked: a
malformed line, an absent or unparseable ts, a lane carrying config with no usable brief).
Reads only: it creates, modifies, moves and deletes nothing.
"""
import argparse, datetime, json, os, re, sys

# An honest stamp never postdates the clock or the file's mtime (`date +%FT%R%z` truncates to the
# minute, downward); this headroom is set by judgement, unmeasured.
CLOCK_TOLERANCE = datetime.timedelta(seconds=60)
# Five minutes allows the one-minute timestamp granularity plus scheduling headroom;
# set by judgement, unmeasured for a new workload. Compare written timestamps, not mtimes.
ORDER_TOLERANCE = datetime.timedelta(minutes=5)
TS = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-]\d{2}:?\d{2})$")
SLOT = {k: re.compile(r"(?:^|[\s·,;(])" + k + r"\s+([^\s·,;]+)") for k in ("model", "effort")}
RUNS_DIR = os.path.join(os.path.expanduser("~"), ".llm-wiki", "ingest-runs")


def parse_ts(s):
    m = TS.match(s) if isinstance(s, str) else None
    if not m:
        return None
    y, mo, d, h, mi, se, off = m.groups()
    if off == "Z":
        tz = datetime.timezone.utc
    else:
        o = off[1:].replace(":", "")
        tz = datetime.timezone((1 if off[0] == "+" else -1) * datetime.timedelta(hours=int(o[:2]), minutes=int(o[2:])))
    try:
        return datetime.datetime(int(y), int(mo), int(d), int(h), int(mi), int(se or 0), tzinfo=tz)
    except ValueError:
        return None


def brief_slots(path):
    """(slots, problem) from the brief's first line - its first paragraph, as the template wraps it."""
    try:
        with open(os.path.expanduser(path), encoding="utf-8", errors="replace") as fh:
            text = fh.read(8192)
    except OSError as e:
        return {}, f"brief unreadable ({e})"
    para = []
    for line in text.splitlines():
        if not line.strip():
            if para:
                break
            continue
        para.append(line.strip())
    first = " ".join(para)
    slots = {}
    for k, rx in SLOT.items():
        m = rx.search(first)
        if m:
            v = m.group(1).rstrip(".,;:)—")
            if v and "{{" not in v:
                slots[k] = v
    return (slots, None) if slots else ({}, "brief first line carries no filled model/effort slot")


def mins(td):
    return int(td.total_seconds() // 60)


def future_reasons(ts, now, mtime, later_min):
    out = []
    if ts > now + CLOCK_TOLERANCE:
        out.append(f"{mins(ts - now)} min after the wall clock now")
    if ts > mtime + CLOCK_TOLERANCE:
        out.append(f"{mins(ts - mtime)} min after the ledger's last modification")
    if later_min is not None and ts - later_min[0] > ORDER_TOLERANCE:
        out.append(f"{mins(ts - later_min[0])} min after line {later_min[1]}, appended later")
    return out


def config_reasons(ev, slots):
    out = []
    for k in ("model", "effort"):
        v = ev.get(k)
        if v is None:
            continue
        if k not in slots:
            out.append(f'{k} "{v}" but the brief first line has no {k} slot')
        elif str(v) != slots[k]:
            out.append(f'{k} "{v}" absent from the brief first line ({k} slot "{slots[k]}")')
    return out


def controls():
    """Planted cases through the same functions: each must fire, and the clean case must not."""
    now = datetime.datetime.now(datetime.timezone.utc)
    day, hour = datetime.timedelta(days=1), datetime.timedelta(hours=1)
    bad = []
    if not future_reasons(now + day, now, now + 2 * day, None):
        bad.append("future ts vs the clock")
    if not future_reasons(now - day, now, now - 2 * day, None):
        bad.append("ts vs the mtime")
    if not future_reasons(now, now + day, now + day, (now - hour, 2)):
        bad.append("ts vs a later line")
    if not config_reasons({"effort": "standard"}, {"model": "opus", "effort": "max"}):
        bad.append("config mismatch")
    if config_reasons({"model": "opus", "effort": "max"}, {"model": "opus", "effort": "max"}):
        bad.append("clean config flagged")
    if parse_ts("2026-09-01T11:24+0100") is None or parse_ts("2026-09-01T11:24") is not None:
        bad.append("ts parser")
    return bad


def fail(msg):
    print(f"PROBE FAILED: {msg}")
    sys.exit(2)


def resolve(arg):
    if os.path.exists(arg) or os.sep in arg:
        return arg
    name = arg if arg.endswith(".jsonl") else arg + ".jsonl"
    return os.path.join(RUNS_DIR, name if name.startswith("run-") else "run-" + name)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check an ingest run ledger for future-dated ts and model/effort "
                                             "strings absent from each lane's brief first line. Reads only.")
    ap.add_argument("ledger", help="a ledger path, or a run id under ~/.llm-wiki/ingest-runs/")
    ap.add_argument("--brief", action="append", default=[], metavar="LANE=PATH", help="a lane's brief (repeatable)")
    ap.add_argument("--no-config", action="store_true", help="skip the config check; the summary says so")
    a = ap.parse_args(argv)
    bad = controls()
    if bad:
        fail("planted control not caught: " + ", ".join(bad))
    briefs = {}
    for spec in a.brief:
        lane, sep, p = spec.partition("=")
        if not (sep and lane and p):
            fail(f"--brief wants LANE=PATH, got {spec!r}")
        briefs[lane] = p
    path = resolve(a.ledger)
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        st = os.stat(path)   # after the read: a line appended meanwhile can only move mtime later
    except OSError as e:
        fail(f"ledger unreadable: {e}")
    now = datetime.datetime.now(datetime.timezone.utc)
    mtime = datetime.datetime.fromtimestamp(st.st_mtime, datetime.timezone.utc)
    events, malformed = [], []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            ev = None
        (events.append((i, ev)) if isinstance(ev, dict) else malformed.append(i))
    if not events:
        fail(f"no parseable event in {path} ({len(malformed)} malformed lines)")
    for i, ev in events:
        if ev.get("event") == "lane_open" and isinstance(ev.get("brief"), str) and ev.get("lane") not in briefs:
            briefs[ev.get("lane")] = ev["brief"]

    offences, unchecked, later_min, ts_checked = {}, [], None, 0
    for i, ev in reversed(events):
        ts = parse_ts(ev.get("ts"))
        if ts is None:
            unchecked.append((i, "ts absent" if "ts" not in ev else f"ts {ev.get('ts')!r} unparseable or without a UTC offset"))
            continue
        ts_checked += 1
        why = future_reasons(ts, now, mtime, later_min)
        if why:
            offences.setdefault(i, [ev, []])[1].append(f"future-ts: ts {ev['ts']} is " + "; ".join(why))
        if later_min is None or ts < later_min[0]:
            later_min = (ts, i)

    cache, lane_problem, cfg_checked, cfg_lanes = {}, {}, 0, set()
    if not a.no_config:
        for i, ev in events:
            if ev.get("model") is None and ev.get("effort") is None:
                continue
            lane = ev.get("lane") or "(no lane)"
            if lane not in briefs:
                lane_problem.setdefault(lane, "no brief named (pass --brief LANE=PATH)")
                continue
            slots, problem = cache.setdefault(lane, brief_slots(briefs[lane]))
            if problem:
                lane_problem.setdefault(lane, f"{problem}: {briefs[lane]}")
                continue
            cfg_checked += 1
            cfg_lanes.add(lane)
            why = config_reasons(ev, slots)
            if why:
                offences.setdefault(i, [ev, []])[1].append(f"config: lane {lane} " + "; ".join(why))

    for i in sorted(offences):
        ev, why = offences[i]
        print(f"OFFENCE line {i} " + " | ".join(why) + " | " + json.dumps(ev, ensure_ascii=False)[:300])
    for i in malformed:
        print(f"UNCHECKED line {i} malformed JSON")
    for i, why in sorted(unchecked):
        print(f"UNCHECKED line {i} {why}")
    for lane, why in sorted(lane_problem.items()):
        print(f"UNCHECKED lane {lane} config: {why}")
    n_future = sum(1 for _ev, why in offences.values() for w in why if w.startswith("future-ts"))
    n_config = sum(1 for _ev, why in offences.values() for w in why if w.startswith("config"))
    cfg = "skipped (--no-config)" if a.no_config else f"{cfg_checked} events over {len(cfg_lanes)} lanes checked"
    print(f"summary: {os.path.basename(path)} · events {len(events)} · malformed {len(malformed)} · ts checked {ts_checked}"
          f" · future-ts offences {n_future} · config {cfg} · config offences {n_config}"
          f" · unchecked ts {len(unchecked)} · unchecked config lanes {len(lane_problem)}")
    print("controls: planted future ts (clock, mtime, later line) and config mismatch caught; clean config not flagged; ts parser ok")
    if offences:
        sys.exit(1)
    left = len(malformed) + len(unchecked) + len(lane_problem)
    if left:
        fail(f"no offence, but {left} items unchecked (listed above) - the ledger is not proven clean")


if __name__ == "__main__":
    main()
