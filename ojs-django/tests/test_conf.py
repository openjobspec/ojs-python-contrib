"""Tests for OJS configuration (conf.py)."""

from __future__ import annotations

import pytest
from django.test import override_settings

from ojs_django.conf import OJSSettings, get_ojs_settings, reset_settings


@pytest.fixture(autouse=True)
def _reset() -> None:  # type: ignore[misc]
    reset_settings()
    yield
    reset_settings()


def test_default_settings() -> None:
    """Default settings should be sensible."""
    with override_settings(OJS=None):
        reset_settings()
        cfg = get_ojs_settings()
    assert cfg.url == "http://localhost:8080"
    assert cfg.default_queue == "default"
    assert cfg.concurrency == 10


def test_dict_based_settings() -> None:
    """Dict-based OJS settings should be parsed correctly."""
    with override_settings(
        OJS={
            "URL": "http://ojs.example.com:9090",
            "DEFAULT_QUEUE": "high",
            "QUEUE_PREFIX": "myapp_",
            "DEFAULT_RETRY": {"max_attempts": 7, "backoff": "linear"},
            "WORKER": {"concurrency": 20, "queues": ["high", "low"], "poll_interval": 5.0},
        }
    ):
        reset_settings()
        cfg = get_ojs_settings()

    assert cfg.url == "http://ojs.example.com:9090"
    assert cfg.default_queue == "high"
    assert cfg.queue_prefix == "myapp_"
    assert cfg.default_retry.max_attempts == 7
    assert cfg.default_retry.backoff == "linear"
    assert cfg.worker.concurrency == 20
    assert cfg.worker.queues == ["high", "low"]
    assert cfg.worker.poll_interval == 5.0


def test_legacy_flat_settings() -> None:
    """Legacy flat OJS_* settings should still work."""
    with override_settings(
        OJS=None,
        OJS_URL="http://legacy:8080",
        OJS_QUEUES=["q1", "q2"],
        OJS_CONCURRENCY=5,
        OJS_POLL_INTERVAL=3.0,
    ):
        reset_settings()
        cfg = get_ojs_settings()

    assert cfg.url == "http://legacy:8080"
    assert cfg.queues == ["q1", "q2"]
    assert cfg.concurrency == 5
    assert cfg.poll_interval == 3.0


def test_queue_prefix() -> None:
    """prefixed_queue should prepend the prefix."""
    cfg = OJSSettings(queue_prefix="staging_")
    assert cfg.prefixed_queue("default") == "staging_default"
    assert cfg.prefixed_queue("email") == "staging_email"


def test_queue_prefix_empty() -> None:
    """Empty prefix should not modify queue name."""
    cfg = OJSSettings(queue_prefix="")
    assert cfg.prefixed_queue("default") == "default"


def test_backward_compat_accessors() -> None:
    """queues, concurrency, poll_interval should delegate to worker settings."""
    with override_settings(
        OJS={
            "WORKER": {"concurrency": 15, "queues": ["a", "b"], "poll_interval": 1.0},
        }
    ):
        reset_settings()
        cfg = get_ojs_settings()

    assert cfg.queues == ["a", "b"]
    assert cfg.concurrency == 15
    assert cfg.poll_interval == 1.0


def test_settings_cached() -> None:
    """get_ojs_settings should cache the result."""
    reset_settings()
    cfg1 = get_ojs_settings()
    cfg2 = get_ojs_settings()
    assert cfg1 is cfg2
