from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Sequence, Set, Tuple


class AssignmentError(RuntimeError):
    pass


@dataclass(frozen=True)
class AssignmentConstraints:
    exclusions: Set[Tuple[int, int]]
    no_repeat_map: Dict[int, int]


def _build_constraints(
    participant_ids: Sequence[int],
    exclusions: Optional[Iterable[Tuple[int, int]]],
    no_repeat_map: Optional[Dict[int, int]],
) -> AssignmentConstraints:
    exclusion_set = set(exclusions or [])
    no_repeat = dict(no_repeat_map or {})
    for participant_id in participant_ids:
        exclusion_set.add((participant_id, participant_id))
    return AssignmentConstraints(exclusions=exclusion_set, no_repeat_map=no_repeat)


def generate_assignments(
    participant_ids: Sequence[int],
    exclusions: Optional[Iterable[Tuple[int, int]]] = None,
    no_repeat_map: Optional[Dict[int, int]] = None,
    seed: Optional[int] = None,
    max_attempts: int = 200,
) -> Dict[int, int]:
    if len(participant_ids) < 2:
        raise AssignmentError("At least 2 participants are required.")

    rng = random.Random(seed)
    participants = list(participant_ids)
    constraints = _build_constraints(participants, exclusions, no_repeat_map)

    allowed_receivers = {
        giver: set(participants)
        - {giver}
        - {constraints.no_repeat_map.get(giver)}
        for giver in participants
    }

    for giver, receiver in constraints.exclusions:
        if giver in allowed_receivers:
            allowed_receivers[giver].discard(receiver)

    if any(not receivers for receivers in allowed_receivers.values()):
        raise AssignmentError("Assignment constraints are too strict to satisfy.")

    def backtrack(assignments: Dict[int, int], remaining_receivers: Set[int]) -> bool:
        if len(assignments) == len(participants):
            return True

        unassigned = [giver for giver in participants if giver not in assignments]
        giver = min(unassigned, key=lambda g: len(allowed_receivers[g] & remaining_receivers))
        choices = list(allowed_receivers[giver] & remaining_receivers)
        rng.shuffle(choices)
        for receiver in choices:
            assignments[giver] = receiver
            remaining_receivers.remove(receiver)
            if backtrack(assignments, remaining_receivers):
                return True
            remaining_receivers.add(receiver)
            assignments.pop(giver, None)
        return False

    for _ in range(max_attempts):
        rng.shuffle(participants)
        assignments: Dict[int, int] = {}
        remaining = set(participants)
        if backtrack(assignments, remaining):
            return assignments

    raise AssignmentError("Failed to generate assignments with the given constraints.")
