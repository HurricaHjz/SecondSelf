#!/usr/bin/env python3
"""Executed old-build counterexamples, on a supplied isolated copy only."""
import argparse
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True)
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args()
    root, build = Path(args.fixture), Path(args.build)
    sys.path.insert(0, str(build / "skills/adopt"))
    import adopt_register as reg
    import adopt_manifest as manifest
    import adopt_kinds as kinds
    os.environ["AIMYTH_ADOPT_LOCKS"] = str(root / "locks")
    skeleton = build / "skills/adopt/templates/register-skeleton.md"
    source = skeleton.read_text()
    ghost = "\n  ## User-level skills\n\n| **Name** | Level | Carrier | Pin · publisher | Acceptance | Bump | Route | State | Record |\n|---|---|---|---|---|---|---|---|---|\n| `ghost` | auto | symlink | 1.0.0 · x | listed | fetch | ghost work: use directly | active | x |\n"
    seed = root / "ghost-seed.md"
    seed.write_text(source + ghost)
    target = root / "ghost-register.md"
    rc = reg.seed(str(target), "2025-01-01", str(seed), True, out=lambda x: None)
    parsed = reg.parse(target.read_text())
    ghost_missing = not reg.live_rows(parsed, "skills", "ghost")
    result = {"H1": {"old_exit": rc, "ghost_bytes_written": ghost in target.read_text(),
                      "ghost_unaccounted": ghost_missing}}
    control = root / "plain-register.md"
    result["H1"]["control_exit"] = reg.seed(str(control), "2025-01-01", str(skeleton), True, out=lambda x: None)
    path_a, path_b = root / "alpha", root / "beta-absent"
    path_a.write_text("fixture binary")
    path_a.chmod(0o755)
    columns = reg.TABLES["cli"]["columns"]
    for rid, path in (("alpha", path_a), ("beta", path_b)):
        values = {"Tool": rid, "Name": rid, "Level": "auto", "Install": str(path),
                  "Pin": "1.0.0", "Pin and bump": "1.0.0", "Pin · publisher": "1.0.0 · fixture", "Publisher": "fixture",
                  "Acceptance": "fixture output", "Bump": "manual", "Route": rid + " work: use directly",
                  "State": "prepared", "Record": "fixture"}
        cells = [values.get(c, "fixture") for c in columns]
        rc = reg.commit(str(control), [{"op": "upsert", "table": "cli", "cells": cells, "expect_row": None}],
                        date="2025-01-01", write=True, out=lambda x: None)
        if not isinstance(rc, dict) or not rc.get("written"):
            raise AssertionError("old row setup refused")
    document = manifest.skeleton("cli", "alpha")
    document.update(state="prepared", version="1.0.0", publisher="fixture", pin="1.0.0",
                    routes=[{"job": "alpha work", "route": "use directly"}])
    document["parts"] = {"install": {"paths": [str(path_a)]},
                         "register_row": {"register": str(control),
                                          "rows": [{"table": "cli", "name": "alpha"},
                                                   {"table": "cli", "name": "beta"}]}}
    mf = root / "alpha.json"
    mf.write_text(json.dumps(document))
    rc = manifest.activate(str(mf), str(control), date="2025-01-01", write=True, timeout=0, out=lambda x: None)
    parsed = reg.parse(control.read_text())
    states = [reg.state_word(reg.live_rows(parsed, "cli", rid)[0].cells[columns.index("State")])
              for rid in ("alpha", "beta")]
    result["H2"] = {"old_exit": rc, "states": states, "beta_exists": path_b.exists(),
                    "alpha_exists_control": path_a.exists()}
    # os.path.lexists catches lookup PermissionError; both scans falsely report absence.
    with patch("os.lstat", side_effect=PermissionError("planted inaccessible ancestor")):
        before = kinds.snapshot(str(root / ".claude.json"), str(root / "settings.json"), str(root / "skills"))
        after = kinds.snapshot(str(root / ".claude.json"), str(root / "settings.json"), str(root / "skills"))
    result["H3a"] = {"false_absence": all(not x["present"] for x in before.values()),
                     "old_changes": kinds.change_list(before, after, [])}
    skills = root / "skills"
    skills.mkdir()
    before = kinds.snapshot(str(root / ".claude.json"), str(root / "settings.json"), str(skills))
    result["H3a"]["accessible_empty_control"] = before["skills"]["present"] and not before["skills"]["entries"]
    (skills / "new").mkdir()
    (skills / "new/SKILL.md").write_text("Intended fixture")
    intended = kinds.snapshot(str(root / ".claude.json"), str(root / "settings.json"), str(skills))
    control_changes = [line for line, detail in kinds.change_list(before, intended, [])]
    (skills / "new/extra-hook").write_text("Unexpected hook")
    after = kinds.snapshot(str(root / ".claude.json"), str(root / "settings.json"), str(skills))
    actual = kinds.change_list(before, after, [])
    result["H3b"] = {"old_changes": [line for line, detail in actual],
                     "intended_only_control": control_changes,
                     "extra_exists": (skills / "new/extra-hook").is_file(),
                     "coarse_declaration_accepted": [line for line, detail in actual] == ["skills: added new"]}
    assert result["H1"]["ghost_bytes_written"] and result["H1"]["ghost_unaccounted"]
    assert result["H2"]["states"] == ["active", "active"] and not result["H2"]["beta_exists"]
    assert result["H3a"]["false_absence"] and not result["H3a"]["old_changes"]
    assert result["H3b"]["coarse_declaration_accepted"]
    print(json.dumps(result, indent=2))
    print("BASELINE reproduced 4/4 prohibited outcomes")


if __name__ == "__main__":
    main()
