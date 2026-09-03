"""Connector-related exceptions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectorError:
    """File/connector-level failure, shared across every connector type.

    Mirrors the {code, message, user_message, retryable} error shape used
    elsewhere in this project's API layer (here `kind` plays the role of
    `code`), so it can be surfaced to the UI without reshaping later. Reused
    by every connector in this package (CSV, GA4, OAuth) — connectors define
    their own local `kind` enum/values but share this envelope.
    """

    kind: str
    message: str
    user_message: str
    retryable: bool = False
