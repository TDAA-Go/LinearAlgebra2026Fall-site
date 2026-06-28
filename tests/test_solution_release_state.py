import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "solution_release_state.py"


class SolutionReleaseStateTest(unittest.TestCase):
    def test_tbd_session_date_keeps_solution_pending(self) -> None:
        with self._schedule({"week": 1, "session_datetime": "TBD"}) as schedule:
            status = self._status(schedule, week=1)

        self.assertEqual(status, "pending")

    def test_schedule_releases_solution_two_days_after_session(self) -> None:
        with self._schedule(
            {
                "week": 2,
                "session_datetime": "2026-09-08T10:30:00+08:00",
                "solution_release_delay_days": 2,
            }
        ) as schedule:
            before = self._status(schedule, week=2, now="2026-09-10T10:29:00+08:00")
            at_release = self._status(
                schedule,
                week=2,
                now="2026-09-10T10:30:00+08:00",
            )

        self.assertEqual(before, "pending")
        self.assertEqual(at_release, "released")

    def test_policy_none_and_all_override_schedule(self) -> None:
        with self._schedule({"week": 3, "session_datetime": "TBD"}) as schedule:
            hidden = self._status(schedule, week=3, policy="none")
            released = self._status(schedule, week=3, policy="all")

        self.assertEqual(hidden, "hidden")
        self.assertEqual(released, "released")

    def test_is_released_exit_code_matches_status(self) -> None:
        with self._schedule({"week": 4, "session_datetime": "TBD"}) as schedule:
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "is-released",
                    "--schedule",
                    str(schedule),
                    "--policy",
                    "schedule",
                    "--week",
                    "4",
                    "--now",
                    "2026-09-10T10:30:00+08:00",
                ],
                cwd=ROOT,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")

    def _status(
        self,
        schedule: Path,
        *,
        week: int,
        policy: str = "schedule",
        now: str = "2026-09-10T10:30:00+08:00",
    ) -> str:
        result = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "status",
                "--schedule",
                str(schedule),
                "--policy",
                policy,
                "--week",
                str(week),
                "--now",
                now,
            ],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.stdout.strip()

    def _schedule(self, *entries: dict[str, object]):
        tempdir = tempfile.TemporaryDirectory()
        path = Path(tempdir.name) / "session-schedule.json"
        path.write_text(json.dumps(list(entries)), encoding="utf-8")

        class ScheduleContext:
            def __enter__(self) -> Path:
                return path

            def __exit__(self, *args: object) -> None:
                tempdir.cleanup()

        return ScheduleContext()


if __name__ == "__main__":
    unittest.main()
