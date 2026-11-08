#!/bin/sh
# Install-time acceptance: run immediately after a successful qmd-fresh.sh,
# outside the sandbox, with the same vault root and qmd environment.
# Usage: /bin/sh qmd-live-check.sh [vault-root]
# Root: argument, then CLAUDE_PROJECT_DIR, then PWD. Uses the wiki collection.
# Select the newest visible wiki Markdown page by filesystem mtime (path breaks
# ties); log.md is excluded by the search contract. Query a phrase from its body.
# No planting, refresh or file-writing commands; output is stdout only.
# qmd owns its configured index/cache; this check never changes source pages.
# Exit 0 = exact newest page returned by vector search; 1 = page missing among
# results; 2 = PROBE FAILED (disabled, absent, unreadable, empty or failed query).
if ! command -v python3 >/dev/null; then
    printf '%s\n' 'PROBE FAILED: python3 absent'
    exit 2
fi
exec python3 -B - "$@" <<'PY_QMD_LIVE_CHECK'
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys

# Query size, result limit and hang bound: set by judgement, unmeasured.
MIN_WORDS, MAX_WORDS, LIMIT, TIMEOUT = 4, 24, 20, 240

def fail(reason):
    print('PROBE FAILED: ' + ' '.join(str(reason).split()))
    sys.exit(2)

def scan_error(error):
    raise error

def pages(root):
    found = []
    for directory, dirs, files in os.walk(root / 'wiki', onerror=scan_error):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for name in files:
            page = Path(directory) / name
            if (name.startswith('.') or page.suffix != '.md' or page.is_symlink()
                    or page == root / 'wiki/log.md'):
                continue
            found.append((page.stat().st_mtime_ns, str(page.relative_to(root)), page))
    if not found:
        fail('no eligible wiki Markdown pages')
    return max(found), len(found)

try:
    if len(sys.argv) > 2:
        fail('usage: qmd-live-check.sh [vault-root]')
    root = Path(sys.argv[1] if len(sys.argv) == 2 else
                os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())).resolve()
    if (root / '.qmd-off').exists():
        fail('.qmd-off present; semantic acceptance cannot run')
    if not (root / 'wiki').is_dir():
        fail('wiki directory missing')
    qmd = shutil.which('qmd')
    if not qmd:
        fail('qmd absent')
    selected, count = pages(root)
    _, relative, page = selected
    original = page.read_bytes()
    lines = original.decode('utf-8-sig').splitlines()
    if lines and lines[0].strip() == '---':
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == '---'), None)
        if end is None:
            fail('newest page has unterminated frontmatter')
        lines = lines[end + 1:]
    phrase = None
    fence = None
    words = re.compile(r"\b[\w’'-]+(?:[ \t]+[\w’'-]+){%d,%d}\b" %
                       (MIN_WORDS - 1, MAX_WORDS - 1))
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(('```', '~~~')):
            marker = stripped[:3]
            fence = None if fence == marker else (fence or marker)
            continue
        if fence or not stripped or stripped.startswith(('#', '<', '|')):
            continue
        match = words.search(line)
        if match:
            phrase = ' '.join(match.group().split())
            break
    if not phrase:
        fail('newest page has no usable body phrase')
    print(f'LIVE CHECK: page={json.dumps(relative)}; eligible pages={count}; '
          f'phrase={json.dumps(phrase)}', flush=True)
    # A single vec: query has no lexical branch. --no-rerank avoids loading the
    # expansion and reranking models; --full-path proves physical page identity.
    with subprocess.Popen([qmd, 'query', 'vec: ' + phrase, '--no-rerank', '--json',
                           '--full-path', '-c', 'wiki', '-n', str(LIMIT)], cwd=root,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True) as process:
        try:
            stdout, stderr = process.communicate(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            fail(f'qmd vector query exceeded {TIMEOUT}s; query process group stopped')
    if process.returncode:
        fail(f'qmd vector query exited {process.returncode}: {stderr or stdout}')
    hits = json.loads(stdout)
    if not isinstance(hits, list) or any(not isinstance(h, dict) or
            not isinstance(h.get('file'), str) for h in hits):
        fail('qmd JSON is not a result list with file paths')
    if not hits:
        fail('vector query returned no results; positive control absent')
    if pages(root)[0] != selected or page.read_bytes() != original:
        fail('newest wiki page changed during acceptance')
    # Virtual identifiers are insufficient evidence of the intended live vault.
    matches = sum('://' not in h['file'] and
                  (root / h['file']).resolve() == page for h in hits)
    print(f'{"PASS" if matches else "FAIL"} live semantic newest-page check: '
          f'matches={matches}; returned={len(hits)}; page={json.dumps(relative)}')
    sys.exit(0 if matches else 1)
except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired) as error:
    fail(error)
PY_QMD_LIVE_CHECK
