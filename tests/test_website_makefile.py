import os
import json
import re
import shutil
import socket
import subprocess
import tempfile
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
    def test_noon_release_controls_generated_pdf_and_homepage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            course = root / "course"
            site = root / "site"
            shutil.copytree(FIXTURE_COURSE, course)
            (course / "coursedesign/release-schedule.json").write_text(json.dumps([
                {"week": 1, "action": "validation", "date": "2026-09-14", "time": "12:00"}
            ]))
            # The session's old delay would incorrectly hold the key until 15:00.
            (course / "coursedesign/session-schedule.json").write_text(json.dumps([
                {"week": 1, "session_datetime": "2026-09-11T15:00:00+08:00", "solution_release_delay_days": 3}
            ]))
            compiler = root / "typst"
            compiler.write_text('#!/bin/bash\nprintf "%%PDF-1.7\\n" > "${@: -1}"\n')
            compiler.chmod(0o755)
            resolver = root / "resolve"
            resolver.write_text('#!/bin/bash\nexec python3 scripts/solution_release_state.py "$@" --now "$RELEASE_TEST_NOW"\n')
            resolver.chmod(0o755)
            env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}")
            for now, released in (("2026-09-14T11:59:59+08:00", False),
                                  ("2026-09-14T12:00:00+08:00", True),
                                  ("2026-09-14T11:59:59+08:00", False)):
                with self.subTest(now=now, released=released):
                    result = subprocess.run([
                        "make", "index", f"COURSE_SOURCE_DIR={course}", f"SITE_DIR={site}",
                        f"SOLUTION_RELEASE={resolver}",
                    ], cwd=ROOT, env=dict(env, RELEASE_TEST_NOW=now), capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual((site / "pdfs/week1-1.validation-solution.pdf").exists(), released)
                    self.assertEqual((site / "week1-1.validation-solution.html").exists(), released)
                    match = re.search(r'const pages = (\[.*?\]);', (site / 'index.html').read_text())
                    page = json.loads(match[1])[0]
                    self.assertEqual(page['solutionStatus'], 'released' if released else 'pending')
                    self.assertEqual(page['solutionAvailableAt'], '2026-09-14T12:00:00+08:00')
                    self.assertEqual(bool(page['solution']), released)
            (course / "coursedesign/release-schedule.json").write_text('[invalid JSON')
            result = subprocess.run([
                "make", "validation-pdfs", f"COURSE_SOURCE_DIR={course}", f"SITE_DIR={site}",
            ], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)

    def test_playground_html_and_assets_come_from_same_course_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            course = Path(tmp) / "course"
            site = Path(tmp) / "site"
            shutil.copytree(FIXTURE_COURSE, course)
            templates = course / ".github/templates"
            assets = templates / "assets/playground"
            assets.mkdir(parents=True)
            (templates / "playground.html").write_text("<title>{{COURSE_CODE}}</title><div id='course-demo'></div>")
            (assets / "shell.js").write_text("document.getElementById('course-demo');")
            subprocess.run(
                ["make", "playground", f"COURSE_SOURCE_DIR={course}", f"SITE_DIR={site}"],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            self.assertIn("id='course-demo'", (site / "playground.html").read_text())
            self.assertNotIn("{{COURSE_CODE}}", (site / "playground.html").read_text())
            self.assertEqual((assets / "shell.js").read_bytes(), (site / "assets/playground/shell.js").read_bytes())

    def test_pdf_build_stops_when_an_earlier_compilation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            compiler = Path(tempdir) / "typst"
            compiler.write_text('#!/bin/sh\ncase "$*" in *fail.typ*) exit 1;; esac\n')
            compiler.chmod(0o755)
            env = dict(os.environ, PATH=tempdir + os.pathsep + os.environ["PATH"])
            for target, variable in (("pdfs", "LEARNING_SHEETS"),
                                     ("validation-pdfs", "VALIDATION_FILES")):
                with self.subTest(target=target):
                    result = subprocess.run(
                        ["make", target, f"{variable}=week1/fail.typ week2/ok.typ",
                         f"SITE_DIR={tempdir}/site", "SOLUTION_KEY_POLICY=none"],
                        cwd=ROOT, env=env, capture_output=True, text=True,
                    )
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertNotIn("→ week2/ok.typ", result.stdout)

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
