#!/usr/bin/env python3
"""core-check.py — SessionStart hook: does the core still match its release?

Prints one line as session context, changes nothing and always exits 0. It warns; it never blocks.

    core: v0.10.0, unchanged (235 files)
    core: v0.10.0, 2 file(s) differ from the release: CLAUDE.md, .claude/skills/query/SKILL.md. Tell ...
    core: not checked (this copy has no git record of a release). Tell ...

The count is the check's own positive control: "unchanged" appears only after every git call has
finished and at least one tracked core file was seen. Any premise that fails, or a call that fails
or runs out of time, prints `core: not checked (<reason>)`, never "unchanged". The reason is written
here and never copied from git's error output, since a bug report carries this line and that
output can hold a home path.

`.claude/core-paths` holds one git pathspec a line, with `#` comments; a line matching nothing the
release or the index holds is a broken list, so the check says "not checked". The list is checked
against itself even where it does not name itself, so narrowing it shows. The working files are
compared, by content, with the newest release tag in HEAD's history. Two write-free steps name the
candidates: `status` for the working tree against HEAD, and a tree-to-tree `diff` for HEAD against
the tag, which is what sees an edit committed on top. Each candidate's working contents are then
compared with the tag's, so a file put back to the release after a local commit is no difference,
and neither is a mode alone. A core file flagged assume-unchanged or skip-worktree counts as
differing whatever its name or contents, since those flags hide an edit from git.

Two things in the core are the user's, and differ without a warning unless the file is flagged:
  - a helper definition's `model:` and `effort:` lines in its frontmatter, which the throttle derives
    from the user's choices;
  - `permissions.allow` in `.claude/settings.json`, where "always allow" answers can land. The rest
    of that file, the deny list included, is compared as JSON, so a new layout alone is no change.

Fresh starts only: a SessionStart `source` of `startup` or `clear`, or a missing or unreadable field.
Any other source prints nothing, since the session already holds the line. `--report` reads no
stdin and prints the same line, for a bug report.

`--no-optional-locks` keeps every call from rewriting `.git/index`, and from waiting on another git's
lock. A vault kept beside a separate clone takes no settings from an update, so no check runs there;
this script, run by hand in such a vault, says "not checked".

Usage: python3 .claude/hooks/core-check.py [--report]
Knob (env): CLAUDE_PROJECT_DIR, the vault root; default two levels above this file's folder.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

CORE_LIST = ".claude/core-paths"
SETTINGS = ".claude/settings.json"
DEFINITION_RE = re.compile(r"\.claude/agents/[^/]+\.md\Z")
FRONTMATTER_RE = re.compile(rb"\A---[ \t]*\r?\n.*?^---[ \t]*\r?$", re.M | re.S)
DERIVED_RE = re.compile(rb"^(?:model|effort)[ \t]*:[^\n]*\n", re.M)
# A release is vMAJOR.MINOR.PATCH, as publish.sh requires, so a `nightly`, a `v2-mine` and a
# `v1.2.0-rc1` are none. Git's glob cannot say that alone, hence the two patterns.
TAG_GLOB = "v[0-9]*.[0-9]*.[0-9]*"
NOT_A_RELEASE = "v*[!0-9.]*"
FRESH = ("startup", "clear")
# One budget for every git call in a run, so the calls together cannot pass the hook's 10-second
# limit and leave no line. Set by judgement: 2 seconds under that limit, to kill a hung git and
# print, and about 17 times the 460 ms median measured for a whole run on a 278-file clone. With
# 180 of 278 files differing and read, a synthetic clone of about the release's size took 765 ms.
DEADLINE_S = 8
SHOWN = 5        # names on the line; the rest are counted. Set by judgement, unmeasured.
NAME_CAP = 120   # characters of one name, so a long stray name cannot crowd the line. Set by judgement.
# These redirect git from the clone at hand to another repository, so an inherited one could turn
# this copy's edit into another repository's "unchanged".
GIT_ROUTING = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY")
NO_RECORD = "this copy has no git record of a release"
TELL_DIFFER = "Tell the owner in your first reply; a bug report carries this line."
TELL_UNCHECKED = 'Tell the owner in your first reply; MANUAL.md, "Updating", says what to do.'


class Unfinished(Exception):
    """The check could not finish; the message is the reason its line gives."""


def stop(proc):
    """Kill a timed-out git and whatever it started. No wait: the line must not hang on a child stuck
    in a read, and a finished child is reaped when this process exits a moment later."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (AttributeError, OSError):
        proc.kill()


