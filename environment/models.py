from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class IncidentObservation(BaseModel):
    step: int
    service_name: str
    error_type: str                        # e.g. "timeout", "OOM", "connection_refused"
    severity_signals: List[str]            # e.g. ["latency_spike", "error_rate_high"]
    affected_services: List[str]           # downstream services affected
    recent_deployments: List[str]          # deployments in last 2 hours
    active_teams: Dict[str, int]           # team_name -> available engineers
    time_elapsed_seconds: int
    current_incident_count: int
    task_id: str
    raw_log: str                           # realistic log snippet e.g. "ERROR: Connection pool exhausted..."
    metrics: Dict[str, float]             # e.g. {"error_rate": 0.94, "p99_latency_ms": 8400}


class IncidentAction(BaseModel):
    severity: str                          # "P1", "P2", "P3"
    assigned_team: str                     # "backend", "database", "devops", "security"
    resolution_strategy: str              # "rollback", "hotfix", "monitor", "escalate"
    confidence: float = Field(ge=0.0, le=1.0)   # 0.0 to 1.0


class IncidentReward(BaseModel):
    value: float                           # total reward this step, clamped [-1.0, 1.0]
    severity_score: float                  # partial: was severity correct?
    routing_score: float                   # partial: was team routing correct?
    strategy_score: float                  # partial: was resolution strategy correct?
    time_penalty: float                    # penalty for taking too long
    cascade_bonus: float                   # bonus for preventing cascade
    confidence_bonus: float               # bonus when confidence matches actual accuracy


class StepResult(BaseModel):
    observation: IncidentObservation
    reward: IncidentReward
    done: bool
    info: Dict