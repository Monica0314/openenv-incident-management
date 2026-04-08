"""
Incident Management & On-Call Response — OpenEnv FastAPI Server
All required endpoints: /reset /step /state /tasks /grader /baseline
"""
import subprocess
import json
import uvicorn
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from environment.env import IncidentManagementEnv
from environment.models import IncidentAction, IncidentObservation, IncidentReward

# ─────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────

app = FastAPI(
    title="OpenEnv: RL Incident Management",
    description=(
        "RL environment for AI-driven IT incident management and on-call response. "
        "Agent classifies alerts, routes to teams, and resolves cascading failures."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single shared environment instance
env = IncidentManagementEnv()


# ─────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────

class ResetRequest(BaseModel):
    task_id: Optional[str] = "alert-classification"
    seed: Optional[int] = 42


class StepRequest(BaseModel):
    action: Dict[str, Any]
    task_id: Optional[str] = None


class GraderRequest(BaseModel):
    task_id: str
    episode_log: list


class StepResponse(BaseModel):
    observation: Dict[str, Any]
    reward: Dict[str, Any]
    done: bool
    info: Dict[str, Any]


# ─────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────

@app.get("/", tags=["health"])
async def root():
    return {
        "name": "incident-management-env",
        "version": "1.0.0",
        "status": "running",
        "docs":"https://monica1-sj-incident-management-env.hf.space/docs",
        "tasks": "/tasks"
    }


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────
# POST /reset
# ─────────────────────────────────────────────

@app.post("/reset", tags=["environment"])
async def reset(body: ResetRequest = ResetRequest()):
    """
    Reset the environment and return the initial observation.
    task_id: 'alert-classification' | 'team-routing' | 'cascade-resolution'
    seed: integer for reproducibility (default 42)
    """
    valid_tasks = ["alert-classification", "team-routing", "cascade-resolution"]
    if body.task_id not in valid_tasks:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task_id '{body.task_id}'. Must be one of: {valid_tasks}"
        )

    try:
        obs = env.reset(task_id=body.task_id, seed=body.seed)
        return obs.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


# ─────────────────────────────────────────────
# POST /step
# ─────────────────────────────────────────────

@app.post("/step", tags=["environment"])
async def step(body: StepRequest):
    """
    Take one step with the given action.
    Returns observation, reward breakdown, done flag, and info.
    """
    if not body.action:
        raise HTTPException(status_code=400, detail="Action must not be empty.")

    # Validate action fields
    valid_severities = ["P1", "P2", "P3"]
    valid_teams = ["backend", "database", "devops", "security"]
    valid_strategies = ["rollback", "hotfix", "monitor", "escalate"]

    severity = body.action.get("severity", "")
    team = body.action.get("assigned_team", "")
    strategy = body.action.get("resolution_strategy", "")
    confidence = body.action.get("confidence", 0.5)

    if severity not in valid_severities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity '{severity}'. Must be one of: {valid_severities}"
        )
    if team not in valid_teams:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid assigned_team '{team}'. Must be one of: {valid_teams}"
        )
    if strategy not in valid_strategies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid resolution_strategy '{strategy}'. Must be one of: {valid_strategies}"
        )
    if not (0.0 <= float(confidence) <= 1.0):
        raise HTTPException(
            status_code=400,
            detail="confidence must be between 0.0 and 1.0"
        )

    try:
        action = IncidentAction(
            severity=severity,
            assigned_team=team,
            resolution_strategy=strategy,
            confidence=float(confidence)
        )
        result = env.step(action)
        return {
            "observation": result.observation.model_dump(),
            "reward": result.reward.model_dump(),
            "done": result.done,
            "info": result.info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Step failed: {str(e)}")


# ─────────────────────────────────────────────
# GET /state
# ─────────────────────────────────────────────

@app.get("/state", tags=["environment"])
async def state():
    """
    Return full environment state including complete episode history.
    Useful for debugging and for the grader to inspect decisions.
    """
    try:
        return env.state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"State fetch failed: {str(e)}")


