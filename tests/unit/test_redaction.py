"""Unit tests for lerim.redaction: content-based secret and PII scrubbing.

Covers each recognized secret/PII pattern, composite text with several
secrets at once, and precision checks that ordinary prose and code
identifiers are left untouched.
"""

from __future__ import annotations

from lerim.redaction import redact_text


# ---------------------------------------------------------------------------
# Individual secret/PII patterns are redacted
# ---------------------------------------------------------------------------


def test_redacts_openai_style_key():
    """An OpenAI-style sk- API key is replaced with the api_key placeholder."""
    text = "export OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz0123456789"
    result = redact_text(text)
    assert "sk-abcdefghijklmnopqrstuvwxyz0123456789" not in result
    assert "[REDACTED:api_key]" in result


def test_redacts_aws_access_key():
    """An AWS access key id (AKIA...) is replaced with a stable placeholder."""
    text = "aws_access_key_id = AKIAIOSFODNN7EXAMPLE"
    result = redact_text(text)
    assert "AKIAIOSFODNN7EXAMPLE" not in result
    assert "[REDACTED:aws_access_key]" in result


def test_redacts_aws_secret_key():
    """An AWS secret access key value is replaced; the key name is preserved."""
    text = 'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
    result = redact_text(text)
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in result
    assert "[REDACTED:aws_secret_key]" in result
    assert "aws_secret_access_key" in result


def test_redacts_bearer_token():
    """A Bearer token in an Authorization header is replaced with a placeholder."""
    text = "Authorization: Bearer abc123DEF456ghi789JKL"
    result = redact_text(text)
    assert "abc123DEF456ghi789JKL" not in result
    assert "[REDACTED:token]" in result
    assert "Bearer" in result


def test_redacts_raw_authorization_header_token():
    """A raw (non-Bearer) Authorization header value is redacted."""
    text = "Authorization: abc123def456ghi789jkl"
    result = redact_text(text)
    assert "abc123def456ghi789jkl" not in result
    assert "[REDACTED:token]" in result


def test_redacts_github_token():
    """A GitHub personal access token (ghp_...) is replaced with a placeholder."""
    text = "token: ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    result = redact_text(text)
    assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in result
    assert "[REDACTED:github_token]" in result


def test_redacts_private_key_block():
    """A PEM private key block is fully replaced with a single placeholder."""
    text = (
        "before\n"
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEA1234567890abcdefghijklmnop\n"
        "moreBase64DataHere==\n"
        "-----END RSA PRIVATE KEY-----\n"
        "after"
    )
    result = redact_text(text)
    assert "MIIEpAIBAAKCAQEA1234567890abcdefghijklmnop" not in result
    assert "[REDACTED:private_key]" in result
    assert "before" in result
    assert "after" in result


def test_redacts_unterminated_private_key_block():
    """A truncated key block with no END marker is redacted through to the end."""
    text = (
        "before context\n"
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEA1234567890abcdefghijklmnop\n"
        "moreBase64DataHereWithoutAnEndMarkerAtAll\n"
    )
    result = redact_text(text)
    assert "MIIEpAIBAAKCAQEA1234567890abcdefghijklmnop" not in result
    assert "moreBase64DataHereWithoutAnEndMarkerAtAll" not in result
    assert "[REDACTED:private_key]" in result
    assert "before context" in result


def test_redacts_two_separate_private_key_blocks_independently():
    """Two separate well-formed key blocks are each redacted, not merged into one."""
    text = (
        "-----BEGIN RSA PRIVATE KEY-----\nAAAA1111\n-----END RSA PRIVATE KEY-----\n"
        "middle text\n"
        "-----BEGIN RSA PRIVATE KEY-----\nBBBB2222\n-----END RSA PRIVATE KEY-----\n"
    )
    result = redact_text(text)
    assert "AAAA1111" not in result
    assert "BBBB2222" not in result
    assert "middle text" in result
    assert result.count("[REDACTED:private_key]") == 2


