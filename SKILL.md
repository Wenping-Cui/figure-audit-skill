---
name: figure-audit
description: >-
  Independently audit scientific figures produced by nature-figure before delivery or after
  revision. Use as the reviewing subagent for a figure-making agent, or when asked to audit
  an existing scientific figure. Check rendered artifacts, source data, scientific claims,
  and the agreed figure/export contract; return evidence-backed findings to the parent.
  Does not author or restyle figures, and does not review unrelated code.
---

# Figure audit

Use this skill as the independent review stage of `nature-figure`. The parent coordinates,
the figure author renders and fixes, and a separate auditor checks the result. An existing
figure can also be audited without `nature-figure` installed when its brief and artifacts
provide the necessary context.

## Choose your role

**Parent / figure author:** after the exports exist, launch one fresh reviewing subagent
using the host's available delegation tool. Give it this SKILL.md and the handoff below.
Prefer a fresh context containing the task, contract, and source artifacts rather than the
author's reasoning or prior verdict. The reviewer must not have authored the figure.
Wait for its report before describing the figure as independently audited. A skill file
alone does not register a subagent or arrange automatic invocation by another skill.

| Host | Parent delegation | Reviewer behavior |
|---|---|---|
| Codex | Use `spawn_agent` when exposed, with a fresh context (`fork_turns="none"` when supported) and an explicit brief. | Read this skill and audit directly; return findings through the host's agent result. |
| Claude Code | Use the available `Agent`/subagent tool with this skill's path and the explicit brief. | Read this skill and audit directly; return findings in the subagent response. |

Tool names vary by host/version; use the available equivalent. Both hosts use the same
handoff, read-only review boundary, helper scripts, and verdicts. Honor the host/user model
configuration; no pinned vendor, model, or effort level is required.

**Reviewing subagent:** perform the audit yourself and return the report to your parent.
Do not spawn another reviewer, edit the generator, overwrite exports, or apply fixes.
You may write verification code and rerun outputs in the assigned scratch directory.
If a rerun cannot be redirected safely, report that gap and continue other checks.

If delegation is unavailable, the parent may perform a clearly labelled self-review;
do not describe it as independent. Use actual available tools for source and image
inspection; do not assume a model or vendor can or cannot inspect pixels.

## Handoff from nature-figure

The parent supplies these items, preferably with project-relative paths:

- The original request and relevant project instructions.
- The figure contract: core conclusion, panel-to-evidence map, archetype, selected
  Python or R backend, final dimensions, typography, and required export formats.
- Exact final artifact paths, caption/legend, generator and rerun command, source-data
  paths, selection rules, statistics definitions, and any author QA notes.
- A scratch directory for verification outputs, plus runtime or resource constraints.

Use [references/checklist.md](references/checklist.md) for the brief and report templates.
Missing source data limits scientific verification; missing rendered images limits visual
verification. Request missing items from the parent, continue checks that are possible,
and mark material gaps as `INCOMPLETE`. Never invent data to complete an audit.

Inherit the selected backend; do not reopen the Python/R choice for an existing figure.
All new renders, previews, exports, and visual QA images must use that backend, consistent
with `nature-figure`. Non-visual inspection by the bundled Python helper is allowed for
R figures. If the selected runtime is missing, skip rerendering and report the blocker;
do not switch backends. Read relevant `nature-figure` contract/QA references when supplied
or available; this audit does not require restarting its figure-authoring workflow.

## Audit procedure

1. **Identify the exact artifacts.** Record the reviewed filenames and hashes or other
   version evidence so the report is tied to the exports actually inspected. Compare
   against the supplied contract, not assumptions about journal defaults.
2. **Run applicable mechanical checks.** Resolve `scripts/figure_audit.sh` relative to
   this SKILL.md. Pass the contract's dimensions, font floor, formats, and the stems of
   every figure named in the handoff:

   ```bash
   bash <skill-dir>/scripts/figure_audit.sh all <figure-dir> \
     --generator <generator> --expect <figure-stem> --formats svg,pdf,png \
     --max-width-mm 183 --max-height-mm 247 --min-pt 5.5
   ```

   Values above are examples, not universal journal requirements; `--min-dpi`,
   `--tiff-modes`, and `--codec` also take contract values. Prefer individual commands
   for a mixed directory so unrelated assets do not distort the audit. Exit `0` means
   every check ran and passed, `1` a check failed, `3` nothing failed but a check was
   skipped (mechanical screen incomplete), `2` usage error. `--allow-skip` turns `3`
   into `0` only for gaps you state in the report. A `PASS` applies only to the named
   check and never establishes scientific correctness or a complete audit.
3. **Independently check evidence and pixels.** Follow the relevant sections of the
   checklist. Recompute claims from source data using independent calculations rather
   than trusting the author's verification arrays. Inspect the actual final render at
   publication size and enlarged. Report inaccessible pixels explicitly. Mechanical
   failures do not prevent independent checks that can still be completed.
4. **Return findings to the parent.** Use the report format below. Findings need concrete
   evidence and a suggested correction; the author implements the correction. Consult
   [references/failure-modes.md](references/failure-modes.md) for relevant failure patterns,
   not a required list of experiments to run on every figure.
5. **Recheck revisions.** When the parent supplies revised artifacts, rerun checks affected
   by the changes and relevant mechanical checks. Record the new artifact versions and
   unresolved findings. A verdict on an earlier render does not clear a new export.

## Required report

- **Scope:** artifacts/version evidence, contract, backend, and whether review was independent.
- **Findings:** ranked `blocker`, `should-fix`, or `cosmetic`; each with panel/file location,
  expected versus observed result, reproducible evidence, and recommended correction.
- **Coverage:** checks performed and results; checks skipped or blocked with reasons and
  their effect on the conclusion. Separate source-data verification from visual inspection.
- **Verdict:** `PASS` when required checks are complete and no blocker/should-fix remains;
  `NEEDS_CHANGES` when an established defect requires correction; `INCOMPLETE` when missing
  evidence prevents clearance. If defects and gaps coexist, report `NEEDS_CHANGES` and
  explicitly state the incomplete coverage. Cosmetic suggestions alone need not block.

The parent verifies disputed findings, sends supported corrections to the author, and
requests re-audit of the changed output. A helper's exit status is not the reviewer verdict.

## Privacy

Keep reusable instructions and examples free of personal names, usernames, email addresses,
local home paths, private repository/service links, subject identifiers, and session history.
Use generic examples. In audit reports prefer project-relative artifact paths and only the
identifiers necessary to locate evidence; do not copy credentials or unrelated personal data
from source files or metadata. Flag sensitive export metadata to the parent without repeating
its contents. Artifact edits, including metadata removal, belong to the author.
