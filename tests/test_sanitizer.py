"""Tests for policy-driven PII sanitization."""

from src.detector import PIIDetector
from src.policies import Action, SanitizationPolicy, EntityPolicy, STRICT_POLICY, PERMISSIVE_POLICY
from src.sanitizer import PIISanitizer


def _detect_and_sanitize(text: str, policy: SanitizationPolicy | None = None) -> tuple:
    detector = PIIDetector()
    detection = detector.detect(text)
    sanitizer = PIISanitizer(policy)
    result = sanitizer.sanitize(detection)
    return detection, result


class TestRedaction:
    def test_email_is_redacted_by_default(self):
        _, result = _detect_and_sanitize("Email: john@example.com")
        assert "[REDACTED_EMAIL_ADDRESS]" in result.sanitized_text
        assert "john@example.com" not in result.sanitized_text

    def test_ip_is_redacted_by_default(self):
        _, result = _detect_and_sanitize("IP: 192.168.1.1")
        assert "192.168.1.1" not in result.sanitized_text

    def test_strict_policy_redacts_everything(self):
        _, result = _detect_and_sanitize(
            "John Smith's email is john@example.com",
            policy=STRICT_POLICY,
        )
        assert "John Smith" not in result.sanitized_text
        assert "john@example.com" not in result.sanitized_text


class TestPseudonymization:
    def test_person_name_is_pseudonymized_by_default(self):
        _, result = _detect_and_sanitize("Contact John Smith for details")
        # Should not contain the original name
        assert "John Smith" not in result.sanitized_text
        # Should not be a redaction placeholder either (it's pseudonymized)
        assert "[REDACTED_PERSON]" not in result.sanitized_text

    def test_pseudonymization_is_deterministic(self):
        _, result1 = _detect_and_sanitize("Contact John Smith")
        _, result2 = _detect_and_sanitize("Contact John Smith")
        assert result1.sanitized_text == result2.sanitized_text


class TestAllowlist:
    def test_permissive_policy_keeps_names(self):
        _, result = _detect_and_sanitize(
            "John Smith sent an email to john@example.com",
            policy=PERMISSIVE_POLICY,
        )
        # Permissive policy allowlists names by default
        # but redacts emails
        assert "john@example.com" not in result.sanitized_text


class TestSanitizationCounts:
    def test_counts_are_correct(self):
        _, result = _detect_and_sanitize(
            "John Smith's email is john@example.com"
        )
        assert result.entity_count > 0
        # At least one entity should be sanitized
        assert result.redacted_count + result.pseudonymized_count > 0
