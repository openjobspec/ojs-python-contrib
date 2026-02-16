"""Pytest configuration — mock the ojs module if it cannot be imported."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock


def _build_mock_ojs() -> types.ModuleType:
    """Create a mock ``ojs`` package that satisfies all adapter imports."""
    mod = types.ModuleType("ojs")

    @dataclass
    class Job:
        id: str = "mock-job-id"
        type: str = ""
        state: str = "available"
        args: list[Any] = field(default_factory=list)
        queue: str = "default"
        meta: dict[str, Any] = field(default_factory=dict)

    class SyncClient:
        def __init__(self, url: str, **kwargs: Any) -> None:
            self.url = url
            self.enqueue = MagicMock(return_value=Job())
            self.close = MagicMock()

        def __enter__(self) -> "SyncClient":
            return self

        def __exit__(self, *args: Any) -> None:
            self.close()

    class Client:
        def __init__(self, url: str, **kwargs: Any) -> None:
            self.url = url

    mod.Job = Job  # type: ignore[attr-defined]
    mod.SyncClient = SyncClient  # type: ignore[attr-defined]
    mod.Client = Client  # type: ignore[attr-defined]
    mod.JobContext = MagicMock  # type: ignore[attr-defined]
    mod.JobRequest = MagicMock  # type: ignore[attr-defined]
    return mod


# Install the mock before any test imports ojs_celery
try:
    import ojs  # noqa: F401
except (ImportError, Exception):
    sys.modules["ojs"] = _build_mock_ojs()
