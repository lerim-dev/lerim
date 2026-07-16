"""Content-based secret and PII redaction applied at the ingestion edge.

This module scrubs common secret and PII patterns out of arbitrary text
before that text is written to any on-disk cache or compact trace, so raw
credentials never reach durable records or skills. It uses only the
standard library ``re`` module -- no new dependencies.

Recognized patterns: private key PEM blocks, passwords embedded in
connection URLs, Bearer/Authorization header tokens, AWS access and secret
keys, OpenAI-style API keys (``sk-...``), GitHub tokens
(``ghp_``/``gho_``/``ghs_``/``ghu_``), and email addresses. Each match is
replaced with a stable ``[REDACTED:<kind>]`` placeholder. Patterns are kept
precise (specific prefixes, minimum lengths, required surrounding syntax)
so ordinary prose and code identifiers are not affected.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Individual secret/PII patterns
# ---------------------------------------------------------------------------
# Applied in sequence below. Order matters: the private-key block is scrubbed
# first so its base64 body cannot accidentally feed a narrower pattern later,
# and the generic email pattern runs last since it is the least specific.

_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
# A truncated/unterminated key block (BEGIN present, no matching END anywhere
# in the text -- e.g. a partial tool-output capture) is not matched by
# _PRIVATE_KEY_RE above. Applied second, after paired blocks are already
# replaced, this catches any BEGIN marker left over and redacts through the
# end of the text so a truncated capture cannot leak its base64 body.
_PRIVATE_KEY_UNTERMINATED_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*",
    re.DOTALL,
)

_URL_PASSWORD_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9+.\-]*://[^\s:/@]+):([^\s@/]+)@"
)

# A digit is required in the token itself so ordinary words after "Bearer"
# (e.g. "the bearer of good news") or after an "Authorization:" label in
# prose do not get treated as secrets.
_BEARER_RE = re.compile(r"(?i)\bBearer\s+(?=[A-Za-z0-9._-]*\d)[A-Za-z0-9._-]{8,}")
_AUTH_HEADER_RE = re.compile(
    r"(?i)\bAuthorization\s*:\s*(?=[A-Za-z0-9._-]*\d)[A-Za-z0-9._-]{8,}"
)

_AWS_SECRET_RE = re.compile(
    r"(?i)\b(aws[_-]secret(?:[_-]access)?[_-]key)(\s*[:=]\s*)"
    r"[\"']?([A-Za-z0-9/+=]{40})[\"']?"
)
_AWS_ACCESS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")

_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")

_GITHUB_TOKEN_RE = re.compile(r"\bgh[opsu]_[A-Za-z0-9]{20,}\b")

# The TLD position excludes common image/media file extensions so that
# retina-scale asset filenames (icon@2x.png, logo@3x.jpg, ...) and similar
# "name@token.ext" filename shapes are not mistaken for email addresses.
# None of these extensions are real TLDs, so genuine email addresses are
# never affected by this exclusion.
_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\."
    r"(?!(?i:png|jpe?g|gif|svg|webp|ico|bmp|tiff?|avif|heic|heif)\b)"
    r"[A-Za-z]{2,}\b"
)


def _replace_url_password(match: re.Match[str]) -> str:
    """Return a scheme://user: prefix with the URL's embedded password redacted."""
    prefix = match.group(1)
    return f"{prefix}:[REDACTED:password]@"


def _replace_aws_secret(match: re.Match[str]) -> str:
    """Return an AWS secret-key assignment with its value redacted."""
    key_name, separator = match.group(1), match.group(2)
    return f"{key_name}{separator}[REDACTED:aws_secret_key]"


def redact_text(text: str) -> str:
    """Scrub common secrets and PII from ``text``, returning the redacted copy.

    Each recognized secret is replaced with a stable ``[REDACTED:<kind>]``
    placeholder (for example ``[REDACTED:api_key]`` or ``[REDACTED:email]``).
    Text containing none of the recognized patterns is returned unchanged.
    """
    redacted = _PRIVATE_KEY_RE.sub("[REDACTED:private_key]", text)
    redacted = _PRIVATE_KEY_UNTERMINATED_RE.sub("[REDACTED:private_key]", redacted)
    redacted = _URL_PASSWORD_RE.sub(_replace_url_password, redacted)
    redacted = _BEARER_RE.sub("Bearer [REDACTED:token]", redacted)
    redacted = _AUTH_HEADER_RE.sub("Authorization: [REDACTED:token]", redacted)
    redacted = _AWS_SECRET_RE.sub(_replace_aws_secret, redacted)
    redacted = _AWS_ACCESS_KEY_RE.sub("[REDACTED:aws_access_key]", redacted)
    redacted = _OPENAI_KEY_RE.sub("[REDACTED:api_key]", redacted)
    redacted = _GITHUB_TOKEN_RE.sub("[REDACTED:github_token]", redacted)
    redacted = _EMAIL_RE.sub("[REDACTED:email]", redacted)
    return redacted


if __name__ == "__main__":
    """Run a real-path smoke test for redact_text."""
    sample = (
        "Contact person@example.com about the sk-abcdefghijklmnopqrstuvwxyz "
        "key and the AKIAABCDEFGHIJKLMNOP access key."
    )
    result = redact_text(sample)
    assert "person@example.com" not in result
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in result
    assert "AKIAABCDEFGHIJKLMNOP" not in result
    assert "[REDACTED:email]" in result
    assert "[REDACTED:api_key]" in result
    assert "[REDACTED:aws_access_key]" in result

    plain = "an ordinary sentence with no secrets at all"
    assert redact_text(plain) == plain