# ─────────────────────────────────────────────
# GET /tasks
# ─────────────────────────────────────────────

@app.get("/tasks", tags=["metadata"])
async def tasks():
    """
    Return all 3 tasks with their action schema, difficulty, and grader details.
    """
    action_schema = IncidentAction.model_json_schema()

    return {
        "tasks": [
            {
                "id": "alert-classification",
                "difficulty": "easy",
                "description": "Classify incoming alert severity as P1, P2, or P3",
                "objective": "Correctly identify severity with high confidence calibration",
                "max_steps": 8,
                "expected_baseline_score": 0.65,
                "grader": "grade_classification — exact match 1.0, adjacent 0.5, wrong 0.0",
                "action_schema": action_schema,
                "reward_range": [-1.0, 1.0]
            },
            {
                "id": "team-routing",
                "difficulty": "medium",
                "description": "Route 10 incidents to correct teams under capacity constraints",
                "objective": "Maximize routing accuracy without overloading any team",
                "max_steps": 10,
                "expected_baseline_score": 0.45,
                "grader": "grade_routing_episode — accuracy minus overload penalty minus gaming penalty",
                "team_capacities": {
                    "backend": 3,
                    "database": 2,
                    "devops": 4,
                    "security": 1
                },
                "action_schema": action_schema,
                "reward_range": [-1.0, 1.0]
            },
            {
                "id": "cascade-resolution",
                "difficulty": "hard",
                "description": "Identify root cause in cascading multi-service failure and resolve correctly",
                "objective": "Find root cause first, then apply correct resolution strategy",
                "max_steps": 10,
                "expected_baseline_score": 0.25,
                "grader": "grade_cascade_episode — root cause 0.5, strategy 0.4, misdirection handling 0.1",
                "warning": "Some scenarios have misdirection — a service that looks like root cause but is not",
                "action_schema": action_schema,
                "reward_range": [-1.0, 1.0]
            }
        ],
        "observation_fields": [
            "step", "service_name", "error_type", "severity_signals",
            "affected_services", "recent_deployments", "active_teams",
            "time_elapsed_seconds", "current_incident_count", "task_id",
            "raw_log", "metrics"
        ],
        "action_fields": ["severity", "assigned_team", "resolution_strategy", "confidence"]
    }


# ─────────────────────────────────────────────
# POST /grader
# ─────────────────────────────────────────────

@app.post("/grader", tags=["evaluation"])
async def grader(body: GraderRequest):
    """
    Grade a completed episode log.
    Pass the full episode_log and task_id to get a score in [0.0, 1.0].
    """
    valid_tasks = ["alert-classification", "team-routing", "cascade-resolution"]
    if body.task_id not in valid_tasks:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task_id. Must be one of: {valid_tasks}"
        )

    try:
        score = env.grade_episode(body.task_id, body.episode_log)
        return {
            "task_id": body.task_id,
            "score": score,
            "score_range": [0.0, 1.0],
            "episode_length": len(body.episode_log)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Grading failed: {str(e)}")


# ─────────────────────────────────────────────
# POST /baseline
# ─────────────────────────────────────────────

@app.post("/baseline", tags=["evaluation"])
async def baseline():
    """
    Trigger the baseline inference script and return scores for all 3 tasks.
    Runs inference.py which uses Qwen2.5-72B via HuggingFace router.
    """
    try:
        result = subprocess.run(
            ["python", "inference.py"],
            capture_output=True,
            text=True,
            timeout=1200  # 20 min max
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "returncode": result.returncode,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Baseline inference timed out after 20 minutes.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Baseline failed: {str(e)}")

# ─────────────────────────────────────────────
# FINAL ENTRY POINT
# ─────────────────────────────────────────────

def main():
    """
    Entry point for the OpenEnv grader.
    Uses 'server.app:app' because the file is in the server folder.
    """
    uvicorn.run("server.app:app", host="0.0.0.0", port=7860)

if __name__ == "__main__":
    main()
