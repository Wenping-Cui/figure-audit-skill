# Figure-audit skill

`figure-audit` is the independent reviewing subagent workflow for figures made with
`nature-figure`. The parent hands finished exports and their figure contract to a fresh
reviewer. The reviewer checks data, claims, and rendered artifacts, then returns findings;
the author fixes the figure and the reviewer checks the revision.

It also supports audits of existing scientific figures when the source artifacts are supplied.
No vendor-specific review bridge or second model subscription is required.

## Install

From this repository's root, link the skill into the host you use:

```bash
# Claude Code
mkdir -p ~/.claude/skills
ln -s "$PWD" ~/.claude/skills/figure-audit

# Codex
mkdir -p ~/.codex/skills
ln -s "$PWD" ~/.codex/skills/figure-audit
```

Use `/figure-audit` in Claude Code or `$figure-audit` in Codex. The skill describes a
subagent workflow; installation does not register a dedicated agent or modify
`nature-figure`. To request the pairing:

> Make the figure using nature-figure. Before delivery, launch a fresh subagent using
> figure-audit to review the exports, source data, caption, and agreed figure contract.
> Return supported corrections to the figure author and recheck the revised exports.

If already running as the reviewer, the agent audits directly without further delegation.
Without a delegation tool, the result must be labelled a self-review.

## Mechanical helper

Python 3 standard library handles core checks. Optional dependencies are Pillow for raster
inspection, poppler's `pdfinfo` and `pdffonts` for PDF geometry and fonts, and `ffprobe` plus
`ffmpeg` for video inspection. Unavailable checks are reported as `SKIP`. These inspect existing files without creating graphics, including
when the figure was authored in R.

```bash
bash scripts/figure_audit.sh all path/to/figures \
  --generator path/to/make_figure.py --expect fig1 --formats svg,pdf,png \
  --max-width-mm 183 --max-height-mm 247 --min-pt 5.5
bash scripts/figure_audit.sh geometry path/to/figure.svg --max-width-mm 89
bash scripts/figure_audit.sh svgdiff path/to/final.svg path/to/rerun.svg
```

Choose formats, limits, TIFF modes (`--tiff-modes`), and video codec (`--codec`) from the
supplied figure contract. Built-in defaults are screening values, not verified journal
requirements. Exit status: `0` every check ran and passed, `1` a check failed, `3` nothing
failed but something was skipped or nothing was checked, `2` usage error. `--allow-skip`
accepts stated skips as exit `0`. Read the coverage and skips before interpreting results. The helper does not establish scientific correctness, inspect layout visually, or
replace the independent reviewer.

## Contents

- [SKILL.md](SKILL.md): parent/reviewer roles, nature-figure handoff, and report contract.
- [references/checklist.md](references/checklist.md): evidence checks and handoff template.
- [references/failure-modes.md](references/failure-modes.md): generic failure examples.
- `scripts/figure_audit.sh` and `scripts/figure_audit.py`: mechanical screening helpers.
- `agents/openai.yaml`: Codex display metadata.
