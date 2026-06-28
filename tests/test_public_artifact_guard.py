import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_public_site_artifacts.py"


class PublicArtifactGuardTest(unittest.TestCase):
    def test_rejects_raw_sources_and_private_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            site = Path(tempdir)
            (site / "index.html").write_text("<html></html>", encoding="utf-8")
            (site / "week1.typ").write_text("#set text()", encoding="utf-8")
            (site / "reference").mkdir()
            (site / "reference" / "textbook.md").write_text("private", encoding="utf-8")

            result = self._run_guard(site)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("week1.typ", result.stderr)
        self.assertIn("reference", result.stderr)

    def test_rejects_unreleased_validation_solution_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            site = Path(tempdir)
            (site / "pdfs").mkdir()
            (site / "pdfs" / "week1-1.validation-solution.pdf").write_bytes(b"%PDF")
            schedule = site / "session-schedule.json"
            schedule.write_text(
                '[{"week": 1, "session_datetime": "TBD"}]',
                encoding="utf-8",
            )

            result = self._run_guard(
                site,
                "--schedule",
                str(schedule),
                "--policy",
                "schedule",
                "--now",
                "2026-09-10T10:30:00+08:00",
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unreleased answer key", result.stderr)

    def test_accepts_released_validation_solution_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            site = Path(tempdir)
            (site / "pdfs").mkdir()
            (site / "pdfs" / "week1-1.validation-solution.pdf").write_bytes(b"%PDF")
            schedule = site / "session-schedule.json"
            schedule.write_text(
                (
                    '[{"week": 1, "session_datetime": "2026-09-08T10:30:00+08:00", '
                    '"solution_release_delay_days": 2}]'
                ),
                encoding="utf-8",
            )

            result = self._run_guard(
                site,
                "--schedule",
                str(schedule),
                "--policy",
                "schedule",
                "--now",
                "2026-09-10T10:30:00+08:00",
            )

        self.assertEqual(result.returncode, 0, result.stderr)

    def _run_guard(self, site: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), str(site), *extra_args],
            cwd=ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )


if __name__ == "__main__":
    unittest.main()
