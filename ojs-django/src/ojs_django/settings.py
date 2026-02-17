"""Backward-compatible settings module.

.. deprecated::
    Import from :mod:`ojs_django.conf` instead. This module exists only for
    backward compatibility.
"""

from __future__ import annotations

from ojs_django.conf import OJSSettings, get_ojs_settings, reset_settings

__all__ = ["OJSSettings", "get_ojs_settings", "reset_settings"]
