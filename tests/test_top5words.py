import tempfile
from pathlib import Path
import unittest

import top5words


class PaperTitleParserTests(unittest.TestCase):
    def test_cvpr_parser_accepts_current_markup_and_nested_text(self):
        source = """
        <dl>
          <dt class="ptitle"><br><a href="paper.html">Learning <em>Useful</em> Images</a></dt>
          <dd>Authors who should not be captured</dd>
        </dl>
        """
        self.assertEqual(
            top5words.parse_paper_titles(source, "cvpr"),
            ["Learning Useful Images"],
        )

    def test_kesen_parser_ignores_comment_templates(self):
        source = """
        <!-- <dt><b>Template title</b></dt> -->
        <dl><dt><B>Real-Time Rendering &amp; Light</B><a href="#">PDF</a></dt></dl>
        """
        self.assertEqual(
            top5words.parse_paper_titles(source, "kesen"),
            ["Real-Time Rendering & Light"],
        )

    def test_cvpr_day_parser_resolves_legacy_links_and_deduplicates(self):
        source = """
        <a href="CVPR2020.py?day=2020-06-16">Tuesday</a>
        <a href="CVPR2020.py?day=2020-06-16">Tuesday again</a>
        <a href="CVPR2020.py?day=all">All</a>
        <a href="https://example.com/?day=2020-06-17">External</a>
        <a href="CVPR2020.py?day=2020-06-18">Thursday</a>
        """
        self.assertEqual(
            top5words.parse_cvpr_day_urls(
                source, "https://openaccess.thecvf.com/CVPR2020"
            ),
            [
                "https://openaccess.thecvf.com/CVPR2020.py?day=2020-06-16",
                "https://openaccess.thecvf.com/CVPR2020.py?day=2020-06-18",
            ],
        )


class WordProcessingTests(unittest.TestCase):
    def test_tokenization_normalizes_unicode_and_drops_noise(self):
        words = top5words.title_words(
            ["A 3D Artist’s Model—Using Light &amp; Shadow: Fast, Robust!", "Café"]
        )
        self.assertEqual(
            words,
            ["artist's", "model", "light", "shadow", "fast", "robust", "café"],
        )
        self.assertNotIn("", words)

    def test_top_words_keeps_first_seen_order_for_ties(self):
        self.assertEqual(
            top5words.top_words(["mesh", "light", "mesh", "ray", "light"], 2),
            [("mesh", 2), ("light", 2)],
        )


class OutputTests(unittest.TestCase):
    def test_session_uses_source_compatible_browser_profile(self):
        session = top5words.create_session()
        try:
            self.assertTrue(session.headers["User-Agent"].startswith("Mozilla/5.0"))
            self.assertEqual(session.headers["Accept"], "*/*")
        finally:
            session.close()

    def test_atomic_write_replaces_complete_utf8_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "output.txt"
            target.write_text("old", encoding="utf-8")
            top5words.atomic_write(target, "new café\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "new café\n")

    def test_cvpr_uses_all_papers_endpoint(self):
        self.assertEqual(
            top5words.cvpr_url(2025),
            "https://openaccess.thecvf.com/CVPR2025?day=all",
        )

    def test_rendered_page_uses_original_template_and_escapes_words(self):
        result = top5words.YearResult(
            year=2025,
            source_url="https://example.test/?a=1&b=2",
            paper_count=2,
            words=("mesh", "a<b"),
            top_words=(("a<b", 2), ("mesh", 1)),
        )
        page = top5words.render_page(top5words.CONFERENCES["sig"], [result], [])
        self.assertIn("<html>", page)
        self.assertIn('<table class="ex">', page)
        self.assertIn("a&lt;b", page)
        self.assertNotIn(">a<b<", page)


if __name__ == "__main__":
    unittest.main()
