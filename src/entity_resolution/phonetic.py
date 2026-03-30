"""Double Metaphone implementation for phonetic entity matching.

Simplified but functional implementation focused on common English name patterns.
Produces primary and secondary phonetic codes (max 4 chars each).
"""

_VOWELS = frozenset("AEIOUY")


def double_metaphone(word: str) -> tuple[str, str]:
    """Generate Double Metaphone codes for a word.

    Returns (primary, secondary) codes, each up to 4 characters.
    """
    if not word:
        return ("", "")

    # Normalize
    w = word.upper().strip()
    w = "".join(c for c in w if c.isalpha())
    if not w:
        return ("", "")

    primary: list[str] = []
    secondary: list[str] = []
    pos = 0
    length = len(w)
    max_len = 4

    def _at(i: int) -> str:
        return w[i] if 0 <= i < length else ""

    def _slice(i: int, n: int) -> str:
        return w[i : i + n] if i >= 0 else ""

    def _add(p: str, s: str | None = None) -> None:
        if s is None:
            s = p
        if p and len(primary) < max_len:
            primary.append(p)
        if s and len(secondary) < max_len:
            secondary.append(s)

    # Handle initial silent letters
    if _slice(0, 2) in ("GN", "KN", "PN", "AE", "WR"):
        pos = 1

    # Initial X -> S
    if _at(0) == "X":
        _add("S")
        pos = 1

    while pos < length and (len(primary) < max_len or len(secondary) < max_len):
        c = _at(pos)

        # Vowels: only contribute at start
        if c in _VOWELS:
            if pos == 0:
                _add("A")
            pos += 1
            continue

        if c == "B":
            _add("P")
            pos += 2 if _at(pos + 1) == "B" else 1

        elif c == "C":
            if _slice(pos, 2) == "CH":
                _add("X")
                pos += 2
            elif _slice(pos, 2) in ("CI", "CE", "CY"):
                _add("S")
                pos += 2
            else:
                _add("K")
                pos += 2 if _at(pos + 1) == "C" else 1

        elif c == "D":
            if _slice(pos, 2) in ("DG",):
                if _at(pos + 2) in ("I", "E", "Y"):
                    _add("J")
                    pos += 3
                else:
                    _add("TK")
                    pos += 2
            else:
                _add("T")
                pos += 2 if _at(pos + 1) == "D" else 1

        elif c == "F":
            _add("F")
            pos += 2 if _at(pos + 1) == "F" else 1

        elif c == "G":
            if _at(pos + 1) == "H":
                if pos > 0 and _at(pos - 1) not in _VOWELS:
                    pos += 2
                    continue
                _add("K")
                pos += 2
            elif _at(pos + 1) in ("I", "E", "Y"):
                _add("J", "K")
                pos += 2
            elif _at(pos + 1) == "G":
                _add("K")
                pos += 2
            elif _at(pos + 1) == "N":
                pos += 2
                continue
            else:
                _add("K")
                pos += 1

        elif c == "H":
            if _at(pos + 1) in _VOWELS and (pos == 0 or _at(pos - 1) not in _VOWELS):
                _add("H")
            pos += 1

        elif c == "J":
            _add("J")
            pos += 2 if _at(pos + 1) == "J" else 1

        elif c == "K":
            _add("K")
            pos += 2 if _at(pos + 1) == "K" else 1

        elif c == "L":
            _add("L")
            pos += 2 if _at(pos + 1) == "L" else 1

        elif c == "M":
            _add("M")
            pos += 2 if _at(pos + 1) == "M" else 1

        elif c == "N":
            _add("N")
            pos += 2 if _at(pos + 1) == "N" else 1

        elif c == "P":
            if _at(pos + 1) == "H":
                _add("F")
                pos += 2
            else:
                _add("P")
                pos += 2 if _at(pos + 1) == "P" else 1

        elif c == "Q":
            _add("K")
            pos += 2 if _at(pos + 1) == "Q" else 1

        elif c == "R":
            _add("R")
            pos += 2 if _at(pos + 1) == "R" else 1

        elif c == "S":
            if _slice(pos, 2) == "SH":
                _add("X")
                pos += 2
            elif _slice(pos, 3) in ("SIO", "SIA"):
                _add("X")
                pos += 3
            else:
                _add("S")
                pos += 2 if _at(pos + 1) == "S" else 1

        elif c == "T":
            if _slice(pos, 3) in ("TIA", "TIO"):
                _add("X")
                pos += 3
            elif _slice(pos, 2) == "TH":
                _add("0")  # theta
                pos += 2
            else:
                _add("T")
                pos += 2 if _at(pos + 1) == "T" else 1

        elif c == "V":
            _add("F")
            pos += 2 if _at(pos + 1) == "V" else 1

        elif c == "W":
            if _at(pos + 1) in _VOWELS:
                _add("W")
                pos += 2
            else:
                pos += 1

        elif c == "X":
            _add("KS")
            pos += 2 if _at(pos + 1) == "X" else 1

        elif c == "Y":
            if _at(pos + 1) in _VOWELS:
                _add("Y")
                pos += 2
            else:
                pos += 1

        elif c == "Z":
            _add("S")
            pos += 2 if _at(pos + 1) == "Z" else 1

        else:
            pos += 1

    return ("".join(primary)[:max_len], "".join(secondary)[:max_len])
