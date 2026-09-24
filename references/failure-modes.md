# Generic failure patterns

These examples illustrate audit risks without retaining personal project histories. Use the
patterns relevant to the figure; they are not a requirement to run every possible control.

## Wrong source or model

A label says subject B while a cached path loads subject A. Reused session identifiers make the
result look plausible. Similarly, a wildcard loader can substitute another model with matching
parameters. Verify source content and embedded provenance, then inspect whether cache keys
include subject, model, condition, and relevant parameters.

## Stale composites

A composite is newly rendered from outdated panels. Its timestamp is current while its content
predates a correction. Trace dependencies through intermediate outputs and compare artifact
versions, generator inputs, and run records. Modification times are clues, not proof.

## Unsupported absence claims

An empty panel is described as a category that never occurred, but the data were filtered out
or omitted from an intermediate table. Trace selection and missingness before interpreting
absence. Report attrition at the experimental-unit level as well as the row level when needed.

## Circular verification

An ordering check compares labels to the same ranks that generated them, so it cannot reveal
a wrong definition. Independently compute the intended quantity from source measurements and
check that the caption names that quantity. Do not expect a particular correlation in advance.

## Normalization masquerading as an effect

A block pattern comes from static group offsets rather than the claimed dynamics. Centering
and pool composition can also change correlation signs and magnitudes. Where relevant, test
a justified control and state which part of the pattern survives. Do not assume all negative
correlations are artifacts or remove legitimate group effects without scientific justification.

## Changes that did not reach the export

A formatter restores labels at save time; a title at a different alignment survives clearing;
a tight crop moves with a repositioned element. Inspect the rendered artifact after changes.
Source-code intent is not evidence that the delivered file changed.

## Unreadable overlays and distorted images

A composite label covers a caption already burned into an image, or a square resize stretches
a rectangular source. Inspect full-size artifacts and partially filled grid rows. Compare
source and displayed aspect ratios. Pixel measurements can support, not replace, inspection.

## Successful exit with missing output

A writer fails to open its output and drops frames without raising an exception. Verify the
explicit expected output list and decode relevant formats. If reliability testing is in scope,
exercise an isolated failure path; never test by altering the final deliverable directory.

## Export mismatches

The contract requires editable text but some labels are outlined; a TIFF carries an unintended
alpha channel; a video is cropped during encoding to satisfy even dimensions. Compare the
actual export with the specific contract. A valid codec or color mode for one venue need not
be valid for another. Recorded even dimensions alone cannot detect a prior crop.

## Misleading scales or legends

Adjacent panels use similar color bars with different limits, or a shared legend implies a
cross-panel category mapping that does not exist. Verify limits and category definitions;
require a shared scale or clear disclosure where comparison would otherwise mislead.

## Partial fixes and changed evidence

An author regenerates the image but leaves a superseded caption or data table. Or a second
render changes panels outside the requested fix. Recheck affected artifacts together and tie
the verdict to their current versions. A previous audit does not clear uninspected revisions.

## Incorrect auditor findings

A reviewer uses the wrong denominator or reads a label incorrectly. Require reproducible
evidence for findings and have the parent resolve disputes by checking sources. Reviewer
confidence is not sufficient evidence; unsupported claims must not drive figure changes.

## Personal information in exports

An SVG comment or PDF metadata field retains a creator name or private filesystem path even
though the visible figure is generic. Flag the field and artifact without repeating the value.
The author removes unintended metadata, regenerates if needed, and supplies the revised file
for inspection. Keep reusable audit examples and reports free of unrelated personal details.
