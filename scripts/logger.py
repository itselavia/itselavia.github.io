"""Structured JSON logger with automatic sensitive-data scrubbing."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import re
import sys
from typing import Any

SENSITIVE_KEY_PATTERN: re.Pattern[str] = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?key|auth[_-]?token|token)\b"
    r"(\s*[:=]\s*)"
    r"(['\"]?[^\s,'\";]+['\"]?)"
)
GITHUB_TOKEN_PATTERN: re.Pattern[str] = re.compile(
    r"\b(gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,})\b"
)
AWS_KEY_PATTERN: re.Pattern[str] = re.compile(r"\b(AKIA[0-9A-Z]{16})\b")
EMAIL_PATTERN: re.Pattern[str] = re.compile(
    r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
)
SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_key",
        "private_key",
        "authorization",
    }
)


def scrub_sensitive_text(text: str) -> str:
    """Redact credentials, tokens, AWS keys, and email addresses from log strings."""
    scrubbed = GITHUB_TOKEN_PATTERN.sub("[REDACTED_GITHUB_TOKEN]", text)
    scrubbed = AWS_KEY_PATTERN.sub("[REDACTED_AWS_KEY]", scrubbed)
    scrubbed = SENSITIVE_KEY_PATTERN.sub(r"\1\2[REDACTED]", scrubbed)
    scrubbed = EMAIL_PATTERN.sub(r"[REDACTED_EMAIL]@\2", scrubbed)
    return scrubbed


def scrub_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive keys and string values in structured log dictionaries."""
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_FIELD_NAMES:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, str):
            sanitized[key] = scrub_sensitive_text(value)
        elif isinstance(value, dict):
            sanitized[key] = scrub_mapping(value)
        elif isinstance(value, list):
            sanitized[key] = [
                scrub_sensitive_text(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


class JsonScrubbingFormatter(logging.Formatter):
    """Format log records as single-line JSON with sensitive fields scrubbed."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": scrub_sensitive_text(record.getMessage()),
        }
        extra_context = getattr(record, "context", None)
        if isinstance(extra_context, dict):
            payload["context"] = scrub_mapping(extra_context)
        return json.dumps(payload, sort_keys=True)


def get_logger(name: str = "agentic.validator") -> logging.Logger:
    """Create or retrieve a structured JSON logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonScrubbingFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level_name, logging.INFO))
    return logger
