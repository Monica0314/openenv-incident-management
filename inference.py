"""
Incident Management Environment — Baseline Inference Script
Follows mandatory OpenEnv stdout format: [START] [STEP] [END]
Uses OpenAI client pointing to HuggingFace router.
"""
import os
import json
import textwrap
import requests
from typing import List, Optional
from openai import OpenAI

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

API_KEY        = os.getenv("API_KEY", "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") 
API_BASE_URL   = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME     = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
ENV_BASE_URL   = os.getenv("ENV_BASE_URL", "http://localhost:7860")

MAX_STEPS               = 8
TEMPERATURE             = 0.2
MAX_TOKENS              = 400
SUCCESS_SCORE_THRESHOLD = 0.1 

TASKS = [
    "alert-classification",
    "team-routing",
    "cascade-resolution"
]

# ─────────────────────────────────────────────
# System prompt — expert on-call engineer
# ─────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert on-call incident response engineer with 10+ years of SRE experience.
    You will receive structured incident alert data including raw logs and metrics.
    You must respond ONLY with a valid JSON object — no explanation, no markdown, no preamble.

    Your JSON must have EXACTLY these fields:
    {
        "severity": "P1" | "P2" | "P3",
        "assigned_team": "backend" | "database" | "devops" | "security",
        "resolution_strategy": "rollback" | "hotfix" | "monitor" | "escalate",
        "confidence": <float between 0.0 and 1.0>
    }

    === SEVERITY GUIDE ===
    P1: Critical — service down, revenue impact, data loss risk, 100% error rate
    P2: High — degraded performance, partial outage, high latency, <80% error rate
    P3: Medium — minor issue, internal only, no immediate user impact

    === TEAM GUIDE ===
    backend:  application errors, logic bugs, API failures, memory leaks, cache issues
    database: query timeouts, connection pool exhaustion, replication lag, schema issues
    devops:   infrastructure, deployment failures, container/k8s issues, network, CDN, config
    security: auth failures, certificate issues, brute force attacks, unusual access patterns

    === STRATEGY GUIDE ===
    rollback: issue started after a recent deployment — revert the deploy
    hotfix:   code or config bug not related to a recent deployment — push a fix
    monitor:  unclear root cause — gather more data before acting
    escalate: requires senior leadership, external vendor, or security team involvement

    === CONFIDENCE GUIDE ===
    Set confidence to match how certain you are:
    0.9-1.0: very clear signals, obvious root cause
    0.6-0.8: good signals but some ambiguity
    0.3-0.5: unclear, monitoring situation
    0.1-0.3: very ambiguous, escalating to be safe

    === CRITICAL RULES ===
    - If recent_deployments is non-empty AND errors started after deploy → use "rollback"
    - If error_type is "ssl_certificate_expired" or "brute_force" → assign "security"
    - If error_type is "replication_lag" or "connection_pool_exhausted" → assign "database"
    - If error_type contains "node", "container", "deploy", "config" → assign "devops"
    - P1 = revenue impact OR 100% error rate OR complete service down
    - In cascade failures: look at raw_log carefully — the FIRST service mentioned is usually root cause
    - Watch for misdirection: if log says "X looks like root cause but..." → X is NOT root cause

    Respond ONLY with the JSON object. Nothing else.
