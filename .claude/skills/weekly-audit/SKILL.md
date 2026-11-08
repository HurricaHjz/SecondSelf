---
name: weekly-audit
description: "The weekly review's tools: the fresh-eyes audit (AUDIT.md), the waste report (weekly-waste.py) and the rule register's one pass (rule_register.py). The calendar's Weekly review runs them each Sunday; /weekly-audit runs them on request. Nothing here schedules itself or stops other work."
user-invocable: true
---

# Weekly audit

The Weekly review in `CALENDAR.md` runs these tools, in this order; nothing schedules them, and
each tool's procedure is its own file.

| Tool | What it does | Its procedure |
|---|---|---|
| The fresh-eyes audit | One reviewer with no prior context reads the week's changed framework files, the lifecycle rows due for review, the items with no row and one rotating slice; the head re-verifies and disposes of each finding. | `AUDIT.md`, with `slice.py`, `pass_order.py` and `brief-audit.md` |
| The rule register's one pass | `rule_register.py weekly` lists what the rule register finds, inside the audit (`AUDIT.md`, step 8). It only lists. | `rule_register.py`'s own docstring |
| The clean-up's listing | `rule_register.py cleanup` prints the store sizes and the old records no wiki page, calendar line or open register entry names, for the weekly review's clean-up step. It lists and deletes nothing. | `rule_register.py`'s own docstring |
| The waste report | Recorded helper consumption and operational outcomes across runs, from the run records alone. It judges nothing. | `README.md` and `FIELDS.md`, with `weekly-waste.py` |

## Where things live

This folder ships, so it holds code and procedure only. Everything a run produces stays out of it:

- **State**, outside the vault: `<store>/tools/weekly-audit/slices.json` and
  `<store>/tools/weekly-waste/dispositions.jsonl`, where `<store>` is `LLM_WIKI_STORE`, else
  `~/.llm-wiki`. Never delete either to start over: each holds a history the next run depends on.
- **Reports**, in the user's layer: `output/reports/audit-report-<date>.md`,
  `output/reports/waste-report-<date>.md` and `output/reports/waste-detail-<date>.md`. The shipped
  `.gitignore` keeps `output/` out of every push.
- **Rows**: `wiki/developments/check-lifecycle.md`, which `setup.sh` seeds with its rules and no rows.
- **The rule register's data**: `wiki/developments/rule-register-data.json`. It holds the owner's
  wordings and never ships, so on a fresh copy the register's pass says "not applicable".

## First use

`setup.sh` makes both stores on a fresh vault. By hand, once each:

```bash
store="${LLM_WIKI_STORE:-$HOME/.llm-wiki}"
mkdir -p "$store/tools/weekly-audit" "$store/tools/weekly-waste" "$store/hooks" output/reports
python3 -B .claude/skills/weekly-audit/slice.py --init
python3 -B .claude/skills/weekly-audit/weekly-waste.py init
```

The audit's `slice.py` needs markdown-it-py 4.2.0 (`python3 -m pip install markdown-it-py==4.2.0`);
without it every pick stays incomplete and says so. The waste report and `pass_order.py` need
nothing beyond Python itself.

The suites are `test_slice.py`, `test_pass_order.py`, `test_weekly_waste.py` and
`test_rule_register.sh`; each ends `PASS n/n` or `FAIL k/n`.
