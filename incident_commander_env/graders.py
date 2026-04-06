"""
Deterministic Graders for the Incident Commander Environment.

Each grader evaluates an agent's performance on a scenario and returns
a score in [0.0, 1.0]. Same actions on same scenario = same score, always.

Scoring components (weighted):
- Priority accuracy:      25%
- Team routing accuracy:  25%
- Correlation accuracy:   20%
- Escalation judgment:    15%
- Time efficiency:        10%
- Communication:           5%
"""

from typing import Dict, List, Optional, Set, Tuple

try:
    from .models import (
        Alert,
        AlertGroundTruth,
        AlertStatus,
        EscalationLevel,
        EscalationState,
        IncidentState,
        Priority,
        ScenarioGroundTruth,
        Team,
    )
except ImportError:
    from models import (
        Alert,
        AlertGroundTruth,
        AlertStatus,
        EscalationLevel,
        EscalationState,
        IncidentState,
        Priority,
        ScenarioGroundTruth,
        Team,
    )


# ─── Escalation Level Ordering ───────────────────────────────────────────────

ESCALATION_ORDER = {
    EscalationLevel.NONE: 0,
    EscalationLevel.ON_CALL_LEAD: 1,
    EscalationLevel.VP_ENG: 2,
    EscalationLevel.CTO: 3,
}


def _escalation_score(
    actual_level: EscalationLevel,
    required_level: EscalationLevel,
) -> float:
    """Score escalation judgment.

    Returns:
        1.0 if correct level
        0.5 if one level off
        0.0 if two+ levels off or way over-escalated
    """
    actual = ESCALATION_ORDER[actual_level]
    required = ESCALATION_ORDER[required_level]
    diff = actual - required

    if diff == 0:
        return 1.0
    elif diff == 1:
        # Slightly over-escalated — not great but not terrible
        return 0.5
    elif diff == -1:
        # Under-escalated by one — also partial credit
        return 0.4
    elif diff >= 2:
        # Way over-escalated — alert fatigue!
        return 0.1
    else:
        # Way under-escalated — missed critical situation
        return 0.1


def _priority_accuracy(
    alerts: List[Alert],
    truths: List[AlertGroundTruth],
) -> float:
    """Score priority assignment accuracy.

    Returns fraction of alerts with correctly assigned priority.
    Unassigned priorities count as incorrect.
    """
    truth_map = {t.alert_id: t for t in truths}
    correct = 0
    total = len(truths)

    if total == 0:
        return 1.0

    for alert in alerts:
        truth = truth_map.get(alert.alert_id)
        if truth is None:
            continue

        if alert.assigned_priority is not None:
            if alert.assigned_priority == truth.correct_priority:
                correct += 1
            elif _priority_distance(alert.assigned_priority, truth.correct_priority) == 1:
                # One level off gets partial credit
                correct += 0.4

    return correct / total


def _priority_distance(a: Priority, b: Priority) -> int:
    """Distance between two priority levels."""
    order = {Priority.P1: 1, Priority.P2: 2, Priority.P3: 3, Priority.P4: 4}
    return abs(order[a] - order[b])


def _team_routing_accuracy(
    alerts: List[Alert],
    truths: List[AlertGroundTruth],
) -> float:
    """Score team assignment accuracy.

    Returns fraction of alerts routed to the correct team.
    """
    truth_map = {t.alert_id: t for t in truths}
    correct = 0
    total = len(truths)

    if total == 0:
        return 1.0

    for alert in alerts:
        truth = truth_map.get(alert.alert_id)
        if truth is None:
            continue

        if alert.assigned_team is not None:
            if alert.assigned_team.lower() == truth.correct_team.value.lower():
                correct += 1

    return correct / total


