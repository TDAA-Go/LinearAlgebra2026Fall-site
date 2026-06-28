import re
import socket
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_COURSE = ROOT / "tests" / "fixtures" / "course"


def run_make_dry_run(*args: str) -> str:
    result = subprocess.run(
        ["make", "-n", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout + result.stderr


def run_make_dry_run_result(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "-n", *args],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class WebsiteMakefileTest(unittest.TestCase):
    def test_build_reads_course_sources_from_configured_source_dir(self) -> None:
        output = run_make_dry_run(
            "validation-pdfs",
            f"COURSE_SOURCE_DIR={FIXTURE_COURSE}",
            "SOLUTION_KEY_POLICY=schedule",
        )

        self.assertIn(f'typst compile --root "{FIXTURE_COURSE}"', output)
        self.assertIn("scripts/solution_release_state.py is-released", output)
        self.assertIn(str(FIXTURE_COURSE / "week1" / "1.validation.typ"), output)

    def test_serve_only_honors_configured_port(self) -> None:
        output = run_make_dry_run("serve-only", "PORT=8123")

        self.assertIn("http://localhost:8123", output)
        self.assertRegex(output, r"http\.server\s+8123\b")

    def test_serve_only_uses_next_port_when_requested_port_is_busy(self) -> None:
        busy_port = self._bind_test_port()
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("::", busy_port))
            listener.listen(1)

            output = run_make_dry_run("serve-only", f"PORT={busy_port}")

        match = re.search(r"http://localhost:(\d+)", output)
        self.assertIsNotNone(match)
        selected_port = int(match.group(1))
        self.assertGreater(selected_port, busy_port)
        self.assertRegex(output, rf"http\.server\s+{selected_port}\b")

    def test_output_pdfs_exports_weekly_packet_to_timestamped_folder(self) -> None:
        result = run_make_dry_run_result("output-pdfs")

        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertRegex(
            output,
            r"output/pdf/linear-algebra-weekly-pdfs-\d{8}-\d{6}",
        )
        self.assertIn('mkdir -p "$packet_dir/$week"', output)
        self.assertIn(
            f'typst compile --root "{FIXTURE_COURSE}" "$src" "$packet_dir/$week/$pdf_name"',
            output,
        )
        self.assertIn("1.learning-sheet.typ", output)
        self.assertIn("1.test.typ", output)
        self.assertIn("1.validation.typ", output)
        self.assertNotIn("1.test.B.typ", output)

    def test_index_uses_only_learning_sheet_viewers(self) -> None:
        output = run_make_dry_run("index")

        self.assertIn(
            "find _site -maxdepth 1 -type f -name 'week*-*.html' -delete",
            output,
        )
        self.assertIn("for pdf in _site/pdfs/*learning-sheet.pdf", output)
        self.assertIn(
            "find _site -maxdepth 1 -type f "
            "-name 'week*-*.learning-sheet.html'",
            output,
        )
        self.assertNotIn("grep -oP", output)

    def test_tdaa_intro_is_footer_link_not_top_nav(self) -> None:
        templates = [
            ROOT / ".github/templates/index.html",
            ROOT / ".github/templates/student-guide.html",
            ROOT / ".github/templates/about.html",
            ROOT / ".github/templates/setup-guide.html",
            ROOT / ".github/templates/instructor-guide.html",
        ]

        for template in templates:
            html = template.read_text()
            self.assertNotIn('class="nav-link">About TDAA', html, template)
            self.assertNotIn('class="nav-link active">About TDAA', html, template)
            self.assertIn('href="about.html">TDAA introduction</a>', html, template)

    def test_student_guide_explains_validation_vs_test(self) -> None:
        html = (ROOT / ".github/templates/student-guide.html").read_text()

        self.assertIn("How does the validation set differ from the test?", html)
        self.assertIn("open-resource", html)
        self.assertIn("graded closed-book check", html)
        self.assertIn("different questions", html)

    def test_index_template_uses_solution_release_metadata(self) -> None:
        html = (ROOT / ".github/templates/index.html").read_text()

        self.assertIn("solutionAvailableAt", html)
        self.assertIn("Answer key · after", html)

    def _bind_test_port(self) -> int:
        for port in range(45123, 45223):
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as candidate:
                candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    candidate.bind(("::", port))
                except PermissionError as exc:
                    self.skipTest(f"socket bind not permitted: {exc}")
                except OSError:
                    continue
                return port
        self.fail("no free test port found")


if __name__ == "__main__":
    unittest.main()
