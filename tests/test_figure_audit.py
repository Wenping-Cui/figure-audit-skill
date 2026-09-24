"""Regression tests for audit results that could mislead a reviewer."""
import contextlib
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "figure_audit", Path(__file__).resolve().parents[1] / "scripts" / "figure_audit.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

FONT_HEADER = ("name                                 type              encoding         emb sub uni object ID\n"
               "------------------------------------ ----------------- ---------------- --- --- --- ---------\n")


def font_row(name, ftype, emb):
    return f"{name:<36} {ftype:<17} {'Identity-H':<16} {emb:<3} yes yes      8  0\n"


def done(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class AuditChecks(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        audit.RESULTS.clear()
        self.capture = contextlib.redirect_stdout(io.StringIO())
        self.capture.__enter__()
        self.addCleanup(self.capture.__exit__, None, None, None)

    def file(self, name, content):
        path = self.root / name
        path.write_text(content)
        return path

    def status(self, check):
        return next(status for status, label, _ in audit.RESULTS if label.startswith(check))

    # ------------------------------------------------------------------ PDF fonts
    def font_probe(self, output, returncode=0, stderr=""):
        path = self.file("figure.pdf", "%PDF-1.4\n")
        with patch.object(audit.shutil, "which", return_value="pdffonts"), \
                patch.object(audit.subprocess, "run", return_value=done(output, returncode, stderr)):
            audit.cmd_fonts(path)

    def test_embedded_font_passes(self):
        self.font_probe(FONT_HEADER + font_row("ExampleFont", "CID TrueType", "yes"))
        self.assertEqual(self.status("fonts embedded"), "PASS")

    def test_unembedded_font_fails_despite_uni_yes(self):
        self.font_probe(FONT_HEADER + font_row("ExampleFont", "CID TrueType", "no"))
        self.assertEqual(self.status("fonts embedded"), "FAIL")

    def test_type3_fails(self):
        self.font_probe(FONT_HEADER + font_row("ExampleFont", "Type 3", "yes"))
        self.assertEqual(self.status("font type"), "FAIL")

    def test_failed_font_probe_cannot_pass(self):
        self.font_probe("", returncode=1, stderr="Couldn't open file")
        self.assertEqual(self.status("fonts"), "FAIL")

    def test_recoverable_pdffonts_warning_does_not_fail(self):
        self.font_probe(FONT_HEADER + font_row("ExampleFont", "CID TrueType", "yes"),
                        stderr="Syntax Error (123): Illegal character")
        self.assertEqual(self.status("pdffonts warnings"), "INFO")
        self.assertEqual(self.status("fonts embedded"), "PASS")

    def test_no_font_rows_is_reported_not_passed(self):
        self.font_probe(FONT_HEADER)
        self.assertEqual(self.status("fonts"), "INFO")
        self.assertNotIn("PASS", {s for s, _, _ in audit.RESULTS})

    # ------------------------------------------------------------------ inventory
    def test_partial_format_set_fails(self):
        self.file("figure.svg", "x")
        self.file("figure.pdf", "x")
        audit.cmd_inventory(self.root, ["svg", "pdf", "png"], [])
        self.assertEqual(self.status("formats figure"), "FAIL")

    def test_expected_stem_missing_everywhere_fails(self):
        audit.cmd_inventory(self.root, ["svg", "pdf"], ["figure1"])
        self.assertEqual(self.status("expected figure1"), "FAIL")

    def test_tif_alias_matches_tiff(self):
        self.file("figure.tif", "x")
        audit.cmd_inventory(self.root, ["tiff"], ["figure"])
        self.assertEqual(self.status("expected figure"), "PASS")

    def test_empty_export_fails(self):
        self.file("figure.svg", "")
        audit.cmd_inventory(self.root, ["svg"], [])
        self.assertEqual(self.status("non-empty"), "FAIL")

    def test_formats_from_different_directories_cannot_complete_each_other(self):
        (self.root / "a").mkdir()
        (self.root / "b").mkdir()
        self.file("a/figure.svg", "x")
        self.file("b/figure.pdf", "x")
        audit.cmd_inventory(self.root, ["svg", "pdf"], ["a/figure"])
        self.assertEqual(self.status("expected a/figure"), "FAIL")

    def test_nonpositive_svg_dimensions_fail(self):
        path = self.file("figure.svg", '<svg width="-10pt" height="0pt"/>')
        audit.cmd_geometry(path, 180, 247)
        self.assertEqual(self.status("geometry"), "FAIL")

    def test_directory_command_rejects_a_file(self):
        path = self.file("figure.svg", "<svg/>")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(audit.main(["inventory", str(path)]), 2)

    # ------------------------------------------------------------------ SVG text
    def test_mixed_live_and_outlined_text_fails(self):
        path = self.file("figure.svg",
                         '<svg width="100pt" height="50pt"><defs><path id="ExampleFont-41" d="M0 0"/>'
                         '</defs><text font-size="8pt">Live</text><use href="#ExampleFont-41"/></svg>')
        audit.cmd_text(path, 5.5)
        self.assertEqual(self.status("live text"), "FAIL")

    def test_font_size_includes_ancestor_scale(self):
        path = self.file("figure.svg",
                         '<svg width="100pt" height="50pt" viewBox="0 0 100 50">'
                         '<g transform="scale(0.5)"><text font-size="8">Small</text></g></svg>')
        audit.cmd_text(path, 5.5)
        self.assertEqual(self.status("min font"), "FAIL")

    def test_viewbox_only_svg_size_is_a_gap(self):
        path = self.file("figure.svg", '<svg viewBox="0 0 100 50"><text font-size="8">A</text></svg>')
        audit.cmd_text(path, 5.5)
        self.assertEqual(self.status("min font"), "SKIP")

    # ------------------------------------------------------------------ svgdiff
    def test_svg_id_renaming_preserves_equivalence(self):
        svg = '<svg><defs><path id="p1" d="M0 0L1 1"/></defs><use href="#p1"/></svg>'
        self.assertEqual(audit.normalise_svg(svg), audit.normalise_svg(svg.replace("p1", "random")))

    def test_svg_changed_glyph_reference_is_detected(self):
        svg = ('<svg><defs><path id="a" d="M0 0L1 1"/><path id="b" d="M0 0L2 2"/>'
               '</defs><use href="#a"/></svg>')
        a = self.file("a.svg", svg)
        b = self.file("b.svg", svg.replace('href="#a"', 'href="#b"'))
        audit.cmd_svgdiff(a, b)
        self.assertEqual(self.status("svg identical"), "FAIL")

    def test_svg_changed_clip_reference_is_detected(self):
        svg = ('<svg><defs><clipPath id="a"><rect width="1"/></clipPath>'
               '<clipPath id="b"><rect width="2"/></clipPath></defs>'
               '<rect clip-path="url(#a)" width="3"/></svg>')
        self.assertNotEqual(audit.normalise_svg(svg),
                            audit.normalise_svg(svg.replace("url(#a)", "url(#b)")))

    def test_svg_visible_text_is_not_normalised(self):
        a = self.file("a.svg", '<svg><text>m12345678</text></svg>')
        b = self.file("b.svg", '<svg><text>m87654321</text></svg>')
        audit.cmd_svgdiff(a, b)
        self.assertEqual(self.status("svg identical"), "FAIL")

    def test_invalid_svg_fails(self):
        a = self.file("a.svg", '<svg>')
        b = self.file("b.svg", '<svg/>')
        audit.cmd_svgdiff(a, b)
        self.assertEqual(self.status("svg parse"), "FAIL")

    # ------------------------------------------------------------------ video
    def video_probe(self, probe_out, codec="h264"):
        with patch.object(audit.shutil, "which", return_value="ffprobe"), \
                patch.object(audit.subprocess, "run", side_effect=[done(probe_out), done(), done()]):
            audit.cmd_video(self.root / "video.mp4", False, codec)

    def test_unknown_video_size_is_a_gap(self):
        self.video_probe("codec_name=h264\nwidth=N/A\nheight=N/A\nnb_frames=N/A\n")
        self.assertEqual(self.status("video parity"), "SKIP")

    def test_odd_video_size_fails(self):
        self.video_probe("codec_name=h264\nwidth=321\nheight=180\nnb_frames=10\n")
        self.assertEqual(self.status("video parity"), "FAIL")

    def test_contract_codec_is_honoured(self):
        self.video_probe("codec_name=vp9\nwidth=320\nheight=180\nnb_frames=10\n", codec="vp9")
        self.assertEqual(self.status("video codec"), "PASS")

    # ------------------------------------------------------------------ staleness
    def test_output_older_than_generator_fails(self):
        out = self.file("figure.svg", "<svg/>")
        generator = self.file("generator.py", "# fixture")
        os.utime(out, (0, 0))
        audit.cmd_stale(self.root, [generator])
        self.assertEqual(self.status("stale"), "FAIL")

    def test_staleness_without_outputs_is_a_gap(self):
        generator = self.file("generator.py", "# fixture")
        audit.cmd_stale(self.root, [generator])
        self.assertEqual(self.status("stale"), "SKIP")

    # ------------------------------------------------------------------ exit status
    def test_skip_without_failure_exits_incomplete(self):
        audit.record("PASS", "a", "")
        audit.record("SKIP", "b", "")
        self.assertEqual(audit.summarise(allow_skip=False), 3)
        self.assertEqual(audit.summarise(allow_skip=True), 0)

    def test_nothing_checked_is_incomplete_even_with_allow_skip(self):
        audit.record("SKIP", "b", "")
        self.assertEqual(audit.summarise(allow_skip=True), 3)

    def test_failure_wins(self):
        audit.record("FAIL", "a", "")
        audit.record("SKIP", "b", "")
        self.assertEqual(audit.summarise(allow_skip=True), 1)


if __name__ == "__main__":
    unittest.main()
