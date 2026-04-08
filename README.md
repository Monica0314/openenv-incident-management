# Incident Management & On-Call Response Environment

## Overview

Every tech company runs thousands of microservices. When something breaks at 3am, an on-call engineer receives dozens of simultaneous alerts and must instantly classify severity, identify root cause vs side effects, route to the correct team, and decide whether to rollback or hotfix — all under extreme time pressure. Wrong decisions cost thousands of dollars per minute in downtime.

This OpenEnv environment simulates exactly that problem. An AI agent acts as an intelligent on-call incident responder, receiving structured alert observations with real log snippets and live metrics, and must take correct actions across 3 tasks of increasing difficulty.

---

## Motivation

Companies like PagerDuty, FireHydrant, and OpsRamp are billion-dollar businesses built around incident management. Netflix, Amazon, Google, and Swiggy all run SRE teams whose primary job is what this agent must learn. No clean RL training environment for this domain existed in OpenEnv — this project fills that gap.

Key pain points this environment captures:
- Alert storms with multiple simultaneous failures
- Cascading failures where symptoms mask the real root cause
- Resource-constrained team routing (security team has 1 engineer!)
- Misdirection scenarios where the obvious culprit is NOT the root cause
- Time pressure — every step costs reward

---

## Observation Space

| Field | Type | Description |
|-------|------|-------------|
| `step` | int | Current step number in the episode |
| `service_name` | str | Name of the primary failing service |
| `error_type` | str | Error category: timeout, OOM, connection_refused, etc. |
| `severity_signals` | List[str] | Observable signals: latency_spike, error_rate_high, etc. |
| `affected_services` | List[str] | Downstream services impacted by this failure |
| `recent_deployments` | List[str] | Deployments pushed in the last 2 hours |
| `active_teams` | Dict[str, int] | Team name → number of available engineers |
| `time_elapsed_seconds` | int | Seconds since incident started |
| `current_incident_count` | int | Total active incidents right now |
| `task_id` | str | Which task is being evaluated |
| `raw_log` | str | Realistic log snippet from the failing service |
| `metrics` | Dict[str, float] | Live metrics: error_rate, p99_latency_ms, requests_per_sec |

---

## Action Space

| Field | Type | Allowed Values | Description |
|-------|------|---------------|-------------|
| `severity` | str | P1, P2, P3 | Incident severity classification |
| `assigned_team` | str | backend, database, devops, security | Team to handle the incident |
| `resolution_strategy` | str | rollback, hotfix, monitor, escalate | How to resolve the incident |
| `confidence` | float | 0.0 – 1.0 | Agent confidence in this action |

---

## Tasks

### Task 1: Alert Classification (Easy)

**Objective:** Given a single alert with raw logs and metrics, classify its severity as P1, P2, or P3.

**Grader logic:**
- Exact severity match: 1.0
- Adjacent severity (P1↔P2 or P2↔P3): 0.5
- Wrong severity: 0.0

**Episode length:** 8 steps

**Expected baseline score:** ~0.65

---

### Task 2: Team Routing (Medium)

**Objective:** Route 10 incoming incidents to the correct teams while respecting capacity limits.

**Team capacities:** backend: 3, database: 2, devops: 4, security: 1

**Grader logic:**
- Routing accuracy score
- Overload penalty: -0.1 per excess engineer over capacity
- Gaming prevention penalty: -0.2 if >60% routed to backend

**Episode length:** 10 steps

**Expected baseline score:** ~0.45

---

### Task 3: Cascade Resolution (Hard)

**Objective:** In a multi-service cascade failure, identify the root cause service and apply the correct resolution strategy.

**Grader logic:**
- Root cause identified: +0.5
- Correct resolution strategy: +0.4
- Misdirection avoided: +0.1 bonus
- Fell for misdirection: -0.2 penalty
- Time penalty: -0.03 per step

**Special mechanic:** Some scenarios have misdirection — a service that looks like the root cause in logs but is not. The agent must read raw_log carefully.

**Episode length:** 10 steps

**Expected baseline score:** ~0.25

---

## Reward Function

```
total = (
    severity_score  × 0.35  +
    routing_score   × 0.35  +
    strategy_score  × 0.20  +
    cascade_bonus   × 0.10  -
    time_penalty          (step × 0.03)  +
    confidence_bonus × 0.10
)
total = clamp(total, -1.0, 1.0)
```

**Confidence calibration bonus:** Agent earns up to +0.2 bonus when its stated confidence matches its actual accuracy over the episode. This rewards well-calibrated uncertainty — a rare and valuable property in RL agents.

**Key properties:**
- Never returns same value twice (depends on step + action + ground truth)
- Partial progress signal at every step
- Penalizes bad behavior (wrong routing, cascade worsening)
- Rewards calibrated confidence

---

## Baseline Scores

| Task | Model | Score |
|------|-------|-------|
| Alert Classification | Qwen/Qwen2.5-72B-Instruct | ~0.65 |
| Team Routing | Qwen/Qwen2.5-72B-Instruct | ~0.45 |
| Cascade Resolution | Qwen/Qwen2.5-72B-Instruct | ~0.25 |

---

## Setup & Usage

### Docker (recommended)

```bash
# Build image
docker build -t incident-env .

# Run locally
docker run -p 7860:7860 \
  -e HF_TOKEN=your_token_here \
  incident-env

# Test endpoints
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "alert-classification", "seed": 42}'

curl http://localhost:7860/tasks

curl http://localhost:7860/health
```

### Run inference baseline

```bash
export HF_TOKEN=your_token_here
export ENV_BASE_URL=http://localhost:7860
python inference.py
```

### Validate OpenEnv compliance

```bash
openenv validate
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HF_TOKEN` | HuggingFace API key for LLM inference | required |
| `API_BASE_URL` | LLM API endpoint | https://router.huggingface.co/v1 |
| `MODEL_NAME` | Model identifier | Qwen/Qwen2.5-72B-Instruct |
| `ENV_BASE_URL` | Environment server URL | http://localhost:7860 |

---

## Project Structure

```
incident-management-env/
├── environment/
│   ├── __init__.py
│   ├── models.py       # Pydantic models with raw_log + metrics
│   ├── scenarios.py    # 30+ seed-based deterministic scenarios
│   ├── graders.py      # Deterministic graders for all 3 tasks
│   ├── reward.py       # Per-step reward with confidence calibration
│   └── env.py          # Main OpenEnv environment class
├── app.py              # FastAPI server — all 6 endpoints
├── inference.py        # Baseline inference script
├── Dockerfile          # Container definition
├── requirements.txt    # Pinned dependencies
├── openenv.yaml        # OpenEnv metadata
└── README.md           # This file
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check + info |
| GET | `/health` | Liveness probe |
| POST | `/reset` | Reset environment, returns initial observation |
| POST | `/step` | Take action, returns observation + reward + done |
| GET | `/state` | Full environment state + episode history |
| GET | `/tasks` | All 3 tasks with action schemas |
| POST | `/grader` | Grade a completed episode |
| POST | `/baseline` | Run baseline inference script |

Interactive API docs available at `/docs` after deployment.