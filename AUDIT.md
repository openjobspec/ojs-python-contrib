# Clean-Code / SRP Audit — `ojs-python-contrib`

Branch: `refactor/clean-code-srp` · Scope: the five CI-declared packages
(`ojs-django`, `ojs-flask`, `ojs-fastapi`, `ojs-celery`, `ojs-sqlalchemy`).
SDK calls were compared with an editable sibling `openjobspec` checkout, not
with a released artifact at the declared minimum `openjobspec>=0.2.0`.
Editable import/distribution metadata may report `0.1.0`, below that minimum,
and source-checkout APIs do not establish compatibility with the minimum
supported dependency. This is an external dependency/minimum-version
verification blocker; the results below must not be read as fully green.

## Summary (five bullets)

- **The codebase is small (~4.4k src LOC) but the baseline was uniformly red:**
  all five packages failed `ruff format`/`ruff check`, four failed strict
  `mypy` (django, flask, fastapi, celery — sqlalchemy was already clean), and
  FastAPI had one failing test. The failures cluster into three real defect
  classes rather than style noise.
- **Highest-leverage split #1 — SDK-contract drift.** Several modules call an
  `openjobspec` API surface that does not exist on the inspected sibling SDK
  (`SyncClient.fetch/complete/fail/release/purge_queue/queue_info/update_meta/list_jobs`,
  `Worker.register(type, handler)`, `ojs.CronJob`, `client.register_cron`,
  `ojs.chain/group/batch` positional shapes). These are latent runtime bugs
  masked by mock-only tests. This is the single most valuable axis to fix
  because it is both the bulk of the `mypy` failures and the source of code
  that cannot run in production.
- **Highest-leverage split #2 — actor-based SRP seams.** The genuinely mixed
  modules are the Django admin views (four views repeat context assembly +
  connection-error degradation), the Django enqueue backend (queue-resolution
  duplicated four times), the Flask client accessor (duplicated verbatim in
  `extension` and `helpers`), the SQLAlchemy event listener (dispatch loop
  duplicated in `install` and `notify`) and the Celery task API
  (`countdown→delay_until` duplicated). Each seam lives **within a single
  framework actor**, so extraction is safe; nothing is deduplicated across
  frameworks.
- **A P0 portability bug gates everything on Python 3.11.**
  `ojs_django/decorators.py` declares `class OJSJobWrapper[T]` (PEP 695, 3.12+)
  while the package advertises `requires-python>=3.11` and CI tests 3.11 — the
  module raises `SyntaxError` on import under 3.11, so the whole package is
  unusable there. Fixed with a 3.11-compatible `TypeVar`/`Generic`.
- **Two Celery modules are structurally incompatible with the current SDK.**
  `ojs_celery/transport.py` (Kombu broker) and `ojs_celery/backend.py`
  (Celery result backend) are built on a pull/ack broker API the OJS SDK does
  not expose (it consumes via `Worker`). Repairing them is a product-level
  redesign, not a refactor, so they are **Deferred** and `ojs-celery`'s strict
  `mypy` gate remains red on exactly those calls (documented below). No types
  were weakened and no bug was hidden to force a green result.

## Findings

Severity: P0 (broken / data-loss / portability), P1 (real bug or wrong SDK
call, masked by mocks), P2 (maintainability / SRP). Cost = fix effort,
Size = code touched, Risk = chance of regression.

