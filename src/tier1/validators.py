"""Post-match validators for Tier 1 regex detections.

Each validator runs ONLY on matched substrings — not on all input.
"""


def validate_credit_card(digits: str) -> bool:
    """Luhn checksum validation for credit card numbers."""
    cleaned = digits.replace(" ", "").replace("-", "")
    if not cleaned.isdigit() or len(cleaned) < 13 or len(cleaned) > 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(cleaned)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def validate_cpf(cpf: str) -> bool:
    """Brazilian CPF check digit verification."""
    cleaned = cpf.replace(".", "").replace("-", "")
    if not cleaned.isdigit() or len(cleaned) != 11:
        return False
    if cleaned == cleaned[0] * 11:
        return False

    # First check digit
    total = sum(int(cleaned[i]) * (10 - i) for i in range(9))
    remainder = total % 11
    d1 = 0 if remainder < 2 else 11 - remainder
    if int(cleaned[9]) != d1:
        return False

    # Second check digit
    total = sum(int(cleaned[i]) * (11 - i) for i in range(10))
    remainder = total % 11
    d2 = 0 if remainder < 2 else 11 - remainder
    return int(cleaned[10]) == d2


def validate_ip(ip: str) -> bool:
    """Validate IPv4: octets 0-255, reject version-number patterns."""
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        octets = [int(p) for p in parts]
    except ValueError:
        return False
    if not all(0 <= o <= 255 for o in octets):
        return False
    # Reject version patterns: all octets single-digit (e.g., 1.0.0.0, 2.0.0.1)
    if all(o <= 9 for o in octets):
        return False
    return True


def validate_email(email: str) -> bool:
    """Basic email structure validation."""
    if "@" not in email:
        return False
    local, _, domain = email.rpartition("@")
    if not local or not domain:
        return False
    if "." not in domain:
        return False
    tld = domain.rsplit(".", 1)[-1]
    return len(tld) >= 2
