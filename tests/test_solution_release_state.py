import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "solution_release_state.py"


class SolutionReleaseStateTest(unittest.TestCase):
    def test_holiday_weeks_share_the_explicit_monday_release(self) -> None:
        with self._schedule(*[
            {"week": week, "action": "validation", "date": "2026-10-12", "time": "12:00"}
            for week in (4, 5)
        ]) as schedule:
            for week in (4, 5):
                self.assertEqual(self._status(schedule, week=week, now="2026-10-12T11:59:59+08:00"), "pending")
                self.assertEqual(self._status(schedule, week=week, now="2026-10-12T12:00:00+08:00"), "released")

    def test_learning_and_test_events_do_not_release_validation(self) -> None:
        with self._schedule(
            {"week": 2, "action": "learning-sheet", "date": "2026-09-11", "time": "15:00"},
            {"week": 2, "action": "test-answer", "date": "2026-09-18", "time": "16:00"},
        ) as schedule:
            self.assertEqual(self._status(schedule, week=2, now="2026-09-20T12:00:00+08:00"), "pending")

    def test_duplicate_and_invalid_releases_fail_closed(self) -> None:
        event = {"week": 2, "action": "validation", "date": "2026-09-14", "time": "12:00"}
        for entries in ([event, event], [dict(event, time="invalid")]):
            with self.subTest(entries=entries), self._schedule(*entries) as schedule:
                result = subprocess.run([
                    "python3", str(SCRIPT), "is-released", "--schedule", str(schedule),
                    "--week", "2", "--now", "2026-09-14T12:00:00+08:00",
                ], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_available_at_matches_explicit_schedule(self) -> None:
        with self._schedule({"week": 2, "action": "validation", "date": "2026-09-14", "time": "12:00"}) as schedule:
            result = subprocess.run([
                "python3", str(SCRIPT), "available-at", "--schedule", str(schedule), "--week", "2",
            ], check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(), "2026-09-14T12:00:00+08:00")

    def test_session_date_alone_cannot_release_answers(self) -> None:
        with self._schedule({"week": 1, "session_datetime": "TBD"}) as schedule:
            status = self._status(schedule, week=1)

        self.assertEqual(status, "pending")

    def test_schedule_releases_answers_at_noon_beijing(self) -> None:
        with self._schedule(
            {
                "week": 2,
                "action": "validation", "date": "2026-09-14", "time": "12:00",
            }
        ) as schedule:
            before = self._status(schedule, week=2, now="2026-09-14T11:59:59+08:00")
            at_release = self._status(
                schedule,
                week=2,
                now="2026-09-14T04:00:00Z",
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
        path = Path(tempdir.name) / "release-schedule.json"
        path.write_text(json.dumps(list(entries)), encoding="utf-8")

        class ScheduleContext:
            def __enter__(self) -> Path:
                return path

            def __exit__(self, *args: object) -> None:
                tempdir.cleanup()

        return ScheduleContext()


if __name__ == "__main__":
    unittest.main()
