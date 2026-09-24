# Figure audit checklist

Apply checks relevant to the figure contract. For each, record the artifact, method, observed
result, and coverage gap. Author QA notes are useful context, not independent evidence.

## 1. Mechanical screening

Resolve `figure_audit.sh` relative to the skill install directory. `all` combines the applicable
checks below; use individual commands for selected artifacts in a mixed directory.

| Check | Command | What the helper checks |
|---|---|---|
| Size | `figure_audit.sh geometry <file.svg\|file.pdf>` | Absolute SVG width/height, or every PDF page via pdfinfo with rotation applied, against width/height limits |
| SVG text | `figure_audit.sh text <file.svg> --min-pt <floor>` | Live versus outlined glyphs; rendered font size with inheritance, em/%, ancestor transforms, and physical units |
| PDF fonts | `figure_audit.sh fonts <file.pdf>` | Embedding via pdffonts; detected Type 3 versus other font types |
| Raster | `figure_audit.sh export <file.tiff\|file.png> --min-dpi <dpi> --tiff-modes <modes>` | Decoding, TIFF color mode, and DPI metadata when present |
| Inventory | `figure_audit.sh inventory <dir> --formats svg,pdf,png --expect <stem>` | Figure files are nonempty; each `--expect` stem, and each stem found in two or more formats, has every required format |
| Staleness | `figure_audit.sh stale <dir> <generator> [<dependency> ...]` | Modification times against supplied dependencies, and log timing |
| Video | `figure_audit.sh video <file.mp4> --codec <codec> [--thorough]` | ffprobe metadata; ffmpeg decodes the first frame and final second (every frame with `--thorough`); dimension parity; codec |
| SVG reproducibility | `figure_audit.sh svgdiff <final.svg> <rerun.svg>` | Text diff with consistent ID renaming and date normalization |

Defaults (180 × 247 mm, 5.5 pt, 300 DPI, alpha-free TIFF modes, H.264, four export formats) are
helper conventions. Use the actual contract.

Exit status: `0` all checks ran and passed; `1` a check failed; `3` nothing failed but a check
was skipped or nothing was checked; `2` usage error. `--allow-skip` accepts stated skips. Other raster color modes, resolutions, and video codecs can be valid;
explain departures rather than treating these defaults as current journal rules.

Limits to report:

- Without `--expect`, inventory cannot discover a figure missing in every format, and stems
  found in only one format are listed as INFO rather than checked. Pass every stem from the
  handoff, relative to the figure directory (for example `panel-set/figure1`). Files in
  different directories do not complete each other's format sets. Inventory does not
  decode files; the per-format checks and your inspection do.
- SVG font sizing does not resolve `<style>` sheets or class rules; those gaps are reported
  and the font check SKIPs rather than passes. PDF font sizes are not measured.
- DPI metadata does not prove sufficient effective resolution at the intended printed size.
- A timestamp comparison can identify suspect staleness but cannot prove provenance. Check
  recorded inputs, hashes, and generation commands where available.
- SVG normalization preserves ID/reference relationships but is not a visual equivalence proof.
- Video decoding shows the ends decode without error; it does not establish frame identity
  or content. Compare requested versus recorded dimensions: odd dimensions may already have
  been cropped during encoding. Inspect representative frames using available tools.
- Optional dependencies can be missing. A skipped mandatory check leaves the audit incomplete.

## 2. Contract and identity

- Does every panel support the declared conclusion and panel-to-evidence map?
- Verify subject, condition, model, and selection from source content or metadata rather than
  filenames alone. Check for identifier collisions and incomplete cache keys.
- Check thresholds, units, transformations, cluster numbering, and sample selection against
  the contract. Verify counts from source rows, not just the plotting arrays.
- Confirm the selected Python or R backend generated the exports and any new QA renders.
  Inherit the author's choice; missing runtime blocks rerendering, not other inspection.

## 3. Provenance and privacy

- Trace generator → intermediate artifacts → source data, including inputs to composites.
- Compare the delivered caption, legend, data tables, and run record to the current exports.
- Record artifact versions/hashes. Do not assume untracked files have usable Git history.
- Inspect embedded metadata, comments, labels, and file references for unintended personal
  information or private paths. Report the field/location without copying sensitive contents.

