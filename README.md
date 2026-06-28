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
  --schedule tests/fixtures/course/coursedesign/session-schedule.json \
  --policy schedule
```

## Private Source Build

```bash
make build COURSE_SOURCE_DIR=vendor/course-source SOLUTION_KEY_POLICY=schedule
```

`SOLUTION_KEY_POLICY=schedule` publishes a week's validation answer key only
after that week's configured session time plus two days. `TBD` session dates do
not publish answer keys.

## Required Secrets

- `COURSE_SOURCE_DEPLOY_KEY`: private SSH key for a read-only deploy key on
  `TDAA-Go/LinearAlgebra2026`.

The private course repository separately needs `SITE_DISPATCH_TOKEN` so it can
trigger this repository's `repository_dispatch` deploy workflow.