""").strip()


# ─────────────────────────────────────────────
# Logging — mandatory OpenEnv format
# ─────────────────────────────────────────────

def log_start(task: str, env: str, model: str):
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: dict, reward: float, done: bool, error: Optional[str]):
    action_str = json.dumps(action, separators=(',', ':'))
    error_val  = error if error else "null"
    done_val   = str(done).lower()
    print(
        f"[STEP] step={step} action={action_str} "
        f"reward={reward:.2f} done={done_val} error={error_val}",
        flush=True
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]):
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.3f} rewards={rewards_str}",
        flush=True
    )


# ─────────────────────────────────────────────
# Agent — get action from LLM
# ─────────────────────────────────────────────

def get_agent_action(client: OpenAI, observation: dict) -> dict:
    """Call LLM to get an action given the current observation."""

    # Build a rich user prompt with all observation fields
    user_prompt = textwrap.dedent(f"""
        === INCIDENT ALERT ===
        Task: {observation.get('task_id', 'unknown')}
        Step: {observation.get('step', 0)} | Time elapsed: {observation.get('time_elapsed_seconds', 0)}s

        Service:        {observation.get('service_name', 'unknown')}
        Error type:     {observation.get('error_type', 'unknown')}
        Severity signals: {', '.join(observation.get('severity_signals', []))}
        Affected services: {', '.join(observation.get('affected_services', [])) or 'none'}
        Recent deployments: {', '.join(observation.get('recent_deployments', [])) or 'none in last 2hrs'}

        Active teams (name: available engineers):
        {json.dumps(observation.get('active_teams', {}), indent=2)}

        Raw log:
        {observation.get('raw_log', 'No log available')}

        Live metrics:
        {json.dumps(observation.get('metrics', {}), indent=2)}

        Active incidents: {observation.get('current_incident_count', 1)}

        Respond with ONLY the JSON action object.
    """).strip()

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt}
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        text = (completion.choices[0].message.content or "").strip()

        # Strip markdown fences if model adds them
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(
                line for line in lines
                if not line.startswith("```")
            ).strip()

        action = json.loads(text)

        # Validate and sanitize fields
        valid_severities = ["P1", "P2", "P3"]
        valid_teams      = ["backend", "database", "devops", "security"]
        valid_strategies = ["rollback", "hotfix", "monitor", "escalate"]

        if action.get("severity") not in valid_severities:
            action["severity"] = "P2"
        if action.get("assigned_team") not in valid_teams:
            action["assigned_team"] = "backend"
        if action.get("resolution_strategy") not in valid_strategies:
            action["resolution_strategy"] = "monitor"

        confidence = float(action.get("confidence", 0.5))
        action["confidence"] = max(0.0, min(1.0, confidence))

        return action

    except Exception as e:
        print(f"[DEBUG] Model error: {e}", flush=True)
        # Safe fallback action
        return {
            "severity": "P2",
            "assigned_team": "backend",
            "resolution_strategy": "monitor",
            "confidence": 0.5
        }


# ─────────────────────────────────────────────
# Run one task episode
# ─────────────────────────────────────────────

def run_task(client: OpenAI, task_id: str) -> float:
    """Run one full episode for a task. Returns normalized score in [0.0, 1.0]."""

    rewards:     List[float] = []
    steps_taken: int         = 0
    score:       float       = 0.0
    success:     bool        = False

    log_start(task=task_id, env="incident-management-env", model=MODEL_NAME)

    try:
        # Reset environment
        reset_resp = requests.post(
            f"{ENV_BASE_URL}/reset",
            json={"task_id": task_id, "seed": 42},
            timeout=120
        )
        reset_resp.raise_for_status()
        observation = reset_resp.json()
        done = False

        for step in range(1, MAX_STEPS + 1):
            if done:
                break

            # Get action from LLM
            action_dict = get_agent_action(client, observation)

            # Send action to environment
            step_resp = requests.post(
                f"{ENV_BASE_URL}/step",
                json={"action": action_dict},
                timeout=30
            )
            step_resp.raise_for_status()
            result = step_resp.json()

            reward      = result.get("reward", {}).get("value", 0.0)
            done        = result.get("done", False)
            error       = result.get("info", {}).get("error", None)
            observation = result.get("observation", observation)

            rewards.append(float(reward))
            steps_taken = step

            log_step(
                step=step,
                action=action_dict,
                reward=float(reward),
                done=done,
                error=error
            )

        # Compute final score
        if rewards:
            avg_reward = sum(rewards) / len(rewards)
            length_factor = len(rewards) / MAX_STEPS

    # Boost short episodes, preserve long ones
        score = max(
            0.0,
            min(1.0, avg_reward * (0.7 + 0.3 * length_factor))
        )

        success = score >= SUCCESS_SCORE_THRESHOLD

    except requests.exceptions.ConnectionError:
        print(
            f"[DEBUG] Cannot connect to environment at {ENV_BASE_URL}. "
            "Is the server running?",
            flush=True
        )
    except Exception as e:
        print(f"[DEBUG] Task error in {task_id}: {e}", flush=True)
    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    print("[DEBUG] Starting baseline inference for all 3 tasks...", flush=True)
    print(f"[DEBUG] Model: {MODEL_NAME}", flush=True)
    print(f"[DEBUG] Environment: {ENV_BASE_URL}", flush=True)

    all_scores = {}
    for task_id in TASKS:
        print(f"\n[DEBUG] Running task: {task_id}", flush=True)
        score = run_task(client, task_id)
        all_scores[task_id] = round(score, 3)
        print(f"[DEBUG] Task {task_id} final score: {score:.3f}", flush=True)

    print(f"\n[SUMMARY] All task scores:", flush=True)
    print(json.dumps(all_scores, indent=2), flush=True)

    avg = sum(all_scores.values()) / len(all_scores)
    print(f"[SUMMARY] Average score: {avg:.3f}", flush=True)


if __name__ == "__main__":
    main()