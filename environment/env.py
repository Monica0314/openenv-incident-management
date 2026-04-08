import random
from typing import List, Dict, Any, Optional

from environment.models import (
    IncidentObservation,
    IncidentAction,
    IncidentReward,
    StepResult
)
from environment.scenarios import (
    get_scenario,
    get_all_scenarios,
    get_team_capacity,
    INCIDENT_SCENARIOS
)
from environment.reward import compute_reward
from environment.graders import grade_episode

TASK_DIFFICULTY_MAP = {
    "alert-classification": "easy",
    "team-routing": "medium",
    "cascade-resolution": "hard"
}

MAX_STEPS_MAP = {
    "alert-classification": 8,   # Fixed: was 5, now 8 for more learning signal
    "team-routing": 10,
    "cascade-resolution": 10
}


class IncidentManagementEnv:
    def __init__(self):
        self.current_task_id: str = "alert-classification"
        self.current_step: int = 0
        self.max_steps: int = 8
        self.done: bool = False
        self.current_scenario: dict = {}
        self.current_observation: Optional[IncidentObservation] = None
        self.episode_log: List[Dict[str, Any]] = []
        self.episode_actions: List[IncidentAction] = []
        self.episode_ground_truths: List[dict] = []
        self.team_loads: Dict[str, int] = {}
        self.seed: int = 0
        self._scenario_queue: List[dict] = []
        self._scenario_index: int = 0
        self.root_cause_found: bool = False

    def reset(self, task_id: str = "alert-classification", seed: int = 42) -> IncidentObservation:
        """Reset environment for a new episode."""
        self.current_task_id = task_id
        self.current_step = 0
        self.done = False
        self.episode_log = []
        self.episode_actions = []
        self.episode_ground_truths = []
        self.team_loads = {team: 0 for team in get_team_capacity()}
        self.seed = seed
        self.root_cause_found = False
        self.max_steps = MAX_STEPS_MAP.get(task_id, 10)

        difficulty = TASK_DIFFICULTY_MAP.get(task_id, "easy")

        # For team-routing: queue all scenarios sequentially
        if task_id == "team-routing":
            all_scenarios = get_all_scenarios(difficulty)
            random.seed(seed)
            self._scenario_queue = all_scenarios[:self.max_steps]
            self._scenario_index = 0
            self.current_scenario = self._scenario_queue[0]
        else:
            self.current_scenario = get_scenario(difficulty, seed)

        self.current_observation = self._build_observation()
        return self.current_observation

    def _build_observation(self) -> IncidentObservation:
        """Build observation from current scenario."""
        s = self.current_scenario
        return IncidentObservation(
            step=self.current_step,
            service_name=s["service_name"],
            error_type=s["error_type"],
            severity_signals=s["severity_signals"],
            affected_services=s["affected_services"],
            recent_deployments=s["recent_deployments"],
            active_teams=s["active_teams"],
            time_elapsed_seconds=self.current_step * 30,
            current_incident_count=len(s["affected_services"]) + 1,
            task_id=self.current_task_id,
            raw_log=s["raw_log"],
            metrics=s["metrics"]
        )

    def step(self, action: IncidentAction) -> StepResult:
        """Take one step in the environment."""
        if self.done:
            return StepResult(
                observation=self.current_observation,
                reward=IncidentReward(
                    value=0.0, severity_score=0.0, routing_score=0.0,
                    strategy_score=0.0, time_penalty=0.0,
                    cascade_bonus=0.0, confidence_bonus=0.0
                ),
                done=True,
                info={"error": "Episode already done. Call /reset to start new episode."}
            )

        self.current_step += 1
        ground_truth = self.current_scenario["ground_truth"]

        # Track team loads for routing task
        if action.assigned_team in self.team_loads:
            self.team_loads[action.assigned_team] += 1

        # Compute reward
        reward = compute_reward(
            action=action,
            ground_truth=ground_truth,
            step=self.current_step,
            task_id=self.current_task_id
        )

        # Track cascade root cause for hard task
        info: Dict[str, Any] = {}
        if self.current_task_id == "cascade-resolution":
            root_cause = ground_truth.get("root_cause_service", "")
            if not self.root_cause_found and action.assigned_team == ground_truth.get("team"):
                self.root_cause_found = True
                info["root_cause_identified"] = True

            is_misdirection = ground_truth.get("misdirection", False)
            misdirection_svc = ground_truth.get("misdirection_service", "")
            if is_misdirection and action.assigned_team != ground_truth.get("team"):
                info["warning"] = f"Misdirection! {misdirection_svc} looks like root cause but is not."

        # Log this step
        step_log = {
            "step": self.current_step,
            "action": action.model_dump(),
            "reward": reward.model_dump(),
            "target_service": self.current_scenario["service_name"],
            "resolution_strategy": action.resolution_strategy
        }
        self.episode_log.append(step_log)
        self.episode_actions.append(action)
        self.episode_ground_truths.append(ground_truth)

        # Check if episode is done
        done = self._check_done(action, ground_truth)
        self.done = done

        # Advance scenario for team-routing task
        if not done and self.current_task_id == "team-routing":
            self._scenario_index += 1
            if self._scenario_index < len(self._scenario_queue):
                self.current_scenario = self._scenario_queue[self._scenario_index]

        self.current_observation = self._build_observation()

        info.update({
            "step": self.current_step,
            "max_steps": self.max_steps,
            "team_loads": self.team_loads,
            "episode_length": len(self.episode_log)
        })

        return StepResult(
            observation=self.current_observation,
            reward=reward,
            done=done,
            info=info
        )

    def _check_done(self, action: IncidentAction, ground_truth: dict) -> bool:
        """Check if episode should end."""
        if self.current_step >= self.max_steps:
            return True

        # Task 1: done when severity correctly classified
        if self.current_task_id == "alert-classification":
            if action.severity == ground_truth["severity"]:
                return True

        # Task 3: done when correct strategy applied after root cause found
        if self.current_task_id == "cascade-resolution":
            if (self.root_cause_found and
                    action.resolution_strategy == ground_truth["strategy"]):
                return True

        return False

    def state(self) -> Dict[str, Any]:
        """Return full environment state including episode history."""
        return {
            "task_id": self.current_task_id,
            "current_step": self.current_step,
            "max_steps": self.max_steps,
            "done": self.done,
            "seed": self.seed,
            "team_loads": self.team_loads,
            "root_cause_found": self.root_cause_found,
            "current_observation": (
                self.current_observation.model_dump()
                if self.current_observation else None
            ),
            "episode_history": self.episode_log,  # Full history for judges
            "episode_length": len(self.episode_log),
            "current_scenario_difficulty": TASK_DIFFICULTY_MAP.get(self.current_task_id, "easy")
        }

    def grade_episode(self, task_id: str, episode_log: List[Dict]) -> float:
        """Grade a completed episode."""
        ground_truths = [
            s["ground_truth"]
            for s in INCIDENT_SCENARIOS[TASK_DIFFICULTY_MAP.get(task_id, "easy")]
        ]
        return grade_episode(task_id, episode_log, ground_truths)