def test_redacts_email_address():
    """A plain email address is replaced with the email placeholder."""
    text = "please reach out to jane.doe@example.com for details"
    result = redact_text(text)
    assert "jane.doe@example.com" not in result
    assert "[REDACTED:email]" in result


def test_redacts_password_in_url():
    """A password embedded in a connection URL is replaced; user/host are kept."""
    text = "db url: postgres://admin:s3cr3tPassw0rd@db.example.com:5432/mydb"
    result = redact_text(text)
    assert "s3cr3tPassw0rd" not in result
    assert "[REDACTED:password]" in result
    assert "admin" in result
    assert "db.example.com" in result


# ---------------------------------------------------------------------------
# Precision: ordinary prose and code identifiers are not over-redacted
# ---------------------------------------------------------------------------


def test_leaves_ordinary_sentence_untouched():
    """A normal sentence with no secrets is returned unchanged."""
    text = "The quarterly review is scheduled for next Tuesday afternoon."
    assert redact_text(text) == text


def test_leaves_code_identifiers_untouched():
    """Ordinary code identifiers that merely resemble secret prefixes are kept."""
    text = "def sk_ratio(sk_value, aws_region): return sk_value / 2"
    assert redact_text(text) == text


def test_leaves_bearer_word_in_prose_untouched():
    """The English word 'bearer' followed by ordinary prose is not redacted."""
    text = "the bearer of this letter should be granted access to the building"
    assert redact_text(text) == text


def test_leaves_short_bearer_like_token_untouched():
    """A digit-free word after Bearer is not treated as a secret token."""
    text = "Bearer information"
    assert redact_text(text) == text


def test_leaves_partial_aws_prefix_untouched():
    """A string that merely starts with AKIA but is not a full key is untouched."""
    text = "AKIA is not a recognized abbreviation here"
    assert redact_text(text) == text


def test_leaves_url_without_password_untouched():
    """A URL with no embedded userinfo/password is left unchanged."""
    text = "see https://example.com/path?query=1 for the report"
    assert redact_text(text) == text


def test_leaves_retina_png_asset_filename_untouched():
    """A retina-scale @2x.png asset filename is not mistaken for an email."""
    text = "see icon@2x.png for the retina asset"
    assert redact_text(text) == text


def test_leaves_retina_asset_filename_in_path_untouched():
    """A retina-scale asset filename embedded in a path is left unchanged."""
    text = "the file lives at assets/logo@2x.png"
    assert redact_text(text) == text


def test_leaves_retina_jpg_asset_filename_untouched():
    """A @3x.jpg retina asset filename is not mistaken for an email."""
    text = "logo@3x.jpg is the exported asset"
    assert redact_text(text) == text


# ---------------------------------------------------------------------------
# Composite behavior
# ---------------------------------------------------------------------------


def test_redacts_multiple_secrets_and_preserves_surrounding_text():
    """Multiple distinct secrets in one text are each redacted; prose survives."""
    text = (
        "Context: contact ops@example.com if the sk-abcdefghijklmnopqrstuvwx key "
        "or the AKIAABCDEFGHIJKLMNOP access key stop working."
    )
    result = redact_text(text)
    assert "ops@example.com" not in result
    assert "sk-abcdefghijklmnopqrstuvwx" not in result
    assert "AKIAABCDEFGHIJKLMNOP" not in result
    assert "[REDACTED:email]" in result
    assert "[REDACTED:api_key]" in result
    assert "[REDACTED:aws_access_key]" in result
    assert "Context: contact" in result
    assert "stop working." in result


def test_redact_text_is_deterministic():
    """Redacting the same input twice yields identical, stable output."""
    text = "email me at test@example.com"
    assert redact_text(text) == redact_text(text)


def test_redact_text_empty_string():
    """Empty text is returned unchanged."""
    assert redact_text("") == ""
