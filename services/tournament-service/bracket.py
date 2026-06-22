"""
Pure bracket math, decoupled from Flask and the database so it can be
unit-tested on its own (see tests/test_bracket.py).
"""
import math


def bracket_size(n):
    """Next power of two >= n (the padded field size)."""
    if n < 2:
        raise ValueError("Need at least 2 participants to generate a bracket")
    return 2 ** math.ceil(math.log2(n))


def total_rounds(n):
    return int(math.log2(bracket_size(n)))


def first_round_pairings(participant_ids):
    """Pad with byes (None) to a power of two; return round-1 (a, b) pairs."""
    size = bracket_size(len(participant_ids))
    padded = list(participant_ids) + [None] * (size - len(participant_ids))
    return [(padded[i * 2], padded[i * 2 + 1]) for i in range(size // 2)]
