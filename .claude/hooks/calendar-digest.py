#!/usr/bin/env python3
"""SessionStart hook: the calendar digest, computed with no model call.

Reads CALENDAR.md at the vault root (CLAUDE_PROJECT_DIR, else the working directory) and prints,
as session context: a header with counts, then every overdue unticked item and every item due
within seven days, never cut below the hook-output limit. An absent file prints one line; an
unreadable file prints one line naming the error; malformed item lines are counted; items whose
date is approximate or conditional (no leading YYYY-MM-DD) are counted and never treated as exact.
Above the output cap (OUT_CAP bytes, below the harness's roughly 10 kB hook-output limit) it shows
what fits and names how many lines remain. Stateless: a resume or a compaction restart prints the
same digest as the start, for the same file and day. Always exits 0.

Line format (CALENDAR.md): `- [ ] YYYY-MM-DD[ HH:MM] · what · [[detail]]`; `[x]` done, `[-]` withdrawn.
Window: 7 days (set by judgement, unmeasured).
"""
import datetime
import os
import re
import sys

WINDOW_DAYS = 7
OUT_CAP = 9000  # bytes; headroom under the ~10 kB hook-output limit
ITEM_RE = re.compile(r"^- \[([ xX\-])\] (.*\S)\s*$")
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?: (\d{2}):(\d{2}))?\b")


def digest(path: str, today: datetime.date) -> str:
    if not os.path.exists(path):
        return f"calendar: {os.path.basename(path)} absent (no dated items known)"
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception as e:  # unreadable, undecodable
        return f"calendar: {os.path.basename(path)} unreadable ({e.__class__.__name__}: {e})"
    overdue, due, approx, malformed = [], [], 0, 0
    horizon = today + datetime.timedelta(days=WINDOW_DAYS)
    for line in lines:
        if not line.startswith("- ["):
            continue
        m = ITEM_RE.match(line)
        if not m:
            malformed += 1
            continue
        mark, text = m.group(1), m.group(2)
        if mark != " ":
            continue  # done or withdrawn
        d = DATE_RE.match(text)
        if not d:
            approx += 1
            continue
        try:
            when = datetime.date(int(d.group(1)), int(d.group(2)), int(d.group(3)))
        except ValueError:
            malformed += 1
            continue
        if when < today:
            overdue.append((when, text))
        elif when <= horizon:
            due.append((when, text))
    overdue.sort(key=lambda t: t[0])
    due.sort(key=lambda t: t[0])
    head = (f"calendar ({today.isoformat()}): {len(overdue)} overdue · {len(due)} due within "
            f"{WINDOW_DAYS} days · {approx} approximate-dated · {malformed} malformed")
    body = [f"overdue: {t}" for _, t in overdue] + [f"due: {t}" for _, t in due]
    out, size = [head], len(head.encode("utf-8")) + 1
    for i, b in enumerate(body):
        n = len(b.encode("utf-8")) + 1
        if size + n > OUT_CAP:
            out.append(f"… and {len(body) - i} more line(s): read CALENDAR.md")
            break
        out.append(b)
        size += n
    return "\n".join(out)


def main():
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    path = os.path.join(root, "CALENDAR.md")
    today = datetime.date.today()
    if os.environ.get("CALENDAR_DIGEST_TODAY"):  # tests only
        today = datetime.date.fromisoformat(os.environ["CALENDAR_DIGEST_TODAY"])
    try:
        sys.stdout.write(digest(path, today) + "\n")
    except Exception as e:  # never break a session start
        sys.stdout.write(f"calendar: digest failed ({e.__class__.__name__}: {e})\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