def git(root, deadline, *args, stdin=None):
    """(exit code, stdout bytes) of one git call, inside what is left of the one deadline."""
    left = deadline - time.monotonic()
    if left <= 0:
        raise Unfinished("git took too long")
    env = {key: value for key, value in os.environ.items() if key not in GIT_ROUTING}
    try:
        proc = subprocess.Popen(
            ["git", "-C", root, "--no-optional-locks", *args], env=env, start_new_session=True,
            stdin=subprocess.DEVNULL if stdin is None else subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        raise Unfinished("git could not be started")
    try:
        out, _ = proc.communicate(stdin, timeout=left)
    except subprocess.TimeoutExpired:
        stop(proc)
        raise Unfinished("git took too long")
    return proc.returncode, out


def failed(step, code):
    return Unfinished("git %s failed with exit %d" % (step, code))


def read_core_list(root):
    """The pathspecs, with the list itself among them. Raises Unfinished on a missing or empty list."""
    path = os.path.join(root, CORE_LIST)
    if not os.path.isfile(path):
        raise Unfinished("no core list in this folder")
    try:
        with open(path, encoding="utf-8") as handle:
            lines = [line.strip() for line in handle]
    except (OSError, UnicodeDecodeError):
        raise Unfinished("the core list could not be read")
    paths = [line for line in lines if line and not line.startswith("#")]
    if not paths:
        raise Unfinished("the core list is empty")
    return paths if CORE_LIST in paths else paths + [CORE_LIST]


def release_tag(root, deadline):
    """The newest release tag in HEAD's history, once this folder is shown to be a clone's root."""
    code, out = git(root, deadline, "rev-parse", "--is-inside-work-tree", "--show-cdup")
    if code:
        if os.path.exists(os.path.join(root, ".git")):
            raise failed("rev-parse", code)
        raise Unfinished(NO_RECORD)
    fields = out.split(b"\n")
    if fields[0] != b"true" or fields[1:2] != [b""]:   # a folder inside some other repository
        raise Unfinished(NO_RECORD)
    code, out = git(root, deadline, "describe", "--tags", "--abbrev=0", "--match", TAG_GLOB,
                    "--exclude", NOT_A_RELEASE, "HEAD")
    tag = out.decode("utf-8", "replace").strip()
    if code or not tag:
        raise Unfinished("no release tag in this copy's history")
    return tag


def tracked_core(root, deadline, ref, paths):
    """(how many core files are tracked, the names hidden by a flag). --with-tree keeps a path the
    release holds from reading as a broken list once a commit has removed it; such a path is listed
    with the letter M, and the tree-to-tree diff reports it."""
    code, out = git(root, deadline, "ls-files", "-v", "-z", "--error-unmatch",
                    "--with-tree=" + ref, "--", *paths)
    if code == 1:
        raise Unfinished("a line of the core list matches nothing git tracks")
    if code:
        raise failed("ls-files", code)
    count, hidden = 0, set()
    for entry in filter(None, out.split(b"\0")):
        letter, name = entry[:1], os.fsdecode(entry[2:])
        if letter == b"M":
            continue
        count += 1
        if letter.islower() or letter == b"S":   # lower case: assume-unchanged; S: skip-worktree
            hidden.add(name)
    if not count:
        raise Unfinished("the core list matches no tracked file")
    return count, hidden


def changed_names(root, deadline, ref, paths):
    """Core paths differing from HEAD on disk, or from the tag in HEAD."""
    code, out = git(root, deadline, "status", "--porcelain=v1", "-z", "--untracked-files=all",
                    "--no-renames", "--", *paths)
    if code:
        raise failed("status", code)
    names = set()
    for entry in filter(None, out.split(b"\0")):
        if len(entry) < 4 or entry[2:3] != b" ":
            raise Unfinished("git status gave a line this check cannot read")
        names.add(os.fsdecode(entry[3:]))
    code, out = git(root, deadline, "diff", "--name-only", "-z", "--no-renames", ref, "HEAD",
                    "--", *paths)
    if code:
        raise failed("diff", code)
    names.update(os.fsdecode(name) for name in filter(None, out.split(b"\0")))
    return names


def released_bytes(root, deadline, ref, names):
    """{name: its bytes in the tag, or None where the tag has no such path}, in one git call however
    many there are. No entry means no answer: a folder at that path, or a name git reads as a line and
    so cannot be asked about, since it would drop a trailing carriage return and answer for another."""
    asked = [name for name in names if "\n" not in name and "\r" not in name]
    if not asked:
        return {}
    request = "".join("%s:%s\n" % (ref, name) for name in asked)
    code, out = git(root, deadline, "cat-file", "--batch", stdin=os.fsencode(request))
    if code:
        raise failed("cat-file", code)
    found, pos = {}, 0
    for name in asked:
        end = out.index(b"\n", pos)
        line = out[pos:end]
        pos = end + 1
        if line.endswith(b" missing"):   # tested first: this reply echoes the name, spaces and all
            found[name] = None
            continue
        head = line.split()
        if len(head) == 3 and head[2].isdigit():
            size = int(head[2])
            if head[1] == b"blob":
                found[name] = out[pos:pos + size]
            pos += size + 1              # a folder's reply carries a body too
    return found


def disk_bytes(root, name):
    """What git would store for a working path: a file's bytes, a link's own text, else None."""
    path = os.path.join(root, name)
    try:
        if os.path.islink(path):
            return os.fsencode(os.readlink(path))
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def without_derived(raw):
    """A definition with the frontmatter's model: and effort: lines lifted out; a line of that shape
    in the body is the product's, and stays."""
    match = FRONTMATTER_RE.match(raw)
    if not match:
        return raw
    return DERIVED_RE.sub(b"", match.group(0)) + raw[match.end():]


def without_allow(raw):
    """Settings as data with `permissions.allow` lifted out, or None where they are not an object.
    A `permissions` block left empty goes too, so an allow list added to a release with no block
    compares equal."""
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    block = data.get("permissions")
    if isinstance(block, dict):
        block = {key: value for key, value in block.items() if key != "allow"}
        if block:
            data["permissions"] = block
        else:
            del data["permissions"]
    return data


def same_content(name, old, new):
    """True when working bytes equal the release's, apart from what belongs to the user."""
    if new is None:
        return False
    if name == SETTINGS:
        kept = without_allow(new)
        return kept is not None and kept == without_allow(old)
    if DEFINITION_RE.match(name):
        return without_derived(old) == without_derived(new)
    return old == new


def matches_release(root, name, released):
    """True when this candidate's working path is as the release has it. A path the release lacks
    matches only by being absent, so a stray new file, whatever its size, is never read."""
    if name not in released:
        return False
    if released[name] is None:
        return not os.path.lexists(os.path.join(root, name))
    return same_content(name, released[name], disk_bytes(root, name))


def differences(root, deadline, ref, names):
    """The candidates whose working contents differ from the release's. A clean tree has none and
    pays for no read; the rest cost one git call, however many they are."""
    candidates = sorted(names)
    released = released_bytes(root, deadline, ref, candidates) if candidates else {}
    return [name for name in candidates if not matches_release(root, name, released)]


def shown(name):
    """One name, safe on one line: anything unprintable becomes `?`, a newline included."""
    return "".join(char if char.isprintable() else "?" for char in name)[:NAME_CAP]


def core_line(root, deadline):
    paths = read_core_list(root)
    if shutil.which("git") is None:
        raise Unfinished("git is not installed")
    tag = release_tag(root, deadline)
    ref = "refs/tags/" + tag
    count, hidden = tracked_core(root, deadline, ref, paths)
    changed = changed_names(root, deadline, ref, paths)
    differ = sorted(hidden | set(differences(root, deadline, ref, changed)))
    if not differ:
        return "core: %s, unchanged (%d files)" % (tag, count)
    names = ", ".join(shown(name) for name in differ[:SHOWN])
    if len(differ) > SHOWN:
        names += " and %d more" % (len(differ) - SHOWN)
    return "core: %s, %d file(s) differ from the release: %s. %s" % (tag, len(differ), names, TELL_DIFFER)


def fresh_start(stream):
    """False only for a source that is present and names a session already under way."""
    try:
        if stream is None or stream.isatty():
            return True
        event = json.loads(stream.read() or "null")
    except (OSError, ValueError):
        return True
    source = event.get("source") if isinstance(event, dict) else None
    return not isinstance(source, str) or source in FRESH


def main(argv):
    deadline = time.monotonic() + DEADLINE_S
    if "--report" not in argv and not fresh_start(sys.stdin):
        return 0
    root = (os.environ.get("CLAUDE_PROJECT_DIR")
            or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    try:
        line = core_line(root, deadline)
    except Unfinished as err:
        line = "core: not checked (%s). %s" % (err, TELL_UNCHECKED)
    except Exception as err:   # a session start is never broken by this check
        line = "core: not checked (the check itself failed: %s). %s" % (type(err).__name__, TELL_UNCHECKED)
    try:
        sys.stdout.buffer.write((line + "\n").encode("utf-8", "replace"))
        sys.stdout.buffer.flush()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
