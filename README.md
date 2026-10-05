# UFUG 2103 Linear Algebra Site

Public GitHub Pages site for the Fall 2026 UFUG 2103 Linear Algebra materials.

This repository contains the open-source website shell only. The canonical
course materials live in the private `TDAA-Go/LinearAlgebra2026` repository.
The Pages workflow checks out a narrow read-only subset of that private source
at build time and publishes only generated public artifacts.

## Local Fixture Build

```bash
python3 -m unittest discover
make build COURSE_SOURCE_DIR=tests/fixtures/course SOLUTION_KEY_POLICY=schedule
scripts/check_public_site_artifacts.py _site \
  --schedule tests/fixtures/course/coursedesign/release-schedule.json \
  --policy schedule
```

## Private Source Build

```bash
make build COURSE_SOURCE_DIR=vendor/course-source SOLUTION_KEY_POLICY=schedule
```

`SOLUTION_KEY_POLICY=schedule` publishes a week's validation answer key only
at the `validation` event in the course `coursedesign/release-schedule.json`,
using Beijing time. A missing event keeps the answer key unpublished.
`session-schedule.json` controls the homepage current-week indicator only.
The private course release workflow checks the live homepage, answer viewer,
and PDF, dispatches a rebuild if publication is incomplete, and verifies it
before reporting success. Hourly site builds remain a backup.

## Required Secrets

- `COURSE_SOURCE_TOKEN`: token that can read the private
  `TDAA-Go/LinearAlgebra2026` repository.

The private course repository separately needs `SITE_DISPATCH_TOKEN` so it can
trigger this repository's `repository_dispatch` deploy workflow.

## Student tutor skill

The Student guide embeds the course source's `.claude/skills/tutor/SKILL.md`
and offers the same file at `skills/tutor/SKILL.md`. Edit the course source,
not the generated page or download. The build HTML-escapes the instructions
and copies only this explicitly public skill, not the other agent files.