def _correlation_accuracy(
    agent_groups: Dict[str, List[str]],
    truth_groups: Dict[str, List[str]],
) -> float:
    """Score how well the agent grouped related alerts.

    Uses set comparison — if the agent created groups that match
    the ground truth groupings (regardless of group names), that's correct.

    Returns a score in [0.0, 1.0].
    """
    if not truth_groups:
        return 1.0

    # Convert truth groups to sets of frozensets for comparison
    truth_sets: List[frozenset] = [
        frozenset(ids) for ids in truth_groups.values()
        if len(ids) > 1  # Only count groups with 2+ alerts
    ]

    if not truth_sets:
        return 1.0

    # Convert agent groups to sets
    agent_sets: List[frozenset] = [
        frozenset(ids) for ids in agent_groups.values()
        if len(ids) > 1
    ]

    if not agent_sets:
        return 0.0

    # Score: for each truth group, what's the best overlap with any agent group?
    total_score = 0.0
    for truth_set in truth_sets:
        best_overlap = 0.0
        for agent_set in agent_sets:
            intersection = len(truth_set & agent_set)
            union = len(truth_set | agent_set)
            if union > 0:
                jaccard = intersection / union
                best_overlap = max(best_overlap, jaccard)
        total_score += best_overlap

    return total_score / len(truth_sets)


def _time_efficiency(
    steps_taken: int,
    min_steps_possible: int,
    max_steps: int,
) -> float:
    """Score time efficiency.

    Perfect score if done in minimum steps.
    Linear decay to 0 at max_steps.
    """
    if steps_taken <= min_steps_possible:
        return 1.0

    remaining_range = max_steps - min_steps_possible
    if remaining_range <= 0:
        return 1.0

    excess_steps = steps_taken - min_steps_possible
    efficiency = max(0.0, 1.0 - (excess_steps / remaining_range))
    return efficiency


def _communication_score(
    updates_sent: int,
    required_updates: int,
) -> float:
    """Score communication (status updates sent).

    Full score if at least required updates sent.
    Partial for fewer. Slight penalty for excessive (>3x) updates (spam).
    """
    if required_updates == 0:
        return 1.0

    if updates_sent >= required_updates:
        if updates_sent > required_updates * 3:
            # Spamming updates also bad
            return 0.6
        return 1.0

    return updates_sent / required_updates


def grade_episode(
    state: IncidentState,
    ground_truth: ScenarioGroundTruth,
    max_steps: int,
) -> Tuple[float, Dict[str, float]]:
    """Grade a complete episode.

    Args:
        state: Final environment state after episode
        ground_truth: Ground truth solution
        max_steps: Maximum allowed steps

    Returns:
        Tuple of (final_score, component_scores)
        where final_score is in [0.0, 1.0]
    """
    # Component scores
    priority_score = _priority_accuracy(state.alerts, ground_truth.alert_truths)
    team_score = _team_routing_accuracy(state.alerts, ground_truth.alert_truths)
    correlation_score = _correlation_accuracy(
        state.correlated_groups, ground_truth.correlation_groups
    )
    escalation_score_val = _escalation_score(
        state.escalation_state.current_level,
        ground_truth.required_escalation_level,
    )
    efficiency_score = _time_efficiency(
        state.step_count, ground_truth.min_steps_possible, max_steps
    )
    comm_score = _communication_score(
        state.updates_sent, ground_truth.required_status_updates
    )

    # Weighted final score
    components = {
        "priority_accuracy": priority_score,
        "team_routing_accuracy": team_score,
        "correlation_accuracy": correlation_score,
        "escalation_judgment": escalation_score_val,
        "time_efficiency": efficiency_score,
        "communication": comm_score,
    }

    weights = {
        "priority_accuracy": 0.25,
        "team_routing_accuracy": 0.25,
        "correlation_accuracy": 0.20,
        "escalation_judgment": 0.15,
        "time_efficiency": 0.10,
        "communication": 0.05,
    }

    final_score = sum(
        components[k] * weights[k] for k in components
    )

    # Clamp to [0, 1]
    final_score = max(0.0, min(1.0, final_score))

    return final_score, components
