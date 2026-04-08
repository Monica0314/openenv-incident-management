---
title: Incident Management Env
emoji: 🚀
colorFrom: red
colorTo: blue
sdk: docker
pinned: false
license: mit
short_description: AI agent for real-time incident triage & SRE
---

# Incident Management & On-Call Response — OpenEnv

DEMO VIDEO:https://www.loom.com/share/9ea374ab019f46c49ccfafe00198b341

## What is this?

3am. Payment service is down. 47 alerts firing at once. You have no idea which one is the real problem.

This is something on-call engineers at Amazon, Netflix, Swiggy deal with every single day. One wrong call — wrong team, wrong fix — costs thousands of dollars per minute. I kept thinking about how there's no good way to train an AI agent for exactly this situation.

So I figured I'd build one and see how far I could take it.

---

## Why this problem

**PagerDuty** is a $3B company. **FireHydrant** raised $50M. **OpsRamp** got acquired by HP. All of them exist because incident response is genuinely hard and genuinely expensive when done wrong.

But there's no RL training environment for this. Agents get trained on games and toy problems. Nobody built one for the thing that actually wakes engineers up at 3am.

That gap felt worth filling.

---

## How it works

The agent sees a real-feeling incident alert — not just a label, but an actual log snippet like:

```
ERROR: Connection pool exhausted after 30s at payment-service:8080 — 
67% of requests timing out
```

along with live metrics (error rate, p99 latency, requests/sec), which downstream services are affected, what got deployed recently, and which teams have engineers available right now.

From that, the agent has to decide:
- **how bad is this** — P1, P2, or P3
- **who should own it** — backend, database, devops, or security
- **what should they do** — rollback, hotfix, monitor, or escalate

Three tasks. Gets harder each time.

---

## Observation Space

| Field | Type | Description |
|-------|------|-------------|
| `step` | int | Current step in the episode |
| `service_name` | str | The failing service |
| `error_type` | str | timeout, OOM, connection_refused, etc. |
| `severity_signals` | List[str] | latency_spike, error_rate_high, revenue_impact, etc. |
| `affected_services` | List[str] | What else broke because of this |
| `recent_deployments` | List[str] | What got pushed in the last 2 hours |
| `active_teams` | Dict[str, int] | Team → available engineers right now |
| `time_elapsed_seconds` | int | How long since this started |
| `current_incident_count` | int | How many incidents are active |
| `task_id` | str | Which task is running |
| `raw_log` | str | Actual log line from the failing service |
| `metrics` | Dict[str, float] | error_rate, p99_latency_ms, requests_per_sec |

---

## Action Space

| Field | Type | Values | What it means |
|-------|------|--------|---------------|
| `severity` | str | P1, P2, P3 | How critical is this |
| `assigned_team` | str | backend, database, devops, security | Who handles it |
| `resolution_strategy` | str | rollback, hotfix, monitor, escalate | What to do |
| `confidence` | float | 0.0 – 1.0 | How sure are you |

---

## The 3 Tasks

### Task 1 — Alert Classification (Easy)

One alert. Read the log and metrics. Decide if it's P1, P2, or P3.

It gets tricky when a P2 looks like a P1 because three downstream services are also failing because of it. The grader gives partial credit for being one level off — because in real incidents, adjacent severity calls happen.

- exact match = 1.0 / one level off = 0.5 / wrong = 0.0
- expected score: ~0.65

---

### Task 2 — Team Routing (Medium)

10 incidents arrive one after another. Backend has 3 engineers, database has 2, devops has 4, security has only 1.

Route each incident to the right team without overloading anyone. I added a gaming prevention penalty too — if the agent just routes everything to backend because it's the most common, it gets penalized for that.

- routing accuracy minus overload penalty minus gaming penalty
- expected score: ~0.45

---

### Task 3 — Cascade Resolution (Hard)

Five services fail in a chain. One of them caused all of it. The agent has to figure out which one actually started it — not just which one is loudest.

Some scenarios have a deliberate misdirection — a service that looks guilty in the logs but isn't. The real root cause is upstream. If the agent falls for it and tries to fix the wrong service, the cascade gets worse and the score drops.

- root cause correctly identified: +0.5
- correct resolution strategy: +0.4
- didn't fall for misdirection: +0.1
- time penalty: -0.03 per step
- expected score: ~0.25

---

## Reward Function

```
reward = (
    severity_score  × 0.35
  + routing_score   × 0.35
  + strategy_score  × 0.20
  + cascade_bonus   × 0.10
  - step × 0.03
  + confidence_bonus × 0.10
)
clamped to [-1.0, 1.0]
```

One thing I spent time on — the confidence calibration bonus. If the agent says it's 90% confident and it's actually right 90% of the time, it gets a bonus. If it says 90% confident but is only right 40% of the time, it gets penalized. I added this because it felt wrong to reward lucky guessing — confidence should mean something.

Reward is never the same value twice — it depends on the step number, the action taken, and the ground truth. So the agent always gets a meaningful signal.

---

## Baseline Scores

| Task | Model | Score |
|------|-------|-------|
| Alert Classification | Qwen/Qwen2.5-72B-Instruct | ~0.65 |
| Team Routing | Qwen/Qwen2.5-72B-Instruct | ~0.45 |
| Cascade Resolution | Qwen/Qwen2.5-72B-Instruct | ~0.25 |

---

## Running it

```bash
docker build -t incident-env .
docker run -p 7860:7860 -e HF_TOKEN=your_token incident-env

# test reset
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "alert-classification", "seed": 42}'

# see all tasks
curl http://localhost:7860/tasks
```

```bash
# run baseline
export HF_TOKEN=your_token
export ENV_BASE_URL=http://localhost:7860
python inference.py
```

---

## Environment Variables

| Variable | Default | Notes |
|----------|---------|-------|
| `HF_TOKEN` | — | required |
| `API_BASE_URL` | https://router.huggingface.co/v1 | LLM endpoint |
| `MODEL_NAME` | Qwen/Qwen2.5-72B-Instruct | swap for any compatible model |
| `ENV_BASE_URL` | http://localhost:7860 | where the env is running |

---

## API Endpoints

| Method | Path | What it does |
|--------|------|--------------|
| GET | `/` | info + status |
| GET | `/health` | liveness check |
| POST | `/reset` | start a new episode |
| POST | `/step` | send an action, get observation + reward |
| GET | `/state` | full state + episode history |
| GET | `/tasks` | all 3 tasks with schemas |
| POST | `/grader` | score a completed episode |
| POST | `/baseline` | run the inference script |

API docs auto-generated at `/docs`.

---

## Project Structure

```
incident-management-env/
├── environment/
│   ├── __init__.py
│   ├── models.py       # pydantic models — raw_log + metrics included
│   ├── scenarios.py    # 30+ scenarios, seed-based, deterministic
│   ├── graders.py      # one grader per task, no randomness in scoring
│   ├── reward.py       # per-step reward, confidence calibration included
│   └── env.py          # main environment class
├── app.py              # fastapi server
├── inference.py        # baseline — [START][STEP][END] format
├── Dockerfile
├── requirements.txt    # all versions pinned
├── openenv.yaml
└── README.md
```
