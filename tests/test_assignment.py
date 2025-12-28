import pytest

from app.services.assignment import AssignmentError, generate_assignments


def test_assignment_basic_bijection():
    participants = [1, 2, 3, 4]
    assignments = generate_assignments(participants, seed=42)
    assert set(assignments.keys()) == set(participants)
    assert set(assignments.values()) == set(participants)
    assert all(giver != receiver for giver, receiver in assignments.items())


def test_assignment_two_people():
    assignments = generate_assignments([10, 20], seed=1)
    assert assignments[10] == 20
    assert assignments[20] == 10


def test_assignment_deterministic_seed():
    participants = [1, 2, 3, 4, 5]
    first = generate_assignments(participants, seed=123)
    second = generate_assignments(participants, seed=123)
    assert first == second


def test_assignment_respects_exclusions():
    participants = [1, 2, 3]
    exclusions = [(1, 2)]
    assignments = generate_assignments(participants, exclusions=exclusions, seed=9)
    assert assignments[1] != 2


def test_assignment_respects_no_repeat():
    participants = [1, 2, 3]
    no_repeat = {1: 2}
    assignments = generate_assignments(participants, no_repeat_map=no_repeat, seed=5)
    assert assignments[1] != 2


def test_assignment_fails_for_too_few_participants():
    with pytest.raises(AssignmentError):
        generate_assignments([1])


def test_assignment_fails_for_tight_constraints():
    participants = [1, 2]
    exclusions = [(1, 2), (2, 1)]
    with pytest.raises(AssignmentError):
        generate_assignments(participants, exclusions=exclusions, seed=7)


def test_assignment_unique_receivers():
    participants = [1, 2, 3, 4, 5, 6]
    assignments = generate_assignments(participants, seed=77)
    assert len(set(assignments.values())) == len(participants)
