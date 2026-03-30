"""Tests for Tier 1: Pure regex PII detection engine."""

import time

import pytest

from src.tier1 import scan
from src.tier1.validators import validate_credit_card, validate_cpf, validate_email, validate_ip


# ── Detection tests ──────────────────────────────────────────────


class TestDetection:
    def test_detect_email(self):
        results = scan("Contact john@example.com for details")
        assert len(results) == 1
        assert results[0].entity_type == "EMAIL_ADDRESS"
        assert results[0].text == "john@example.com"

    def test_detect_phone(self):
        results = scan("Call 555-123-4567 now")
        assert len(results) == 1
        assert results[0].entity_type == "PHONE_NUMBER"

    def test_detect_phone_with_country(self):
        results = scan("Call +1 (555) 123-4567 now")
        assert len(results) == 1
        assert results[0].entity_type == "PHONE_NUMBER"

    def test_detect_ipv4(self):
        results = scan("Server at 192.168.1.100 is down")
        assert len(results) == 1
        assert results[0].entity_type == "IP_ADDRESS"
        assert results[0].text == "192.168.1.100"

    def test_detect_credit_card(self):
        # Luhn-valid Visa test number
        results = scan("CC: 4532015112830366")
        cc_results = [r for r in results if r.entity_type == "CREDIT_CARD"]
        assert len(cc_results) == 1

    def test_detect_ssn(self):
        results = scan("SSN: 123-45-6789")
        assert len(results) == 1
        assert results[0].entity_type == "US_SSN"

    def test_detect_cpf(self):
        # Valid CPF: 529.982.247-25
        results = scan("CPF: 529.982.247-25")
        assert len(results) == 1
        assert results[0].entity_type == "BRAZILIAN_CPF"

    def test_detect_api_key(self):
        results = scan("Key: sk-abcdefghijklmnopqrstuvwxyz")
        assert len(results) == 1
        assert results[0].entity_type == "API_KEY"


# ── False positive rejection ─────────────────────────────────────


class TestFalsePositiveRejection:
    def test_reject_invalid_credit_card(self):
        # Random digits that fail Luhn
        results = scan("Number: 1234567890123456")
        cc_results = [r for r in results if r.entity_type == "CREDIT_CARD"]
        assert len(cc_results) == 0

    def test_reject_version_as_ip(self):
        results = scan("version 2.0.0.1")
        ip_results = [r for r in results if r.entity_type == "IP_ADDRESS"]
        assert len(ip_results) == 0

    def test_reject_invalid_cpf(self):
        # All same digits = invalid
        results = scan("CPF: 111.111.111-11")
        cpf_results = [r for r in results if r.entity_type == "BRAZILIAN_CPF"]
        assert len(cpf_results) == 0

    def test_reject_invalid_email(self):
        results = scan("not-an-email")
        email_results = [r for r in results if r.entity_type == "EMAIL_ADDRESS"]
        assert len(email_results) == 0

    def test_reject_short_api_key(self):
        results = scan("sk-short")
        api_results = [r for r in results if r.entity_type == "API_KEY"]
        assert len(api_results) == 0


# ── Combined / edge cases ────────────────────────────────────────


class TestCombined:
    def test_multiple_pii_types(self):
        text = "Email john@test.com, phone 555-123-4567, IP 192.168.1.100"
        results = scan(text)
        types = {r.entity_type for r in results}
        assert "EMAIL_ADDRESS" in types
        assert "PHONE_NUMBER" in types
        assert "IP_ADDRESS" in types

    def test_clean_text(self):
        results = scan("The weather is nice today")
        assert len(results) == 0

    def test_empty_string(self):
        results = scan("")
        assert len(results) == 0

    def test_confidence_with_validator(self):
        results = scan("Server at 192.168.1.100")
        assert results[0].confidence == 1.0  # IP has validator

    def test_confidence_without_validator(self):
        results = scan("SSN: 123-45-6789")
        assert results[0].confidence == 0.95  # SSN has no validator


# ── Validator unit tests ─────────────────────────────────────────


class TestValidators:
    def test_luhn_known_valid(self):
        assert validate_credit_card("4532015112830366") is True
        assert validate_credit_card("5425233430109903") is True

    def test_luhn_known_invalid(self):
        assert validate_credit_card("1234567890123456") is False

    def test_cpf_valid(self):
        assert validate_cpf("529.982.247-25") is True

    def test_cpf_invalid_check_digits(self):
        assert validate_cpf("529.982.247-26") is False

    def test_cpf_all_same(self):
        assert validate_cpf("111.111.111-11") is False

    def test_ip_valid(self):
        assert validate_ip("192.168.1.100") is True
        assert validate_ip("10.0.0.1") is True

    def test_ip_reject_version_pattern(self):
        assert validate_ip("2.0.0.1") is False  # all single-digit octets

    def test_email_valid(self):
        assert validate_email("user@example.com") is True
        assert validate_email("user.name+tag@domain.co.uk") is True

    def test_email_invalid(self):
        assert validate_email("no-at-sign") is False
        assert validate_email("@no-local.com") is False


# ── Performance test ─────────────────────────────────────────────


class TestPerformance:
    def test_scan_latency(self):
        text = (
            "Contact john@example.com at 555-123-4567. "
            "Server 192.168.1.100 in datacenter. "
            "CC: 4532015112830366. SSN: 123-45-6789. "
            "CPF: 529.982.247-25. Key: sk-abcdefghijklmnopqrstuvwxyz. "
            "Additional context text to pad the string to approximately "
            "five hundred characters for a realistic benchmark scenario "
            "that simulates typical agent tool-call payload sizes."
        )
        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            scan(text)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / iterations) * 1000
        # Should be well under 0.5ms per scan
        assert avg_ms < 0.5, f"Average scan latency {avg_ms:.3f}ms exceeds 0.5ms"
