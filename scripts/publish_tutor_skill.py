#!/usr/bin/env python3
"""Embed the canonical tutor skill in the guide and publish its download."""

import argparse
import html
from pathlib import Path


PLACEHOLDER = "{{TUTOR_SKILL}}"


def publish_tutor_skill(source: Path, guide: Path) -> None:
    skill = source.read_bytes()
    text = skill.decode("utf-8")
    page = guide.read_text(encoding="utf-8")
    if page.count(PLACEHOLDER) != 1:
        raise ValueError("student guide must contain exactly one tutor skill placeholder")
    page = page.replace(PLACEHOLDER, html.escape(text))
    download = guide.parent / "skills" / "tutor" / "SKILL.md"
    download.parent.mkdir(parents=True, exist_ok=True)
    download.write_bytes(skill)
    guide.write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("guide", type=Path)
    args = parser.parse_args()
    publish_tutor_skill(args.source, args.guide)


if __name__ == "__main__":
    main()
