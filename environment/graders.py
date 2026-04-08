from typing import List, Dict, Any
from environment.models import IncidentAction

SEVERITY_RANK = {"P1": 1, "P2": 2, "P3": 3}

TEAM_CAPACITY = {
    "backend": 3,
    "database": 2,
    "devops": 4,
    "security": 1
}


# ─────────────────────────────────────────────
# TASK 1: Alert Classification Grader (Easy)
# ─────────────────────────────────────────────

def grade_classification(action: IncidentAction, ground_truth: dict) -> float:
    """
    Grade severity classification.
    Exact match: 1.0
    Adjacent severity: 0.5
    Wrong: 0.0
    """
    correct_severity = ground_truth["severity"]

    if action.severity == correct_severity:
        return 1.0
    elif abs(SEVERITY_RANK[action.severity] - SEVERITY_RANK[correct_severity]) == 1:
        return 0.5
    else:
        return 0.0


def grade_team_routing_single(action: IncidentAction, ground_truth: dict) -> float:
    """Grade a single routing action."""
    if action.assigned_team == ground_truth["team"]:
        return 1.0
    return 0.0


def grade_strategy_single(action: IncidentAction, ground_truth: dict) -> float:
    """Grade a single strategy action."""
    if action.resolution_strategy == ground_truth["strategy"]:
        return 1.0
    return 0.0


# ─────────────────────────────────────────────
# TASK 2: Team Routing Grader (Medium)
# ─────────────────────────────────────────────

def grade_routing_episode(
    episode_actions: List[IncidentAction],
    episode_ground_truths: List[dict]
) -> float:
    """
    Grade full routing episode.
    - Routing accuracy score
    - Strict overload penalty (any team over capacity = penalty)
    - Backend gaming prevention: must route correctly across ALL teams
    """
    if not episode_actions:
        return 0.0

    team_loads: Dict[str, int] = {team: 0 for team in TEAM_CAPACITY}

    correct_routings = 0
    for action, gt in zip(episode_actions, episode_ground_truths):
        if action.assigned_team == gt["team"]:
            correct_routings += 1
        # Track load regardless of correctness
        if action.assigned_team in team_loads:
            team_loads[action.assigned_team] += 1

    routing_accuracy = correct_routings / len(episode_actions)

    # Strict overload penalty — any overloaded team costs 0.1 per excess engineer
    overload_penalty = 0.0
    for team, load in team_loads.items():
        capacity = TEAM_CAPACITY[team]
        if load > capacity:
            overload_penalty += (load - capacity) * 0.1

    # Backend gaming prevention — if >60% routed to backend, apply extra penalty
    backend_ratio = team_loads.get("backend", 0) / len(episode_actions)
    gaming_penalty = 0.2 if backend_ratio > 0.6 else 0.0

    final_score = routing_accuracy - overload_penalty - gaming_penalty
    return max(0.0, min(1.0, final_score))


# ─────────────────────────────────────────────
# TASK 3: Cascade Resolution Grader (Hard)
# ─────────────────────────────────────────────

def grade_cascade_episode(
    episode_log: List[Dict[str, Any]],
    ground_truth: dict
) -> float:
    """
    Grade cascade resolution episode.
    - Root cause identification: +0.5
    - Correct strategy: +0.4
    - Misdirection handling: extra bonus for NOT falling for red herring
    - Time penalty: -0.03 per step
    - Wrong strategy on misdirection scenario: -0.2 extra
    """
    if not episode_log:
        return 0.0

    root_cause = ground_truth["root_cause_service"]
    correct_strategy = ground_truth["strategy"]
    is_misdirection = ground_truth.get("misdirection", False)
    misdirection_service = ground_truth.get("misdirection_service", None)

    # Check if root cause was correctly identified
    root_identified = any(
        step.get("target_service") == root_cause or
        step.get("assigned_team") == ground_truth["team"]
        for step in episode_log
    )

    # Check final strategy
    last_step = episode_log[-1]
    strategy_correct = last_step.get("resolution_strategy") == correct_strategy

    # Check if agent fell for misdirection
    fell_for_misdirection = False
    if is_misdirection and misdirection_service:
        fell_for_misdirection = any(
            step.get("target_service") == misdirection_service
            for step in episode_log[:2]  # Only penalize if misled in first 2 steps
        )

    steps_taken = len(episode_log)

    base_score = 0.0
    if root_identified:
        base_score += 0.5
    if strategy_correct:
        base_score += 0.4

    # Bonus for not falling for misdirection
    if is_misdirection and not fell_for_misdirection:
        base_score += 0.1

    # Penalty for falling for misdirection
    if fell_for_misdirection:
        base_score -= 0.2

    # Time penalty
    time_penalty = min(0.3, steps_taken * 0.03)

    final_score = base_score - time_penalty
    return max(0.0, min(1.0, final_score))


# ─────────────────────────────────────────────
# CONFIDENCE CALIBRATION GRADER
# ─────────────────────────────────────────────

def grade_confidence_calibration(
    episode_actions: List[IncidentAction],
    episode_correctness: List[float]
) -> float:
    """
    Reward agent when confidence matches actual accuracy.
    Perfect calibration: confidence=0.9 when 90% correct = bonus
    Overconfident on wrong answers = penalty
    """
    if not episode_actions:
        return 0.0

    actual_accuracy = sum(episode_correctness) / len(episode_correctness)
    avg_confidence = sum(a.confidence for a in episode_actions) / len(episode_actions)

    # Calibration error — lower is better
    calibration_error = abs(avg_confidence - actual_accuracy)

    # Bonus: 0.2 max when perfectly calibrated, 0.0 when off by 0.5+
    calibration_bonus = max(0.0, 0.2 - (calibration_error * 0.4))
    return round(calibration_bonus, 4)


# ─────────────────────────────────────────────
# EPISODE GRADER — unified entry point
# ─────────────────────────────────────────────

def grade_episode(
    task_id: str,
    episode_log: List[Dict[str, Any]],
    ground_truths: List[dict]
) -> float:
    """
    Unified episode grader for all 3 tasks.
    Returns score in [0.0, 1.0].
    """
    if not episode_log or not ground_truths:
        return 0.0

    if task_id == "alert-classification":
        scores = []
        for step_log, gt in zip(episode_log, ground_truths):
            action = IncidentAction(**step_log["action"])
            scores.append(grade_classification(action, gt))
        return round(sum(scores) / len(scores), 4)

    elif task_id == "team-routing":
        actions = [IncidentAction(**s["action"]) for s in episode_log]
        return round(grade_routing_episode(actions, ground_truths), 4)

    elif task_id == "cascade-resolution":
        gt = ground_truths[0] if ground_truths else {}
        return round(grade_cascade_episode(episode_log, gt), 4)

    return 0.0