"""Tests for PII detection engine."""

from src.detector import PIIDetector


def _make_detector() -> PIIDetector:
    return PIIDetector()


class TestEmailDetection:
    def test_detects_email(self):
        d = _make_detector()
        result = d.detect("Contact me at john@example.com")
        types = [e.entity_type for e in result.entities]
        assert "EMAIL_ADDRESS" in types

    def test_detects_multiple_emails(self):
        d = _make_detector()
        result = d.detect("Email a@b.com or c@d.com")
        emails = [e for e in result.entities if e.entity_type == "EMAIL_ADDRESS"]
        assert len(emails) >= 2


class TestNameDetection:
    def test_detects_person_name(self):
        d = _make_detector()
        result = d.detect("John Smith works at Acme Corp")
        types = [e.entity_type for e in result.entities]
        assert "PERSON" in types


class TestIPDetection:
    def test_detects_ipv4(self):
        d = _make_detector()
        result = d.detect("Server IP is 192.168.1.1")
        types = [e.entity_type for e in result.entities]
        assert "IP_ADDRESS" in types


class TestPhoneDetection:
    def test_detects_phone_number(self):
        d = _make_detector()
        result = d.detect("Call me at 555-867-5309 today")
        types = [e.entity_type for e in result.entities]
        assert "PHONE_NUMBER" in types


class TestNoPII:
    def test_clean_text_has_no_pii(self):
        d = _make_detector()
        result = d.detect("The sky is blue and grass is green")
        assert not result.has_pii

    def test_empty_text(self):
        d = _make_detector()
        result = d.detect("")
        assert result.entity_count == 0


class TestDictDetection:
    def test_detects_pii_in_dict_values(self):
        d = _make_detector()
        data = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "note": "No PII here",
        }
        results = d.detect_in_dict(data)
        assert "email" in results
        assert results["email"].has_pii
