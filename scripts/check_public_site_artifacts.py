#!/usr/bin/env python3
"""Fail if the generated Pages artifact contains private course material."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from solution_release_state import release_state


PRIVATE_DIRS = {"course-source", "reference", "textbook", "vendor"}
RAW_SUFFIXES = {".toml", ".typ"}
TEST_ARTIFACT = re.compile(r"(^|[.-])test(\.|-|$)", re.IGNORECASE)
SOLUTION_PDF = re.compile(r"week(?P<week>\d+)-.*\.validation-solution\.pdf$")


def check_site(
    site_dir: Path,
    *,
    schedule: Path | None = None,
    policy: str = "schedule",
    now: datetime | None = None,
) -> list[str]:
    errors: list[str] = []
    if not site_dir.exists():
        return [f"{site_dir} does not exist"]

    for path in sorted(site_dir.rglob("*")):
        if path == site_dir:
            continue
        rel = path.relative_to(site_dir)
        parts = rel.parts

        if any(part.startswith(".") for part in parts):
            errors.append(f"hidden file is not public-safe: {rel}")

        if any(part in PRIVATE_DIRS for part in parts):
            errors.append(f"private directory leaked into site: {rel}")

        if path.is_file() and path.suffix in RAW_SUFFIXES:
            errors.append(f"raw source file leaked into site: {rel}")

        if path.is_file() and path.suffix in {".html", ".pdf"} and TEST_ARTIFACT.search(path.name):
            errors.append(f"test artifact leaked into site: {rel}")

        match = SOLUTION_PDF.match(path.name)
        if path.is_file() and match:
            week = int(match.group("week"))
            state = release_state(
                schedule_path=schedule or Path("__missing_session_schedule__.json"),
                policy=policy,
                week=week,
                now=now,
            )
            if not state.is_released:
                errors.append(f"unreleased answer key leaked into site: {rel}")

    return errors


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_dir", type=Path)
    parser.add_argument("--schedule", type=Path)
    parser.add_argument(
        "--policy",
        choices=("none", "schedule", "all"),
        default="schedule",
    )
    parser.add_argument("--now")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    now = None
    if args.now:
        try:
            now = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        except ValueError:
            print(f"invalid --now datetime: {args.now}", file=sys.stderr)
            return 2

    try:
        errors = check_site(
            args.site_dir,
            schedule=args.schedule,
            policy=args.policy,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001 - CLI guard should report and fail closed.
        print(f"artifact guard error: {exc}", file=sys.stderr)
        return 2

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
