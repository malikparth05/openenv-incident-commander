"""
Inference Script — Incident Commander Environment
===================================================
MANDATORY:
- Uses OpenAI Client for all LLM calls
- Reads API_BASE_URL, MODEL_NAME, HF_TOKEN from environment variables
- Emits [START], [STEP], [END] stdout format exactly as specified
- Runs all 3 tasks and produces scores in [0, 1]

STDOUT FORMAT:
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import asyncio
import json
import os
import textwrap
from typing import Any, Dict, List, Optional

from openai import OpenAI

from incident_commander_env import IncidentCommanderEnv

# ─── Configuration ────────────────────────────────────────────────────────────

IMAGE_NAME = os.getenv("IMAGE_NAME")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"

BENCHMARK = "incident_commander_env"
MAX_STEPS_PER_TASK = {"single_service_outage": 10, "multi_service_degradation": 20, "cascading_infrastructure_failure": 30}
TEMPERATURE = 0.3
MAX_TOKENS = 500
SUCCESS_SCORE_THRESHOLD = 0.3

TASKS = ["single_service_outage", "multi_service_degradation", "cascading_infrastructure_failure"]


# ─── Logging helpers (EXACT format required) ──────────────────────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    # Sanitize action to be single-line
    action_clean = action.replace("\n", " ").replace("\r", "")[:200]
    print(
        f"[STEP] step={step} action={action_clean} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)


# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""
You are an expert IT Incident Commander managing a real-time infrastructure outage.
You must triage alerts, assign them to the right teams, and escalate appropriately.

Available tools (call exactly ONE per turn):
1. acknowledge_alert(alert_id) — Acknowledge you've seen an alert
2. set_priority(alert_id, priority) — Set priority: P1 (critical), P2 (high), P3 (medium), P4 (low)
3. assign_team(alert_id, team) — Route to team: platform, database, network, application, infrastructure, security
4. escalate(level) — Escalate: on_call_lead, vp_eng, cto
5. send_update(message, channel) — Send status update to: incident_channel, stakeholder_email, status_page
6. search_runbooks(query) — Search engineering wikis/runbooks to figure out how to handle specific alerts, which team owns what, etc.
7. mark_resolved(alert_id) — Mark alert as resolved
8. investigate(alert_id) — Get more details about an alert
9. correlate_alerts(alert_ids) — Group related alerts. alert_ids is comma-separated: "alert-001,alert-002"
10. get_status() — Get current incident status summary

Strategy:
- First acknowledge all alerts to show you've seen them
- Investigate critical alerts to understand root cause
- Set correct priorities (P1 for critical, P4 for noise/informational)
- Route alerts to the RIGHT team based on the service affected
- Correlate related alerts into incident groups
- Escalate to the appropriate level (don't over-escalate noise)
- Send status updates to stakeholders

Respond with ONLY a JSON object specifying the tool call:
{"tool": "<tool_name>", "args": {"param1": "value1", ...}}

Examples:
{"tool": "search_runbooks", "args": {"query": "api gateway 503 errors"}}
{"tool": "acknowledge_alert", "args": {"alert_id": "alert-001"}}
{"tool": "set_priority", "args": {"alert_id": "alert-001", "priority": "P1"}}
{"tool": "assign_team", "args": {"alert_id": "alert-001", "team": "platform"}}
{"tool": "escalate", "args": {"level": "on_call_lead"}}
{"tool": "correlate_alerts", "args": {"alert_ids": "alert-001,alert-002,alert-003"}}
{"tool": "send_update", "args": {"message": "Investigating API gateway outage", "channel": "incident_channel"}}
""").strip()


# ─── Observation Formatter ────────────────────────────────────────────────────

def format_observation(obs_metadata: Dict[str, Any], step: int) -> str:
    """Format the observation into a readable prompt for the LLM."""
    alerts_info = []
    for alert in obs_metadata.get("alerts", []):
        status = alert.get("status", "unknown")
        priority = alert.get("assigned_priority", "unset")
        team = alert.get("assigned_team", "unassigned")
        alerts_info.append(
            f"  - [{alert['alert_id']}] [{alert['severity']}] {alert['title']}\n"
            f"    Service: {alert['service']} | Status: {status} | Priority: {priority} | Team: {team}\n"
            f"    Description: {alert['description'][:150]}..."
        )

    alerts_block = "\n".join(alerts_info) if alerts_info else "  No alerts"

    # Investigation results
    inv_results = obs_metadata.get("investigation_results", {})
    inv_block = ""
    if inv_results:
        inv_block = "\n\nInvestigation Results:\n"
        for aid, result in inv_results.items():
            inv_block += f"  [{aid}]: {result[:200]}...\n"

    # SLA timers
    sla_info = []
    for timer in obs_metadata.get("sla_timers", []):
        if timer.get("breached"):
            sla_info.append(f"  ⚠️ {timer['alert_id']}: SLA BREACHED!")
        elif timer.get("steps_remaining", 99) <= 3:
            sla_info.append(f"  🔴 {timer['alert_id']}: {timer['steps_remaining']} steps until SLA breach!")
    sla_block = "\n".join(sla_info) if sla_info else ""

    last_result = obs_metadata.get("last_action_result", "")
    system_status = obs_metadata.get("system_status", "unknown")
    step_num = obs_metadata.get("step_number", step)
    max_steps = obs_metadata.get("max_steps", 10)
    escalation = obs_metadata.get("escalation_state", {}).get("current_level", "none")

    return textwrap.dedent(f"""
=== STEP {step_num}/{max_steps} ===
System Status: {system_status}
Escalation Level: {escalation}
Last Action Result: {last_result}

Active Alerts:
{alerts_block}
{inv_block}
{f"SLA Warnings:{chr(10)}{sla_block}" if sla_block else ""}

What is your next action? Respond with a JSON tool call.
    """).strip()