| ID | Location | Category | Sev | Actor(s) / axis | Cost | Size | Risk |
|----|----------|----------|-----|-----------------|------|------|------|
| F1 | `ojs-django/src/ojs_django/decorators.py:17` | Portability bug | P0 | Runtime/packaging | S | XS | Low |
| F2 | `ojs-django` pytest (`pyproject` `[tool.pytest.ini_options]`) | Test infra | P0 | CI/test runner | S | XS | Low |
| F3 | `ojs-fastapi/tests/test_depends.py:17` | Test isolation bug | P0 | FastAPI tests | S | XS | Low |
| F4 | `ojs-flask/src/ojs_flask/health.py:51`, `cli.py:72` | Wrong SDK call (`queue_stats(Queue)`) | P1 | Flask ops/health | S | XS | Low |
| F5 | `ojs-flask/src/ojs_flask/worker.py:88`, `ojs-fastapi/src/ojs_fastapi/handlers.py:94` | Wrong SDK call (`Worker.register` arity) | P1 | Flask/FastAPI worker | S | XS | Low |
| F6 | `ojs-fastapi/src/ojs_fastapi/workflow.py` | Wrong SDK call (`chain/group/batch`, `client.workflow()`) | P1 | FastAPI workflows | M | S | Med |
| F7 | `ojs-fastapi/src/ojs_fastapi/cron.py:80` | Wrong SDK call (`ojs.CronJob`, `register_cron`) | P1 | FastAPI cron | M | S | Med |
| F8 | `ojs-flask/src/ojs_flask/cli.py:31` | Wrong app-extensions key (`ojs_extension`) | P1 | Flask CLI worker | S | XS | Low |
| F9 | Flask `extension.py`/`health.py`/`cli.py` mypy | Type soundness (bare `Callable`, unused ignores, `no-any-return`) | P1 | Flask maintainers | M | S | Low |
| F10 | FastAPI `depends.py:38/43`, `health.py:40` mypy | Type soundness (`cast`, invariant `tags`) | P1 | FastAPI maintainers | S | XS | Low |
| F11 | Celery `__init__.py:36` `migrate_task(*args, **kwargs)` | Type/arg bug | P1 | Celery migration | S | XS | Low |
| F12 | Celery `backend.py:99/105` state-map assignment types | Type soundness | P2 | Celery backend | S | XS | Low |
| F13 | Celery `transport.py`/`backend.py`/`migration.py` untyped 3rd-party + subclass-`Any` | mypy config | P1 | Celery maintainers | S | XS | Low |
| F14 | `ojs-django/src/ojs_django/admin.py` (4 views) | SRP: duplicated context + degradation | P2 | Django admin | M | S | Low |
| F15 | `ojs-django/src/ojs_django/backend.py` (×4) | SRP: duplicated queue resolution | P2 | Django enqueue | S | XS | Low |
| F16 | `ojs-flask/src/ojs_flask/extension.py` vs `helpers.py` | SRP: duplicated client accessor | P2 | Flask extension | S | XS | Low |
| F17 | `ojs-sqlalchemy/src/ojs_sqlalchemy/events.py` (`install`+`notify`) | SRP: duplicated dispatch loop | P2 | SQLAlchemy events | S | XS | Low |
| F18 | `ojs-sqlalchemy/src/ojs_sqlalchemy/enqueue.py` (sync+async) | SRP: duplicated kwargs build | P2 | SQLAlchemy enqueue | S | XS | Low |
| F19 | `ojs-celery/src/ojs_celery/adapter.py` + `compat.py` | SRP: duplicated `countdown→delay_until` | P2 | Celery task API | S | XS | Low |
| F20 | All five packages | Lint + format not green | P1 | All maintainers | M | M | Low |
| D1 | `ojs-celery/src/ojs_celery/transport.py` | SDK-contract drift (broker API absent) | P0 | Celery broker | L | L | High |
| D2 | `ojs-celery/src/ojs_celery/backend.py` | SDK-contract drift (result API absent) | P0 | Celery result backend | L | L | High |
| D3 | `ojs-django/src/ojs_django/enqueue.py` | Legacy duplicate of `backend.py` (own client singleton, different signature) | P2 | Django enqueue | M | M | Med |

## Ordered implementation sequence

1. **F20** — `ruff format` + `ruff check --fix` + manual residue, per package
   (unblocks readable diffs for everything after).
2. **F1** — Django PEP 695 → `TypeVar`/`Generic` (restores 3.11 import + fixes
   the single Django `mypy` error).
3. **F2** — Django `pytest` `pythonpath` so the canonical `pytest` console
   script collects (matches CI/Makefile).
4. **F3** — FastAPI `test_depends` shared-mock invariant (repairs the one
   failing test).
5. **F4, F5, F8** — clear wrong-SDK-call bugs with regression tests.
6. **F9, F10, F11, F12, F13** — type-soundness repairs (`cast`, real
   annotations, targeted `type: ignore[misc]` for subclassing untyped
   third-party bases, per-module `ignore_missing_imports`).
7. **F6, F7** — FastAPI workflow/cron corrected to the real SDK builders /
   `register_cron_job`, with regression tests asserting the correct calls.
8. **F14–F19** — actor-local SRP extractions, each guarded by pre-existing or
   newly added characterization tests.
9. Re-run every gate on a clean per-package env across Python 3.12 and 3.13,
   while recording that the editable sibling cannot verify compatibility with
   the declared `openjobspec>=0.2.0` minimum.

## Out of scope

