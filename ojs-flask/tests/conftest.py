"""Conftest: mock the ojs module if the SDK is not importable (e.g., dev/CI mismatch)."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock


def _install_ojs_mock() -> None:
    """Install a lightweight mock for the ``ojs`` package so tests can run
    without a fully functional OJS Python SDK installation."""
    mock_ojs = ModuleType("ojs")
    mock_ojs.SyncClient = MagicMock  # type: ignore[attr-defined]
    mock_ojs.Client = MagicMock  # type: ignore[attr-defined]
    mock_ojs.Worker = MagicMock  # type: ignore[attr-defined]
    mock_ojs.Job = MagicMock  # type: ignore[attr-defined]
    mock_ojs.JobContext = MagicMock  # type: ignore[attr-defined]
    mock_ojs.CronJob = MagicMock  # type: ignore[attr-defined]
    mock_ojs.JobState = MagicMock  # type: ignore[attr-defined]
    sys.modules["ojs"] = mock_ojs


try:
    import ojs  # noqa: F401
except (ImportError, Exception):
    _install_ojs_mock()