# ─── LLM Interaction ─────────────────────────────────────────────────────────

def get_model_action(client: OpenAI, observation_prompt: str, history: List[str]) -> Dict[str, Any]:
    """Get the next action from the LLM."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add recent history for context
    for entry in history[-5:]:
        messages.append({"role": "assistant", "content": entry})

    messages.append({"role": "user", "content": observation_prompt})

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()

        # Parse JSON response
        # Try to extract JSON from the response (handle markdown code blocks)
        if "```" in text:
            # Extract from code block
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]

        parsed = json.loads(text)
        return parsed

    except json.JSONDecodeError:
        # Fallback: try to extract tool call from text
        print(f"[DEBUG] Failed to parse JSON from LLM response: {text[:200]}", flush=True)
        return {"tool": "get_status", "args": {}}
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return {"tool": "get_status", "args": {}}


# ─── Main Loop ────────────────────────────────────────────────────────────────

async def run_task(client: OpenAI, base_url: str, task_name: str) -> float:
    """Run a single task and return the score."""
    import httpx

    max_steps = MAX_STEPS_PER_TASK.get(task_name, 10)
    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as http:
            # Reset with specific task
            reset_resp = await http.post("/reset", json={"task": task_name})
            reset_data = reset_resp.json()
            obs_metadata = reset_data.get("observation", {})
            done = reset_data.get("done", False)

            for step in range(1, max_steps + 1):
                if done:
                    break

                # Format observation for LLM
                obs_prompt = format_observation(obs_metadata, step)

                # Get action from LLM
                action_dict = get_model_action(client, obs_prompt, history)
                tool_name = action_dict.get("tool", "get_status")
                tool_args = action_dict.get("args", {})

                # Execute via /step endpoint with CallToolAction
                action_str = f"{tool_name}({json.dumps(tool_args)})"
                try:
                    step_resp = await http.post("/step", json={
                        "action": {
                            "type": "call_tool",
                            "tool_name": tool_name,
                            "arguments": tool_args,
                        }
                    })
                    step_data = step_resp.json()

                    # Extract reward, done, and observation
                    reward = step_data.get("reward") or 0.0
                    done = step_data.get("done", False)
                    error = None

                    # Update observation for next step
                    obs_raw = step_data.get("observation", {})
                    if isinstance(obs_raw, dict):
                        # The observation from MCP step is the tool result
                        # Get fresh state from /state endpoint for full observation
                        pass

                    rewards.append(reward)
                    steps_taken = step

                    log_step(step=step, action=action_str, reward=reward, done=done, error=error)
                    history.append(json.dumps(action_dict))

                    if done:
                        break

                    # Get updated observation from reset (state endpoint)
                    # The /step returns MCP tool result, we need full observation
                    # Re-fetch via another reset-less state query if available
                    # For now, carry forward the observation metadata from tool result
                    tool_result_text = ""
                    if isinstance(obs_raw, dict):
                        result_data = obs_raw.get("result", {})
                        if isinstance(result_data, dict):
                            content = result_data.get("content", [])
                            if content and isinstance(content, list):
                                tool_result_text = content[0].get("text", "")
                            elif result_data.get("data"):
                                tool_result_text = str(result_data["data"])
                        elif isinstance(result_data, str):
                            tool_result_text = result_data

                    # Update obs_metadata with the tool result as "last_action_result"
                    if tool_result_text:
                        obs_metadata["last_action_result"] = tool_result_text

                except Exception as e:
                    error_msg = str(e)[:100]
                    rewards.append(-0.05)
                    steps_taken = step
                    log_step(step=step, action=action_str, reward=-0.05, done=False, error=error_msg)
                    history.append(json.dumps(action_dict))

        # Calculate final score from rewards
        if rewards:
            # Normalize: sum of positive rewards vs. max theoretical reward
            positive_rewards = sum(r for r in rewards if r > 0)
            max_possible = max_steps * 0.15  # conservative estimate
            raw_score = positive_rewards / max_possible if max_possible > 0 else 0.0
            score = max(0.0, min(1.0, raw_score))
        else:
            score = 0.0

        success = score >= SUCCESS_SCORE_THRESHOLD

    except Exception as e:
        print(f"[DEBUG] Task {task_name} failed: {e}", flush=True)
        import traceback
        traceback.print_exc()
        score = 0.0
        success = False

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


async def main() -> None:
    """Run all 3 tasks and report scores."""
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    # Determine environment base URL
    if IMAGE_NAME:
        # When using Docker, the OpenEnv infra handles container management
        # For now, assume the container is already running
        env_base_url = os.getenv("ENV_BASE_URL", "http://localhost:8000")
    else:
        env_base_url = os.getenv("ENV_BASE_URL", "http://localhost:8000")

    try:
        all_scores = {}
        for task_name in TASKS:
            print(f"\n{'='*60}", flush=True)
            print(f"Running task: {task_name}", flush=True)
            print(f"{'='*60}", flush=True)

            score = await run_task(client, env_base_url, task_name)
            all_scores[task_name] = score

        # Summary
        print(f"\n{'='*60}", flush=True)
        print("FINAL SCORES:", flush=True)
        print(f"{'='*60}", flush=True)
        for task, score in all_scores.items():
            print(f"  {task}: {score:.2f}", flush=True)
        avg_score = sum(all_scores.values()) / len(all_scores) if all_scores else 0.0
        print(f"  Average: {avg_score:.2f}", flush=True)

    except Exception as e:
        print(f"[DEBUG] Main failed: {e}", flush=True)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
