# Contributing to OJS Python Contrib

Thank you for your interest in contributing to the Open Job Spec Python community integrations!

## Adding a New Integration

Each new integration lives in its own directory `ojs-{framework}/` and must include:

1. **`pyproject.toml`** — Package metadata with `openjobspec` as a dependency
2. **`src/ojs_{framework}/`** — Source code with type hints and `py.typed` marker
3. **`tests/`** — pytest tests (no real OJS server required)
4. **`examples/`** — Working example app with `docker-compose.yml`
5. **`README.md`** — Installation, usage, and API documentation

### Package Conventions

- **PyPI name**: `openjobspec-{framework}`
- **Import name**: `ojs_{framework}`
- **Build system**: hatchling via `pyproject.toml`
- **Testing**: pytest with `asyncio_mode = auto`
- **Type checking**: mypy strict mode
- **Linting**: ruff

### Code Style

- Use modern Python (3.11+): type hints, `match` statements, `StrEnum`
- Use `async`/`await` where the framework supports it
- Keep dependencies minimal: only the framework + `openjobspec`
- Follow the patterns established by existing integrations

## Development Setup

```bash
# Clone the repository
git clone https://github.com/openjobspec/ojs-python-contrib.git
cd ojs-python-contrib

# Install all packages in dev mode
make install-all

# Run tests
make test-all

# Lint and type check
make lint-all
```

## Pull Request Process

1. Create a feature branch from `main`
2. Add or update integration code
3. Ensure all tests pass: `make test-all`
4. Ensure linting passes: `make lint-all`
5. Update the root README.md if adding a new integration
6. Submit a PR with a clear description

## Reporting Issues

Please file issues on the [GitHub issue tracker](https://github.com/openjobspec/ojs-python-contrib/issues) with:

- The integration package name and version
- Python version
- Framework version
- Minimal reproduction steps
