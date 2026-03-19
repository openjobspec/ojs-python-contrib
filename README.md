# Open Job Spec — Python Contrib
[![Stability: beta](https://img.shields.io/badge/stability-beta-yellow.svg)](https://github.com/openjobspec/openjobspec/blob/main/STABILITY.md)

[![CI](https://github.com/openjobspec/ojs-python-contrib/actions/workflows/ci.yml/badge.svg)](https://github.com/openjobspec/ojs-python-contrib/actions/workflows/ci.yml)

Community framework integrations for the [OJS Python SDK](https://github.com/openjobspec/ojs-python-sdk).

## Provided Integrations

| Status | Integration | Description |
|--------|-------------|-------------|
| alpha  | [Django](./ojs-django/README.md) | Django app with management commands, settings integration, and `transaction.on_commit()` enqueue |
| alpha  | [Flask](./ojs-flask/README.md) | Flask extension with app factory pattern support |
| alpha  | [FastAPI](./ojs-fastapi/README.md) | FastAPI dependency injection and lifespan management |
| alpha  | [Celery](./ojs-celery/README.md) | Celery-compatible `@task` decorator for seamless migration |
| alpha  | [SQLAlchemy](./ojs-sqlalchemy/README.md) | Transactional job enqueue via SQLAlchemy session events |

Status definitions: `alpha` (API may change), `beta` (API stable, not battle-tested), `stable` (production-ready).

## Installation

Each integration is a separate PyPI package:

```bash
pip install openjobspec-django
pip install openjobspec-flask
pip install openjobspec-fastapi
pip install openjobspec-celery
pip install openjobspec-sqlalchemy
```

## Package Naming

- **PyPI packages**: `openjobspec-{framework}` (e.g., `openjobspec-django`)
- **Import names**: `ojs_{framework}` (e.g., `from ojs_django import enqueue_after_commit`)

## Development

```bash
# Install all packages in development mode
make install-all

# Run all tests
make test-all

# Lint all packages
make lint-all

# Format all packages
make format-all
```

## Requirements

- Python >= 3.11
- [openjobspec](https://github.com/openjobspec/ojs-python-sdk) >= 0.1.0

## License

Apache License 2.0 — see [LICENSE](./LICENSE).

