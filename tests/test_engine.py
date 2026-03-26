"""Tests for the PII-Safe engine (end-to-end pipeline)."""

import json

from src.engine import PIISafeEngine
from src.policies import BUILTIN_POLICIES, STRICT_POLICY


class TestScan:
    def test_scan_returns_sanitized_text(self):
        engine = PIISafeEngine()
        result = engine.scan("Email me at john@example.com")
        assert "john@example.com" not in result.sanitization.sanitized_text

    def test_scan_returns_privacy_score(self):
        engine = PIISafeEngine()
        result = engine.scan("John Smith, john@example.com, 192.168.1.1")
        assert result.privacy_score.score > 0
        assert result.privacy_score.level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_clean_text_scores_zero(self):
        engine = PIISafeEngine()
        result = engine.scan("The sky is blue and grass is green")
        assert result.privacy_score.score == 0.0
        assert result.privacy_score.level == "NONE"


class TestPolicySwitch:
    def test_can_switch_policy_by_name(self):
        engine = PIISafeEngine()
        engine.set_policy("strict")
        assert engine.policy.name == "strict"

    def test_strict_policy_redacts_names(self):
        engine = PIISafeEngine(policy=STRICT_POLICY)
        result = engine.scan("Contact John Smith")
        assert "John Smith" not in result.sanitization.sanitized_text
        assert "[REDACTED_PERSON]" in result.sanitization.sanitized_text

    def test_invalid_policy_raises(self):
        engine = PIISafeEngine()
        try:
            engine.set_policy("nonexistent")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


class TestDetectOnly:
    def test_detect_returns_entities_without_sanitizing(self):
        engine = PIISafeEngine()
        result = engine.detect("john@example.com")
        assert result.has_pii
        types = [e.entity_type for e in result.entities]
        assert "EMAIL_ADDRESS" in types


class TestDictScan:
    def test_scan_dict_finds_pii_in_values(self):
        engine = PIISafeEngine()
        data = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "note": "No PII here",
        }
        results = engine.scan_dict(data)
        assert "email" in results
        assert results["email"].detection.has_pii


class TestSerialization:
    def test_scan_result_serializes_to_json(self):
        engine = PIISafeEngine()
        result = engine.scan("john@example.com")
        data = result.to_dict()
        # Should be JSON-serializable
        json_str = json.dumps(data)
        assert "sanitized_text" in json_str
        assert "privacy_score" in json_str