- The four non-CI directories `ojs-agentcore/`, `ojs-crewai/`,
  `ojs-langgraph/`, `ojs-openai/` — they have no `pyproject.toml`, are absent
  from the `Makefile` `PACKAGES` list and the CI matrix, and ship only a
  README + stub `__init__` + one test each. Not part of the declared gates.
- `examples/` apps and their `docker-compose.yml`/`requirements.txt` — these
  scripts **are** linted/formatted by the canonical `ruff check .`/`ruff format`
  (run from the package root), so intentional demo-only violations (`T201`
  prints, `A002` arg names) are suppressed with narrowly-scoped `# noqa`; but
  examples are **not** type-checked (`mypy` targets `src/`) and **not** run by
  the test suite (`testpaths = ["tests"]`), and their runtime logic is left
  unchanged.
- Any change to public adapter APIs, decorator/registration surfaces, route
  paths, settings/config keys, serialization or the package identity/versions.
- Dependency-version bumps, generated files, and format-only churn beyond the
  files the canonical formatter/linter must touch.
- The `openjobspec` SDK itself and all sibling repositories (never modified).

## Deferred

- **D1/D2 — Celery broker + result backend redesign.** `transport.py` and
  `backend.py` require a pull/ack/consume API (`fetch`, `complete`, `fail`,
  `release`, `purge_queue`, `queue_info`, `update_meta`, `list_jobs`) that the
  current `openjobspec` `SyncClient` does not provide — the SDK consumes jobs
  through `Worker`, not a Kombu-style broker. Making these type-check would
  require either inventing SDK methods (impossible without touching the SDK) or
  a `# type: ignore`/Protocol that hides a genuine runtime defect (rejected:
  that would be "weakening types" and hiding a bug). Consequently these calls
  remain the **only** residual `ojs-celery` strict-`mypy` errors, and the
  package's `mypy` gate stays red pending a product decision (add broker
  endpoints to the SDK, or re-implement the transport on top of `Worker`).
  All other Celery `mypy`/lint/format/test issues are repaired.
- **D3 — `ojs_django/enqueue.py`.** A legacy near-duplicate of `backend.py`
  with its own separate `_sync_client` singleton and a *different* public
  signature (`enqueue(job_type, args_list)` vs `backend.enqueue(job_type,
  *args)`), so it cannot be collapsed into a re-export shim without changing a
  public import path's behavior. It is unused by tests/examples/README/src.
  Correct resolution is a deprecation cycle (public/product change), deferred.
- **Celery result-state mapping.** `backend.py` maps to non-lifecycle names
  (`queued`, `retrying`, `dead`) instead of the OJS 8-state model; corrected
  mapping is wire/product behavior, deferred with D1/D2.

## Configuration additions (needed for the canonical gates)

- `ojs-django/pyproject.toml` — `[tool.pytest.ini_options] pythonpath = ["."]`
  so the canonical `pytest` console script (used by CI + `make test-all`) can
  import `tests.settings` for `pytest-django` (F2).
- `ojs-fastapi/pyproject.toml` — `[tool.ruff.lint.flake8-bugbear]
  extend-immutable-calls = ["fastapi.Depends", ...]` so `B008` respects the
  FastAPI dependency-injection idiom instead of flagging every endpoint.
- `ojs-celery/pyproject.toml` — `[[tool.mypy.overrides]] module =
  ["celery.*", "kombu.*"] ignore_missing_imports = true` because those
  third-party packages ship no stubs/`py.typed`. This does not weaken any of
  our own annotations.

No existing config keys were changed; only additive keys were introduced.

## Results (clean per-package venv, Python 3.11, 3.12 and 3.13)

Every gate below was run on a freshly created virtualenv per package for each of
Python 3.11.13, 3.12.13 and 3.13.13 (3.11 provided via `uv`), plus the canonical
`make install-all` / `make test-all` / `make lint-all` on a shared env and a
`python -m build` wheel + import smoke for all five packages. These runs used
the available editable sibling SDK; they do not verify the declared minimum
dependency version.

| Package | ruff check | ruff format | mypy (strict) | pytest | build |
|---------|:----------:|:-----------:|:-------------:|-------:|:-----:|
| ojs-django | pass | pass | pass | 43 pass | wheel + py.typed |
| ojs-flask | pass | pass | pass | 73 pass | wheel + py.typed |
| ojs-fastapi | pass | pass | pass | 57 pass | wheel + py.typed |
| ojs-celery | pass | pass | **11 deferred (D1/D2)** | 55 pass | wheel + py.typed |
| ojs-sqlalchemy | pass | pass | pass | 58 pass | wheel + py.typed |

