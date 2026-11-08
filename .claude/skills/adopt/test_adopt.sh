#!/bin/sh
# The caller supplies this script's literal path; Python derives its sibling suite.
exec python3 -B - "$0" "$@" <<'ADOPT_REGISTER_SUITE'
import runpy
import sys
from pathlib import Path
target = Path(sys.argv.pop(1)).resolve(strict=True).with_name("test_register.py")
sys.path.insert(0, str(target.parent))
sys.argv[0] = str(target)
runpy.run_path(str(target), run_name="__main__")
ADOPT_REGISTER_SUITE
