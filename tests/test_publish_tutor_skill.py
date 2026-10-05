import html
import tempfile
import unittest
from pathlib import Path

from scripts.publish_tutor_skill import publish_tutor_skill


class PublishTutorSkillTest(unittest.TestCase):
    def test_download_and_escaped_preview_share_the_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.md"
            guide = root / "site" / "student-guide.html"
            guide.parent.mkdir()
            payload = '# Tutor\nUse x < y & "explain".\n<script>alert(1)</script>\n'
            source.write_text(payload, encoding="utf-8")
            guide.write_text("<code>{{TUTOR_SKILL}}</code>", encoding="utf-8")
            publish_tutor_skill(source, guide)
            self.assertEqual(
                (guide.parent / "skills/tutor/SKILL.md").read_bytes(),
                source.read_bytes(),
            )
            self.assertEqual(
                guide.read_text(encoding="utf-8"),
                "<code>" + html.escape(payload) + "</code>",
            )

    def test_invalid_template_fails_before_publishing(self):
        for template in ("<code></code>", "{{TUTOR_SKILL}}{{TUTOR_SKILL}}"):
            with self.subTest(template=template), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "source.md"
                source.write_text("# Tutor", encoding="utf-8")
                guide = root / "student-guide.html"
                guide.write_text(template, encoding="utf-8")
                with self.assertRaises(ValueError):
                    publish_tutor_skill(source, guide)
                self.assertFalse((root / "skills").exists())
                self.assertEqual(guide.read_text(encoding="utf-8"), template)

    def test_missing_source_fails_before_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide = root / "student-guide.html"
            guide.write_text("{{TUTOR_SKILL}}", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                publish_tutor_skill(root / "missing.md", guide)
            self.assertFalse((root / "skills").exists())


if __name__ == "__main__":
    unittest.main()