## 4. Scientific claims and statistics

- Independently recompute quantitative claims from the earliest usable source. State when
  only processed data are available and what assumptions remain unverified.
- Check `n`, biological versus technical repeats, the experimental unit, center/spread or
  interval definition, test, multiplicity correction, and exact comparison against the caption.
- Check units and time scales, denominators, exclusion/filter rules, missingness, and attrition
  at the level relevant to the claim. Distinguish absent data from data excluded by analysis.
- For model figures, check split definitions, leakage risks, seeds/folds, metric definitions,
  uncertainty, and baseline consistency when relevant to the plotted claim.
- Do not validate an ordering or statistic solely against the same array that defines it.
- When normalization or sampling might explain the claimed effect, use a proportionate
  independent control. Avoid requiring unrelated experiments for a presentation-only audit.

## 5. Rendered appearance and image integrity

- Inspect final artifacts at intended size and enlarged: clipping, overlap, panel labels,
  legibility, color encoding, shared scales, legend scope, and agreement with the caption.
- Check that comparable panels use comparable scales or disclose differences clearly.
  Check accessibility beyond red/green distinctions when categories depend on color.
- Inspect source image aspect, resampling, calibrated scale bars, crop, contrast, stitching,
  and reuse when applicable. Locate the raw-to-processed chain for image-based claims.
- Verify requested visual changes from the export, not just from plotting code. Automated
  bounding-box or pixel checks can support visual inspection but do not prove it by themselves.
- If pixels cannot be inspected with available tools, state that visual review is incomplete.
  Do not substitute a source-code review for inspection of the final render.

## 6. Reproduction

Rerun only within the allowed scratch directory using the selected backend and supplied
command, after checking it will not overwrite source artifacts. Compare claims and rendered
content; account for metadata, compression, and stochastic variation. Byte-identical images
are useful for deterministic exports but are not a universal requirement.

Exercise failure paths only if generator reliability is in scope and the checks can be
isolated safely. Missing outputs must not count as success. Do not edit the author’s code or
run costly jobs beyond the handoff constraints; describe unavailable checks in the report.

## 7. Parent-to-reviewer brief

```text
You are the independent reviewing subagent. Use figure-audit at <skill-dir>/SKILL.md.
Audit directly; do not delegate again or modify the generator/data/final exports.
Read <relevant project instructions>. Write verification outputs only to <scratch-dir>.

Original request: <request>
Figure contract: <core conclusion; panel map; archetype; selected Python/R backend>
Export contract: <dimensions; font limits; formats; resolution; other agreed requirements>
Artifacts and caption: <exact paths>
Source data and definitions: <paths; units; selection; statistics>
Generator and reproduction: <path; command; runtime; how to redirect outputs>
Constraints: <time/compute limits; known unavailable inputs>
Optional author QA: <paths; treat as unverified>

Recompute material claims independently and inspect the final rendered artifacts.
Return scope/version evidence; ranked findings with expected/observed results and
reproducible evidence; checks run; checks skipped with reasons; and PASS, NEEDS_CHANGES,
or INCOMPLETE. Recommend fixes for the author; apply none yourself.
```

## 8. Reviewer report

```text
Scope: <artifact paths + hashes/version; contract; backend; independent or self-review>

Findings:
- [blocker / should-fix / cosmetic] <panel/file and issue>
  Expected: <contract/claim>
  Observed: <measurement or rendered evidence>
  Evidence: <source; method/command; result>
  Recommendation: <correction for author>

Coverage:
- Source-data checks: <methods and outcomes>
- Rendered-artifact checks: <methods and outcomes>
- Mechanical checks: <results and relevant limitations>
- Skipped/blocked: <reason; effect on clearance>

Verdict: <PASS / NEEDS_CHANGES / INCOMPLETE with concise reason>
```

Revised artifacts require rechecking affected findings. Report unresolved gaps even if every
executed helper check passed. A separate vendor or model is not required for independence;
a reviewer who did not author the figure and independently checks evidence is the requirement.
