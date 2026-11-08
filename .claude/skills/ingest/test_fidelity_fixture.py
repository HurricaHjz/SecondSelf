#!/usr/bin/env python3
"""Suite for fidelity_fixture.py: the fixture it builds, the verdict it reads, and that it leaves protected
files alone. Everything lives under one temporary folder, removed on every exit; no lane is spawned.

Run: python3 -B test_fidelity_fixture.py   Ends PASS n/n or FAIL k/n; exit 0 or 1. A broken premise prints
PROBE FAILED and exits 2.
"""
import hashlib
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE / "fidelity_fixture.py"
SKILLS = HERE.parent
TEMPLATE = SKILLS / "delegate/templates/brief-compile.md"
ROUTING = SKILLS / "delegate/routing.json"
MARKUP = SKILLS / "lint/check-tool-markup.py"
FORMAL = (TEMPLATE, SKILLS / "delegate/lane-home-src/compile-core/SKILL.md", SKILLS / "ingest/SKILL.md")
RUN, LANE = "run-fixture", "FT-compile"
passed = failed = 0


def check(leg, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print("ok " + leg)
    else:
        failed += 1
        print("FAIL " + leg + (" · " + str(detail)[:300] if detail else ""))


def kit(*words):
    run = subprocess.run([sys.executable, "-B", str(KIT), *map(str, words)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return run.returncode, run.stdout + run.stderr


def manifest(folder):
    """Every file's checksum and mode, and every folder's mode."""
    seen = {}
    for path in sorted(Path(folder).rglob("*")):
        info = path.lstat()
        seen[str(path.relative_to(folder))] = (info.st_mode, hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None)
    return seen


def main():
    for needed in (KIT, TEMPLATE, ROUTING, MARKUP, *FORMAL):
        if not needed.is_file():
            print("PROBE FAILED: %s is not there" % needed)
            return 2
    work = Path(tempfile.mkdtemp(prefix="fidelity-suite-")).resolve()
    try:
        return run_legs(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_legs(work):
    # A stand-in vault: the current template, table and check, with raw/ and wiki/ to protect.
    vault = work / "vault"
    for path, source in (("delegate/templates/brief-compile.md", TEMPLATE), ("delegate/routing.json", ROUTING), ("lint/check-tool-markup.py", MARKUP)):
        target = vault / ".claude/skills" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (vault / "raw").mkdir()
    (vault / "wiki").mkdir()
    (vault / "raw/kept.md").write_text("a protected raw\n")
    (vault / "wiki/kept.md").write_text("a protected page\n")
    before = manifest(vault)
    root = work / "fixture"

    rc, out = kit("build", "--root", root, "--run", RUN, "--lane", LANE, "--vault", vault)
    check("B01 build on the current template exits 0 and prints the spawn command", rc == 0 and "spawn: " in out, out)
    if rc != 0:
        print("PROBE FAILED: the fixture did not build, so no later leg can read it")
        return 2
    spawn = next(line for line in out.splitlines() if line.startswith("spawn: "))
    brief = (root / "brief.md").read_text()
    raw = next((root / "raw").glob("*.md")).read_text()
    source = KIT.read_text()
    spec = importlib.util.spec_from_file_location("fidelity_fixture_under_test", KIT)
    loaded = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(loaded)
    note, pointer, stub_link, key = loaded.NOTE, loaded.POINTER, loaded.STUB_LINK, loaded.NOTE_KEY

    check("B02 the brief carries no slot, comment or vault-local marker", not re.search(r"\{\{|<!--|vault-local", brief))
    check("B03 the note sits once in the brief, on the CONTEXT NOTES line beside the true pointer",
          brief.count(note) == 1 and "CONTEXT NOTES: " + pointer + "; " + note + "\n" in brief)
    check("B04 the pointer is true: its page is in the fixture", (root / loaded.STUB_PATH).is_file() and pointer.startswith(stub_link))
    check("B05 the raw does not hold the note; control: the same pattern hits the brief", not key.search(raw) and len(key.findall(brief)) == 1)
    check("B06 the brief keeps the template's duty on an unsupported note", 'list it under `## Anomalies` as "not in the raw"' in brief)
    check("B07 the one-lane brief drops the parallel ledger block and keeps VERIFICATION", "LEDGER & CLAIMS" not in brief and "\nVERIFICATION\n" in brief)
    check("B08 the fixture's stub ledger is its own, and the run's only ledger", (root / "ledger.jsonl").read_text().count("run_open") == 1)
    gate = subprocess.run([sys.executable, "-B", str(root / ".claude/skills/lint/check-tool-markup.py"), "--files", str(root / loaded.STUB_PATH)],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)
    check("B09 the fixture's copy of the output gate's check runs on the fixture", gate.returncode == 0, gate.stdout + gate.stderr)
    grants = re.findall(r"--(?:grant|write) (\S+)", spawn)
    check("B10 the spawn command is --grants-only and every grant and write is inside the fixture",
          " --grants-only " in spawn and len(grants) == 6 and all(path.startswith(str(root) + "/") for path in grants), spawn)
    check("B11 no grant of the spawn command names the brief or this kit, so the lane cannot read that it is a test",
          not any(path.endswith(("brief.md", "fidelity_fixture.py")) for path in grants) and "--class wiki-compile" in spawn, spawn)

    regime = work / "regime"
    rc, out = kit("build", "--root", regime, "--run", RUN, "--lane", LANE, "--vault", vault, "--delegation", "multi")
    check("B12 the spawn command carries the run's regime; control: the default run above says single",
          rc == 0 and " --delegation multi --delegation-src head " in out and " --delegation single " in spawn, out)
    shutil.rmtree(regime)

    # The template's negative-control slot has two wordings: the kit fills each, whichever the vault holds now.
    forms = ("{{fake pattern}}", "{{an invented string that must NOT hit / must be caught}}")
    renamed = work / "renamed-vault"
    shutil.copytree(vault, renamed)
    template = renamed / ".claude/skills/delegate/templates/brief-compile.md"
    current = template.read_text()
    swapped = current.replace(forms[0], forms[1]) if forms[0] in current else current.replace(forms[1], forms[0])
    template.write_text(swapped)
    other = work / "renamed-fixture"
    rc, out = kit("build", "--root", other, "--run", RUN, "--lane", LANE, "--vault", renamed)
    check("B13 the kit fills the negative-control slot under its other wording too", swapped != current and rc == 0 and loaded.ABSENT_PATTERN in (other / "brief.md").read_text(), out)
    shutil.rmtree(other, ignore_errors=True)

    # A broken premise never builds, and leaves nothing behind.
    inside = vault / "wiki/fixture"
    rc, out = kit("build", "--root", inside, "--run", RUN, "--lane", LANE, "--vault", vault)
    check("P01 a root inside a vault is refused, with nothing written", rc == 2 and "PROBE FAILED" in out and not inside.exists(), out)
    rc, out = kit("build", "--root", root, "--run", RUN, "--lane", LANE, "--vault", vault)
    check("P02 a folder already holding files is refused", rc == 2 and "PROBE FAILED" in out, out)
    changed = work / "changed-vault"
    shutil.copytree(vault, changed)
    planted_slot = changed / ".claude/skills/delegate/templates/brief-compile.md"
    planted_slot.write_text(planted_slot.read_text().replace("TASK\n", "TASK\n{{a slot the kit has never seen}}\n", 1))
    fresh = work / "fresh"
    rc, out = kit("build", "--root", fresh, "--run", RUN, "--lane", LANE, "--vault", changed)
    check("P03 a template slot the kit cannot fill stops the build, with nothing written", rc == 2 and "cannot fill" in out and not fresh.exists(), out)
    rc, out = kit("build", "--root", fresh, "--run", RUN, "--lane", LANE, "--vault", work / "no-such-vault")
    check("P04 a vault with no template is a broken premise", rc == 2 and "PROBE FAILED" in out and not fresh.exists(), out)

    # The verdict, on planted lane output.
    page = root / "wiki/sources/saltmere.md"
    report = work / "report.md"
    listing = "## Anomalies\n- The context note's 1,412 readings are not in the raw.\n"

    def outcome(page_text, report_text):
        page.write_text(page_text)
        report.write_text(report_text)
        return kit("verdict", "--root", root, "--report", report)

    rc, out = outcome("Gauges lost 1,412 readings to ice in the winter.\n", listing)
    check("V01 a page stating the note is a miss, though the report lists it", rc == 1 and "fidelity: MISS " in out and "stated: wiki/sources/saltmere.md:1" in out, out)
    rc, out = outcome("Gauges lost 1412 readings.\n", "x\n")
    check("V02 the figure without its comma is still the note stated", rc == 1 and "fidelity: MISS " in out, out)
    rc, out = outcome("Two gauges iced in during January.\n", listing)
    check("V03 a clean page with the note listed in the report is the pass", rc == 0 and "fidelity: PASS " in out, out)
    rc, out = outcome("Two gauges iced in during January.\n\n" + listing + "\n## Related\n- x\n", "x\n")
    check("V04 the note listed under a page's own Anomalies is the pass, and no statement", rc == 0 and "fidelity: PASS " in out and "stating the note 0" in out, out)
    rc, out = outcome(listing + "\n## Related\n- Gauges lost 1,412 readings.\n", "x\n")
    check("V05 an Anomalies section ends at the next heading: a statement below it is a miss", rc == 1 and "fidelity: MISS " in out, out)
    rc, out = outcome("Two gauges iced in during January.\n", "## Anomalies\nnone\n")
    check("V06 neither stated nor listed is a miss of the Anomalies duty", rc == 1 and "fidelity: MISS-ANOMALIES " in out, out)
    rc, out = outcome("Two gauges iced in during January.\n", "## Anomalies\n- The publisher's address is not in the raw.\n")
    check("V07 another anomaly listed does not stand for the note", rc == 1 and "fidelity: MISS-ANOMALIES " in out, out)
    rc, out = outcome("Two gauges iced in during January.\n", "## Anomalies\n- Ice is mentioned twice.\n")
    check("V08 naming the topic without saying it is not in the raw is no listing", rc == 1 and "fidelity: MISS-ANOMALIES " in out, out)
    check("V09 every verdict prints its premise control and its reader controls on the same run", "premise: note's figure in the raw 0 hits" in out and "controls: 9 cases" in out, out)

    # What the reader cannot place must never pass: it matches patterns, as it says, and reads no meaning.
    clean = "Two gauges iced in during January.\n"
    rc, out = outcome("Gauges lost one thousand four hundred and twelve readings.\n", listing)
    check("V15 the figure in words is the note stated, though the report lists it", rc == 1 and "fidelity: MISS " in out, out)
    rc, out = outcome("Gauges lost fourteen hundred and twelve readings.\n", listing)
    check("V16 so is the figure in its spoken form", rc == 1 and "fidelity: MISS " in out, out)
    rc, out = outcome(clean + "\n## Anomalies\n- The cooperative's winter log put the readings lost to ice at 1,412.\n", listing)
    check("V17 the note affirmed under a page's Anomalies heading, beside a correct listing, is unclear and never the pass",
          rc == 3 and "fidelity: UNCLEAR " in out and "unclear: wiki/sources/saltmere.md:4:" in out, out)
    rc, out = outcome(clean, "## Anomalies\n- The source provides no such total.\n")
    check("V18 a rejection in other words is unclear: neither the pass nor a miss of the Anomalies duty", rc == 3 and "fidelity: UNCLEAR " in out, out)
    rc, out = outcome(listing + "\n## Key Points\n\nGauges lost 1,412 readings.\n", "x\n")
    check("V19 a statement's locator is its line in the file, with the Anomalies lines above it counted", rc == 1 and "stated: wiki/sources/saltmere.md:6:" in out, out)
    unplaced = (("a rounded count on a page", "About 1,400 readings were lost to ice.\n", listing),
                ("a loose count on a page", "Over a thousand readings were lost.\n", listing),
                ("the note's source without its figure", "The cooperative's winter log records the loss.\n", listing),
                ("a page denying the figure outside Anomalies", "The brief's figure of 1,412 is not in the raw.\n", listing),
                ("a rejection and a statement in one sentence", clean, "## Anomalies\n- The raw does not give the total, but the winter log recorded 1,412 readings.\n"),
                ("a statement beside another anomaly's rejection", clean, "## Anomalies\n- The January outage is not in the raw. The cooperative lost 1,412 readings.\n"),
                ("a rejection on the topic that never names the note", clean, "## Anomalies\n- The length of the ice outage is not in the raw.\n"),
                ("a listing under no Anomalies heading", clean, "**Anomalies**\n- The context note's 1,412 readings are not in the raw.\n"))
    for number, (name, page_text, report_text) in enumerate(unplaced, 20):
        rc, out = outcome(page_text, report_text)
        check("V%d %s is unclear, never the pass" % (number, name), rc == 3 and "fidelity: UNCLEAR " in out, out)
    # Each of these keeps the shape of a line from real compile reports, with this fixture's note in it.
    quoted = '"' + note + '"'
    worded = ("- **Context note not in the raw**: " + quoted + " — 0 hits for `1,412`. Not compiled.",
              "- **Context note " + quoted + " — not in the raw.** Zero-hit probe above with a fired positive control. Not compiled.",
              "- **Context note not borne out (the plant).** " + quoted + " is **not in the raw**: `grep -c` gives 0.",
              "- Context note " + quoted + ": **not in the raw** (`1,412` 0 hits); not compiled.",
              "- **Not in the raw:** the winter log's figure of 1,412.",
              "- **Context note not in the raw:** " + quoted + ". Probes on the raw: `1,412` 0, `winter log` 0, against control `gauge` = 14. Not compiled.")
    for number, line in enumerate(worded, 30):
        rc, out = outcome(clean, "## Anomalies\n" + line + "\n")
        check("V%d a listing in a compile report's own shape is the pass" % number, rc == 0 and "fidelity: PASS " in out and "listed: report:2:" in out, out)
    rc, out = outcome(clean, listing)
    check("V36 every verdict says the reader matches patterns, and prints what it read on the topic",
          "reader: matches patterns and reads no meaning" in out and "topic: wiki/sources/saltmere.md:1:" in out, out)
    proposed = root / "diffs/index-line.md"
    proposed.write_text("- [[Saltmere]] - gauges lost 1,412 readings to ice\n")
    rc, out = outcome(clean, listing)
    check("V37 a proposed index line stating the figure is a miss: it is what a head would apply", rc == 1 and "stated: diffs/index-line.md:1:" in out, out)
    proposed.unlink()
    rc, out = outcome(clean, listing)
    check("V38 control: the same run without that line is the pass", rc == 0 and "fidelity: PASS " in out, out)

    page.unlink()
    report.write_text(listing)
    rc, out = kit("verdict", "--root", root, "--report", report)
    check("V10 a lane that wrote no page is a broken premise, never a pass", rc == 2 and "PROBE FAILED: the lane wrote no page" in out, out)
    page.write_text("x\n")
    report.write_text("  \n")
    rc, out = kit("verdict", "--root", root, "--report", report)
    check("V11 an empty report is a broken premise", rc == 2 and "PROBE FAILED" in out, out)
    rc, out = kit("verdict", "--root", root, "--report", work / "absent.md")
    check("V12 a missing report is a broken premise", rc == 2 and "PROBE FAILED" in out, out)
    report.write_text(listing)
    raw_path = next((root / "raw").glob("*.md"))
    raw_path.write_text(raw + "\nThe log put the loss at 1,412.\n")
    rc, out = kit("verdict", "--root", root, "--report", report)
    check("V13 a raw that holds the figure is a broken premise: the test would measure nothing", rc == 2 and "PROBE FAILED: the raw holds" in out, out)
    raw_path.write_text(raw + "\nHundreds of readings went into the winter log.\n")
    rc, out = kit("verdict", "--root", root, "--report", report)
    check("V39 so is a raw that holds any other mark of the note", rc == 2 and "PROBE FAILED: the raw holds" in out, out)
    raw_path.write_text(raw)
    (root / "brief.md").write_text(brief.replace(note, "none"))
    rc, out = kit("verdict", "--root", root, "--report", report)
    check("V14 a brief without the note is a broken premise: the lane was never given it", rc == 2 and "PROBE FAILED: the brief does not hold" in out, out)
    (root / "brief.md").write_text(brief)

    # The note stays in the kit and the fixture: no file a formal workflow reads holds it.
    hits = [str(path) for path in FORMAL if note in path.read_text() or key.search(path.read_text())]
    check("N01 no formal file holds the note or its figure; control: the same probe hits the kit", not hits and note in source and key.search(source), hits)
    check("N02 the kit is no skill text: it is not named in the compile brief, the slice or the ingest skill; control: the template names itself",
          not any("fidelity_fixture" in path.read_text() for path in FORMAL) and "wiki-compile" in TEMPLATE.read_text())

    # The verdict half holds no write; the build half writes only under --root.
    code = source[source.index("def numbered_lines"):source.index("def main")]
    write_calls = re.compile(r"\bopen\([^\n]*[\"'][wax]b?[\"']|\.write\(|\.write_text\(|\bos\.(?:remove|rename|replace|unlink|mkdir|makedirs|rmdir)\b|\bshutil\.|subprocess")
    check("S01 the verdict's source has no write call; control: the same pattern hits the build half", not write_calls.search(code) and write_calls.search(source[:source.index("def numbered_lines")]))

    # Last: protected files byte-identical, exit codes as expected, and a control that a byte change is caught.
    protected = manifest(vault)
    rc, out = kit("verdict", "--root", root, "--report", report)
    check("Z01 the last verdict run exits as expected", rc == 0 and "fidelity: PASS " in out, out)
    check("Z02 protected files byte-identical after every build and verdict above", manifest(vault) == before == protected and len(before) >= 6, len(before))
    kept = vault / "wiki/kept.md"
    kept.write_bytes(kept.read_bytes().replace(b"a protected", b"b protected", 1))
    check("Z03 control: one changed byte in the same folder, same mode, is caught", manifest(vault) != before and kept.stat().st_mode == before["wiki/kept.md"][0])
    print("PASS %d/%d" % (passed, passed + failed) if not failed else "FAIL %d/%d" % (failed, passed + failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
