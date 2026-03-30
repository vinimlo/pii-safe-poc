"""Similarity computation primitives for entity resolution.

All pure Python — no external dependencies. Implements:
- Damerau-Levenshtein distance (with transpositions)
- Character trigram generation and Jaccard similarity
- Token-level Jaccard similarity
- MinHash signature generation
- LSH banding for approximate nearest neighbor retrieval
"""

import hashlib
from typing import Sequence

# Large prime for MinHash hash functions
_LARGE_PRIME = 2_147_483_647  # 2^31 - 1

# Fixed seed coefficients for MinHash reproducibility
_MINHASH_A = [
    982451653, 472882027, 920419823, 715827883, 553105243,
    393342743, 261534853, 180143327, 104729587, 86028121,
    73856093, 64439929, 52361161, 43112609, 37139213,
    32452843, 27644437, 24036583, 20396989, 17624813,
    15485863, 13686517, 12105877, 10711523, 9576891,
    8495693, 7594753, 6776221, 5994983, 5346277,
    4759123, 4256233, 3796879, 3393491, 3037000499,
    2717084437, 2434612897, 2180083753, 1951356377, 1746262553,
    1562504947, 1398101329, 1250264587, 1117291457, 998632621,
    893871739, 799497659, 714954853, 639001891, 570908947,
    510067913, 455978177, 407556403, 364093697, 325324643,
    290633987, 259789721, 232124903, 207474013, 185362447,
    165580141, 148035889, 132387563, 118370887,
]

_MINHASH_B = [
    314159265, 271828182, 141421356, 173205080, 223606797,
    244948974, 264575131, 282842712, 300000000, 316227766,
    331662479, 346410161, 360555127, 374165738, 387298334,
    400000000, 412310562, 424264068, 435889894, 447213595,
    458257569, 469041575, 479583152, 489897948, 500000000,
    509901951, 519615242, 529150262, 538516480, 547722557,
    556776435, 565685424, 574456264, 583095189, 591607978,
    600000000, 608276252, 616441400, 624499799, 632455532,
    640312423, 648074069, 655743852, 663324958, 670820393,
    678232998, 685565460, 692820323, 700000000, 707106781,
    714142842, 721110255, 728010988, 734846922, 741619848,
    748331477, 754983443, 761577310, 768114574, 774596669,
    781024967, 787400787, 793725393, 800000000,
]


def damerau_levenshtein(s1: str, s2: str) -> int:
    """Damerau-Levenshtein distance supporting transpositions."""
    len1, len2 = len(s1), len(s2)
    # Optimal string alignment variant
    d = [[0] * (len2 + 1) for _ in range(len1 + 1)]

    for i in range(len1 + 1):
        d[i][0] = i
    for j in range(len2 + 1):
        d[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,      # deletion
                d[i][j - 1] + 1,      # insertion
                d[i - 1][j - 1] + cost,  # substitution
            )
            # Transposition
            if (
                i > 1
                and j > 1
                and s1[i - 1] == s2[j - 2]
                and s1[i - 2] == s2[j - 1]
            ):
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)

    return d[len1][len2]


def normalized_damerau_levenshtein(s1: str, s2: str) -> float:
    """Normalized Damerau-Levenshtein: 1.0 = identical, 0.0 = completely different."""
    if not s1 and not s2:
        return 1.0
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return 1.0 - (damerau_levenshtein(s1, s2) / max_len)


def character_trigrams(s: str) -> set[str]:
    """Generate character trigrams from a string."""
    if len(s) < 3:
        return {s} if s else set()
    return {s[i : i + 3] for i in range(len(s) - 2)}


def trigram_jaccard(s1: str, s2: str) -> float:
    """Jaccard similarity of character trigrams. Returns [0, 1]."""
    t1 = character_trigrams(s1.lower())
    t2 = character_trigrams(s2.lower())
    if not t1 and not t2:
        return 1.0
    if not t1 or not t2:
        return 0.0
    intersection = len(t1 & t2)
    union = len(t1 | t2)
    return intersection / union if union > 0 else 0.0


def token_jaccard(s1: str, s2: str) -> float:
    """Jaccard similarity of lowercased word tokens. Returns [0, 1]."""
    t1 = set(s1.lower().split())
    t2 = set(s2.lower().split())
    if not t1 and not t2:
        return 1.0
    if not t1 or not t2:
        return 0.0
    intersection = len(t1 & t2)
    union = len(t1 | t2)
    return intersection / union if union > 0 else 0.0


def _hash_trigram(trigram: str, a: int, b: int) -> int:
    """Hash a trigram with given coefficients for MinHash."""
    h = int(hashlib.md5(trigram.encode()).hexdigest(), 16)
    return (a * h + b) % _LARGE_PRIME


def minhash_signature(trigrams: set[str], num_hashes: int = 64) -> tuple[int, ...]:
    """Generate MinHash signature from a set of trigrams.

    Uses num_hashes independent hash functions with fixed seeds.
    Returns tuple of num_hashes minimum hash values.
    """
    if not trigrams:
        return tuple([_LARGE_PRIME] * num_hashes)

    sig = []
    for i in range(num_hashes):
        a = _MINHASH_A[i % len(_MINHASH_A)]
        b = _MINHASH_B[i % len(_MINHASH_B)]
        min_hash = min(_hash_trigram(t, a, b) for t in trigrams)
        sig.append(min_hash)
    return tuple(sig)


def lsh_bands(
    signature: tuple[int, ...],
    num_bands: int = 32,
    rows_per_band: int = 2,
) -> list[int]:
    """Split MinHash signature into bands and hash each band for LSH.

    With b=32 bands and r=2 rows, two signatures with Jaccard ~0.43
    have ~86% probability of sharing at least one band.
    """
    bands = []
    for b in range(num_bands):
        start = b * rows_per_band
        end = start + rows_per_band
        band_slice = signature[start:end]
        band_hash = hash(band_slice)
        bands.append(band_hash)
    return bands


def phonetic_similarity(code1: str, code2: str) -> float:
    """Similarity between two phonetic codes based on character overlap."""
    if not code1 and not code2:
        return 1.0
    if not code1 or not code2:
        return 0.0
    max_len = max(len(code1), len(code2))
    matches = sum(1 for a, b in zip(code1, code2) if a == b)
    return matches / max_len
