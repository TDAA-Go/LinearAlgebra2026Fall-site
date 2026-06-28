#!/usr/bin/env python3
"""Decide whether a week's validation answer key is public."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReleaseState:
    status: str
    available_at: datetime | None

    @property
    def is_released(self) -> bool:
        return self.status == "released"


def release_state(
    *,
    schedule_path: Path,
    policy: str,
    week: int,
    now: datetime | None = None,
) -> ReleaseState:
    if policy == "none":
        return ReleaseState("hidden", None)
    if policy == "all":
        return ReleaseState("released", None)
    if policy != "schedule":
        raise ValueError(f"unknown solution key policy: {policy}")

    entry = _entry_for_week(_load_schedule(schedule_path), week)
    if entry is None:
        return ReleaseState("pending", None)

    session_time = _parse_datetime(entry.get("session_datetime"))
    if session_time is None:
        return ReleaseState("pending", None)

    delay_days = _delay_days(entry)
    available_at = session_time + timedelta(days=delay_days)
    now = now or datetime.now(timezone.utc)
    if _aware(now) >= _aware(available_at):
        return ReleaseState("released", available_at)
    return ReleaseState("pending", available_at)


def _load_schedule(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("rb") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return [entry for entry in data if isinstance(entry, dict)]


def _entry_for_week(schedule: list[dict[str, Any]], week: int) -> dict[str, Any] | None:
    for entry in schedule:
        if entry.get("week") == week:
            return entry
    return None


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or value.upper() == "TBD":
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _delay_days(entry: dict[str, Any]) -> int:
    value = entry.get("solution_release_delay_days", 2)
    try:
        delay = int(value)
    except (TypeError, ValueError):
        return 2
    return max(delay, 0)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _parse_now(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = _parse_datetime(value)
    if parsed is None:
        raise ValueError(f"invalid --now datetime: {value}")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("status", "is-released", "available-at"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--schedule", required=True, type=Path)
        subparser.add_argument(
            "--policy",
            choices=("none", "schedule", "all"),
            default="schedule",
        )
        subparser.add_argument("--week", required=True, type=int)
        subparser.add_argument("--now")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        state = release_state(
            schedule_path=args.schedule,
            policy=args.policy,
            week=args.week,
            now=_parse_now(args.now),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"solution release state error: {exc}", file=sys.stderr)
        return 2

    if args.command == "status":
        print(state.status)
        return 0
    if args.command == "available-at":
        if state.available_at is not None:
            print(state.available_at.isoformat())
        return 0
    if args.command == "is-released":
        return 0 if state.is_released else 1
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
