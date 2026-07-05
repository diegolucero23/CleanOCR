"""
Secret redaction helpers.

Every place that stringifies an exception or writes diagnostic output should
pass the text through redact() so the Gemini API key can never leak into
failed_pages.log, the Redis DLQ, structured logs, or console tracebacks —
even if a future SDK version starts embedding the key in error messages.
"""
import logging
import re
import traceback

from app.core import config

REDACTED = "[REDACTED_GOOGLE_API_KEY]"

# Google API keys are "AIza" + 35 url-safe chars; match a small range around
# that so truncated/extended variants are still caught.
_GOOGLE_KEY_RE = re.compile(r"AIza[0-9A-Za-z_\-]{31,40}")


def redact(text) -> str:
    """Return text with the configured API key and any key-shaped string removed."""
    s = str(text)
    key = config.GOOGLE_API_KEY
    # Mock/dummy values (MOCK_KEY_DO_NOT_CHARGE, test-key-for-ci) are not
    # secrets and are load-bearing in test assertions — leave them readable.
    if key and len(key) >= 8 and not key.startswith("MOCK"):
        s = s.replace(key, REDACTED)
    return _GOOGLE_KEY_RE.sub(REDACTED, s)


class SecretRedactingFilter(logging.Filter):
    """Logging filter that scrubs key material from records.

    Covers the formatted message, %-style args, `extra` fields (which
    python-json-logger serializes into the output), and exception tracebacks.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        for attr, value in list(record.__dict__.items()):
            if isinstance(value, str) and attr not in ("msg", "name", "pathname", "filename", "module", "funcName"):
                record.__dict__[attr] = redact(value)
        if record.exc_info and not record.exc_text:
            record.exc_text = redact("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        return True
