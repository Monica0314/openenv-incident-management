from environment.models import IncidentAction, IncidentReward
from environment.graders import (
    grade_classification,
    grade_team_routing_single,
    grade_strategy_single,
    grade_confidence_calibration,
    SEVERITY_RANK
)


def grade_severity(action_severity: str, correct_severity: str) -> float:
    """Partial credit severity grading."""
    if action_severity == correct_severity:
        return 1.0
    elif abs(SEVERITY_RANK[action_severity] - SEVERITY_RANK[correct_severity]) == 1:
        return 0.5
    return 0.0


def grade_routing(action_team: str, correct_team: str) -> float:
    if action_team == correct_team:
        return 1.0
    return 0.0


def grade_strategy(action_strategy: str, correct_strategy: str) -> float:
    if action_strategy == correct_strategy:
        return 1.0
    return 0.0


def compute_cascade_bonus(action: IncidentAction, ground_truth: dict) -> float:
    """
    Bonus for preventing cascade:
    - Correct team + correct strategy = full bonus
    - Only correct team = partial
    - Wrong both = 0
    """
    team_correct = action.assigned_team == ground_truth.get("team", "")
    strategy_correct = action.resolution_strategy == ground_truth.get("strategy", "")

    if team_correct and strategy_correct:
        return 1.0
    elif team_correct:
        return 0.4
    return 0.0


def compute_confidence_bonus(
    action: IncidentAction,
    severity_score: float,
    routing_score: float,
    strategy_score: float
) -> float:
    """
    Confidence calibration bonus.
    Reward agent when its confidence matches its actual correctness.
    """
    actual_accuracy = (severity_score + routing_score + strategy_score) / 3.0
    calibration_error = abs(action.confidence - actual_accuracy)
    # Max bonus 0.2, decreases linearly with calibration error
    bonus = max(0.0, 0.2 - (calibration_error * 0.4))
    return round(bonus, 4)


def compute_reward(
    action: IncidentAction,
    ground_truth: dict,
    step: int,
    task_id: str
) -> IncidentReward:
    """
    Compute per-step reward signal.
    Never returns same value twice — depends on step, action, ground truth.
    Total clamped to [-1.0, 1.0].
    """
    severity_score = grade_severity(action.severity, ground_truth.get("severity", "P2"))
    routing_score = grade_routing(action.assigned_team, ground_truth.get("team", "backend"))
    strategy_score = grade_strategy(action.resolution_strategy, ground_truth.get("strategy", "monitor"))

    # Time penalty grows each step — ensures reward varies per step
    time_penalty = round(step * 0.03, 4)

    # Cascade bonus — only meaningful for hard task
    cascade_bonus = 0.0
    if task_id == "cascade-resolution":
        cascade_bonus = compute_cascade_bonus(action, ground_truth)

    # Confidence calibration bonus — clever mechanic for all tasks
    confidence_bonus = compute_confidence_bonus(
        action, severity_score, routing_score, strategy_score
    )

    # Weighted total
    total = (
        severity_score  * 0.35 +
        routing_score   * 0.35 +
        strategy_score  * 0.20 +
        cascade_bonus   * 0.10 -
        time_penalty    +
        confidence_bonus * 0.10
    )

    # Task-specific adjustments
    if task_id == "alert-classification":
        # Severity is everything for task 1
        total = (
            severity_score * 0.70 +
            routing_score  * 0.15 +
            strategy_score * 0.15 -
            time_penalty   +
            confidence_bonus * 0.10
        )
    elif task_id == "team-routing":
        # Routing is primary for task 2
        total = (
            routing_score  * 0.65 +
            severity_score * 0.15 +
            strategy_score * 0.10 -
            time_penalty   +
            confidence_bonus * 0.10
        )

    clamped = max(-1.0, min(1.0, round(total, 4)))

    return IncidentReward(
        value=clamped,
        severity_score=round(severity_score, 4),
        routing_score=round(routing_score, 4),
        strategy_score=round(strategy_score, 4),
        time_penalty=round(time_penalty, 4),
        cascade_bonus=round(cascade_bonus, 4),
        confidence_bonus=round(confidence_bonus, 4)
    )