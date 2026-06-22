import pytest
from bracket import bracket_size, total_rounds, first_round_pairings


def test_power_of_two_field():
    assert bracket_size(2) == 2
    assert bracket_size(4) == 4
    assert bracket_size(5) == 8
    assert bracket_size(8) == 8


def test_rounds_count():
    assert total_rounds(2) == 1
    assert total_rounds(4) == 2
    assert total_rounds(8) == 3


def test_fewer_than_two_raises():
    with pytest.raises(ValueError):
        bracket_size(1)


def test_byes_for_three_participants():
    pairings = first_round_pairings(["A", "B", "C"])
    assert len(pairings) == 2
    flat = [p for pair in pairings for p in pair]
    assert flat.count(None) == 1


def test_no_byes_for_power_of_two():
    pairings = first_round_pairings(["A", "B", "C", "D"])
    flat = [p for pair in pairings for p in pair]
    assert None not in flat
