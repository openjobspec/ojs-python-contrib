# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-09-02

### Added

- Added real `SyncClient` worker-operation coverage for the Celery broker and
  result backend using the SDK fake transport.

### Fixed

- Corrected release metadata so each integration package reports version 0.5.0.
- Added locked Python 3.11-3.13 CI, publish dry-runs, and clean wheel smoke tests.
- Replaced Celery calls to nonexistent SDK methods with supported OJS
  `fetch`, `ack`, `nack`, and queue-statistics operations.

## [0.4.1] - 2026-04-21

### Fixed

- Documented the v0.4.0 integration release.

## [0.4.0] - 2026-04-20

### Changed

- Middleware integration updated for Django 5.2, FastAPI 0.115, Flask 3.1
- Aligned with openjobspec v0.4.0

## [0.2.0] - 2026-02-28

### Changed

- Unified the five integration package versions at 0.2.0.
- Promoted `openjobspec-django` to beta.

### Improved

- Expanded test coverage for Flask, FastAPI, Celery, and SQLAlchemy packages

## [0.1.0] - 2025-01-01

### Added

- Initial release of `openjobspec-django` (alpha)
- Initial release of `openjobspec-flask` (alpha)
- Initial release of `openjobspec-fastapi` (alpha)
- Initial release of `openjobspec-celery` (alpha)
- Initial release of `openjobspec-sqlalchemy` (alpha)
