"""
Deterministic Graders for the Incident Commander Environment.

Each grader evaluates an agent's performance on a scenario and returns
a score in [0.0, 1.0]. Same actions on same scenario = same score, always.

Scoring components (weighted):
- Priority accuracy:          20%
- Team routing accuracy:      20%
- Correlation accuracy:       15%
- Escalation judgment:        15%
- Root cause identification:  10%  (was root cause investigated or postmortem correct?)
- Communication:               7%
- Time efficiency:             8%
- SLA compliance:              5%
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
        PostmortemData,
        Priority,
        ScenarioGroundTruth,
        SLATimer,
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
        PostmortemData,
        Priority,
        ScenarioGroundTruth,
        SLATimer,
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


def _root_cause_identification_score(
    investigation_results: Dict[str, str],
    truths: List[AlertGroundTruth],
    postmortem: Optional["PostmortemData"] = None,
) -> float:
    """Score whether the agent correctly identified the root cause.

    Two paths to full credit:
    1. Agent wrote a postmortem with the correct root_cause_alert_id (best signal)
    2. Agent investigated the root cause alert using the investigate() tool

    Returns 1.0 for full credit, 0.0 if root cause was never identified.
    """
    root_cause_ids = {t.alert_id for t in truths if t.is_root_cause}

    if not root_cause_ids:
        return 1.0  # No root cause defined — full credit

    # Path 1: postmortem correctly identifies root cause
    if postmortem is not None:
        if postmortem.root_cause_alert_id in root_cause_ids:
            return 1.0

    # Path 2: root cause alert was investigated
    investigated = set(investigation_results.keys())
    if root_cause_ids & investigated:
        return 0.75  # Partial credit — found it but didn't write postmortem

    return 0.0


def _sla_compliance_score(
    alerts: List[Alert],
    sla_timers: Optional[List["SLATimer"]],
) -> float:
    """Score SLA compliance — did high-priority alerts get assigned before timers breached?

    Penalizes P1/P2 alerts whose SLA timer breached while still unassigned.
    Full score if no P1/P2 SLA breaches occurred.
    """
    if not sla_timers:
        return 1.0

    alert_map = {a.alert_id: a for a in alerts}
    violations = 0
    total_high_priority = 0

    for timer in sla_timers:
        alert = alert_map.get(timer.alert_id)
        if alert is None:
            continue
        # Only track P1/P2 alerts for SLA
        if alert.assigned_priority in (Priority.P1, Priority.P2):
            total_high_priority += 1
            if timer.breached and alert.assigned_team is None:
                violations += 1

    if total_high_priority == 0:
        return 1.0

    return max(0.0, 1.0 - (violations / total_high_priority))


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


def _generate_feedback(
    components: Dict[str, float],
    weights: Dict[str, float],
    state: IncidentState,
    ground_truth: ScenarioGroundTruth,
    sla_timers: Optional[List["SLATimer"]] = None,
) -> str:
    """Generate human-readable feedback explaining the score breakdown.

    This feedback teaches agents what they did well and where they lost points,
    enabling iterative improvement.
    """
    feedback_lines: List[str] = []
    total_lost = 0.0

    # Priority accuracy feedback
    if components["priority_accuracy"] < 1.0:
        lost = (1.0 - components["priority_accuracy"]) * weights["priority_accuracy"]
        total_lost += lost
        wrong = sum(
            1 for a in state.alerts
            for t in ground_truth.alert_truths
            if t.alert_id == a.alert_id and a.assigned_priority is not None
            and a.assigned_priority != t.correct_priority
        )
        unassigned = sum(
            1 for t in ground_truth.alert_truths
            if not any(a.alert_id == t.alert_id and a.assigned_priority is not None for a in state.alerts)
        )
        if wrong > 0:
            feedback_lines.append(f"Priority: {wrong} alert(s) had incorrect priority. Cost: -{lost:.2f}")
        if unassigned > 0:
            feedback_lines.append(f"Priority: {unassigned} alert(s) were never prioritized. Cost: -{lost:.2f}")

    # Team routing feedback
    if components["team_routing_accuracy"] < 1.0:
        lost = (1.0 - components["team_routing_accuracy"]) * weights["team_routing_accuracy"]
        total_lost += lost
        misrouted = sum(
            1 for a in state.alerts
            for t in ground_truth.alert_truths
            if t.alert_id == a.alert_id and a.assigned_team is not None
            and a.assigned_team.lower() != t.correct_team.value.lower()
        )
        feedback_lines.append(f"Routing: {misrouted} alert(s) sent to wrong team. Cost: -{lost:.2f}")

    # Escalation feedback
    if components["escalation_judgment"] < 1.0:
        lost = (1.0 - components["escalation_judgment"]) * weights["escalation_judgment"]
        total_lost += lost
        actual = state.escalation_state.current_level.value
        required = ground_truth.required_escalation_level.value
        if ESCALATION_ORDER.get(state.escalation_state.current_level, 0) > \
           ESCALATION_ORDER.get(ground_truth.required_escalation_level, 0):
            feedback_lines.append(
                f"Escalation: Over-escalated to '{actual}' (needed '{required}'). "
                f"Alert fatigue risk. Cost: -{lost:.2f}"
            )
        else:
            feedback_lines.append(
                f"Escalation: Under-escalated at '{actual}' (needed '{required}'). "
                f"Critical situation may have been missed. Cost: -{lost:.2f}"
            )

    # Root cause feedback
    if components["root_cause_identification"] < 1.0:
        lost = (1.0 - components["root_cause_identification"]) * weights["root_cause_identification"]
        total_lost += lost
        root_ids = {t.alert_id for t in ground_truth.alert_truths if t.is_root_cause}
        if state.postmortem is None:
            feedback_lines.append(
                f"Root Cause: No postmortem written. Root cause alert(s): {root_ids}. Cost: -{lost:.2f}"
            )
        else:
            feedback_lines.append(
                f"Root Cause: Postmortem identified '{state.postmortem.root_cause_alert_id}' "
                f"but actual root cause was {root_ids}. Cost: -{lost:.2f}"
            )

    # SLA compliance feedback
    if components["sla_compliance"] < 1.0:
        lost = (1.0 - components["sla_compliance"]) * weights["sla_compliance"]
        total_lost += lost
        breached = sum(1 for t in (sla_timers or []) if t.breached)
        feedback_lines.append(
            f"SLA: {breached} SLA timer(s) breached before alerts were assigned. Cost: -{lost:.2f}"
        )

    # Communication feedback
    if components["communication"] < 1.0:
        lost = (1.0 - components["communication"]) * weights["communication"]
        total_lost += lost
        feedback_lines.append(
            f"Communication: Sent {state.updates_sent}/{ground_truth.required_status_updates} "
            f"required status updates. Cost: -{lost:.2f}"
        )

    # Correlation feedback
    if components["correlation_accuracy"] < 1.0:
        lost = (1.0 - components["correlation_accuracy"]) * weights["correlation_accuracy"]
        total_lost += lost
        feedback_lines.append(
            f"Correlation: Alert groups did not match expected incident groupings. Cost: -{lost:.2f}"
        )

    # Time efficiency feedback
    if components["time_efficiency"] < 0.5:
        lost = (1.0 - components["time_efficiency"]) * weights["time_efficiency"]
        total_lost += lost
        feedback_lines.append(
            f"Efficiency: Used {state.step_count} steps (optimal: {ground_truth.min_steps_possible}). Cost: -{lost:.2f}"
        )

    # Positive feedback
    strengths = []
    if components["priority_accuracy"] >= 0.9:
        strengths.append("priority assignment")
    if components["team_routing_accuracy"] >= 0.9:
        strengths.append("team routing")
    if components["root_cause_identification"] >= 1.0:
        strengths.append("root cause identification")
    if components["escalation_judgment"] >= 1.0:
        strengths.append("escalation judgment")
    if components["sla_compliance"] >= 1.0:
        strengths.append("SLA compliance")

    result_parts = []
    if strengths:
        result_parts.append(f"Strengths: {', '.join(strengths)}")
    if feedback_lines:
        result_parts.append("Areas for improvement:")
        result_parts.extend(f"  • {line}" for line in feedback_lines)
    else:
        result_parts.append("Perfect performance — no points lost!")

    return "\n".join(result_parts)


def grade_episode(
    state: IncidentState,
    ground_truth: ScenarioGroundTruth,
    max_steps: int,
    sla_timers: Optional[List["SLATimer"]] = None,
) -> Tuple[float, Dict[str, float]]:
    """Grade a complete episode.

    Args:
        state: Final environment state after episode
        ground_truth: Ground truth solution
        max_steps: Maximum allowed steps
        sla_timers: SLA timer objects with breach status (optional)

    Returns:
        Tuple of (final_score, detailed_result)
        where final_score is in [0.0, 1.0] and detailed_result contains
        component scores and textual feedback.
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
    root_cause_score = _root_cause_identification_score(
        state.investigation_results,
        ground_truth.alert_truths,
        state.postmortem,
    )
    sla_score = _sla_compliance_score(state.alerts, sla_timers)

    # Weighted final score — weights sum to 1.0
    components = {
        "priority_accuracy": priority_score,
        "team_routing_accuracy": team_score,
        "correlation_accuracy": correlation_score,
        "escalation_judgment": escalation_score_val,
        "root_cause_identification": root_cause_score,
        "time_efficiency": efficiency_score,
        "communication": comm_score,
        "sla_compliance": sla_score,
    }

    weights = {
        "priority_accuracy": 0.20,
        "team_routing_accuracy": 0.20,
        "correlation_accuracy": 0.15,
        "escalation_judgment": 0.15,
        "root_cause_identification": 0.10,
        "time_efficiency": 0.08,
        "communication": 0.07,
        "sla_compliance": 0.05,
    }

    final_score = sum(components[k] * weights[k] for k in components)

    # Clamp to [0, 1]
    final_score = max(0.0, min(1.0, final_score))

    # Generate detailed textual feedback
    feedback = _generate_feedback(components, weights, state, ground_truth, sla_timers)

    # Return enriched result — components dict now includes feedback
    components["feedback"] = feedback  # type: ignore[assignment]

    return final_score, components