`make test-all` → 286 tests pass. `make lint-all` → django/flask/fastapi/
sqlalchemy pass `ruff check` + strict `mypy`; `ojs-celery`'s residual `mypy`
errors are exactly the deferred broker/result-backend SDK-drift calls in
`transport.py`/`backend.py` (every other Celery `mypy` error was repaired).
`pip-audit` reports no known vulnerabilities. The F1 fix was proven on real
3.11: the previous `class OJSJobWrapper[T]` raises `SyntaxError` under 3.11
while the `TypeVar`/`Generic` form imports cleanly. Test totals grew from the
baseline via added characterization/regression tests (django +3, flask +2),
while FastAPI's previously failing test now passes.

**External dependency blocker:** an editable sibling import/distribution may
identify itself as `0.1.0`, which cannot satisfy or validate the declared
`openjobspec>=0.2.0` contract. Until the suite is run against an identifiable
released artifact at `0.2.0` (and preferably at both the minimum and current
supported versions), minimum-version compatibility remains unverified.
During final verification, an existing Python 3.12 environment reported both
the sibling import and distribution as `0.1.0`; reinstalling the same editable
checkout into fresh environments reported `0.4.0`. That discrepancy is exactly
why editable sibling metadata is not accepted as release-compatibility
evidence.

Final verification on 2026-08-10 re-ran `make test-all` under Python 3.11.13,
3.12.13 and 3.13.13: all three runs passed the same 286 tests (43 Django, 73
Flask, 57 FastAPI, 55 Celery, 58 SQLAlchemy). `ruff check` passed all five
packages on all three runtimes. Strict `mypy` passed Django, Flask, FastAPI and
SQLAlchemy; Celery retained the same 11 deferred D1/D2 errors on every runtime.
The strengthened FastAPI cron regression passed (5 tests), as did targeted
FastAPI strict `mypy`, `ruff check`, and `ruff format --check`.

## Release-readiness follow-up (2026-09-02)

- All five package versions now match the current repository tag, `v0.4.1`.
- Each package has a `uv.lock`; CI uses `uv sync --locked` and `uv run
  --frozen` across Python 3.11, 3.12, and 3.13.
- Dependabot now scans all five package directories, and CI builds both wheel
  and sdist artifacts, runs `uv publish --dry-run`, and installs each wheel in
  a clean consumer environment.
- The current `v0.4.1` SDK tag still identifies its artifact as `0.4.0` and
  imports `cryptography` without declaring it or providing the advertised
  `crypto` extra. The locked test source therefore includes `cryptography` as
  a development-only compatibility dependency. Publishing a corrected SDK
  artifact remains an external release-order blocker; contrib runtime
  dependencies were not broadened to hide it.
- With the locked MyPy 1.20.2 toolchain, Celery reports 12 errors in the same
  two deferred D1/D2 modules; all other package MyPy gates pass.

### Coordinated 0.5.0 resolution

- All five integration packages and their lockfiles now target the local
  `openjobspec` 0.5.0 artifact with the compatibility window
  `>=0.5.0,<0.6.0`.
- The SDK now exposes normative `fetch`, `ack`, and `nack` operations through
  `Client` and `SyncClient`. Celery broker acknowledgement, rejection,
  requeue, fetch, and size operations use those supported APIs.
- Unsafe queue purge is deliberately not mapped: OJS only defines guarded
  administrative purge with explicit state filters and confirmation.
- The result backend stores successful results through ACK and structured
  failures/retries through NACK. Unsupported metadata mutation and tag-search
  calls were removed.
- Celery strict MyPy is fully green, and its suite passes 58 tests including
  real `SyncClient` plus `FakeTransport` coverage.

## Baseline (clean per-package venv, Python 3.12; local repro)

| Package | ruff check | ruff format | mypy | pytest |
|---------|-----------:|------------:|-----:|-------:|
| ojs-django | 28 | 8 files | 1 (F1 syntax) | 40 pass¹ |
| ojs-flask | 30 | 11 files | 14 | 71 pass |
| ojs-fastapi | 47 | 7 files | 16 | 56 pass / 1 fail (F3) |
| ojs-celery | 57 | 10 files | 26 | 55 pass |
| ojs-sqlalchemy | 59 | 10 files | 0 | 58 pass |

¹ Django tests pass under `python -m pytest`; the plain `pytest` console
script fails collection until F2 (`pytest-django` imports settings before the
package root is on `sys.path`).
