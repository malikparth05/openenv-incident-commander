"""
Local test for inference pipeline — uses a scripted "smart" agent
instead of an LLM, to validate the full loop + logging format.
"""

import asyncio
import json
from incident_commander_env import IncidentCommanderEnv

BENCHMARK = "incident_commander_env"
MODEL_NAME = "scripted-agent"

# ─── Same logging format as real inference.py ─────────────────────────────────

def log_start(task, env, model):
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step, action, reward, done, error):
    error_val = error if error else "null"
    done_val = str(done).lower()
    action_clean = action.replace("\n", " ")[:200]
    print(f"[STEP] step={step} action={action_clean} reward={reward:.2f} done={done_val} error={error_val}", flush=True)

def log_end(success, steps, score, rewards):
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)


# ─── Scripted agent actions per task ──────────────────────────────────────────

TASK1_ACTIONS = [
    ("acknowledge_alert", {"alert_id": "alert-001"}),
    ("acknowledge_alert", {"alert_id": "alert-002"}),
    ("acknowledge_alert", {"alert_id": "alert-003"}),
    ("set_priority", {"alert_id": "alert-001", "priority": "P1"}),
    ("set_priority", {"alert_id": "alert-002", "priority": "P1"}),
    ("set_priority", {"alert_id": "alert-003", "priority": "P2"}),
    ("assign_team", {"alert_id": "alert-001", "team": "platform"}),
    ("assign_team", {"alert_id": "alert-002", "team": "platform"}),
    ("assign_team", {"alert_id": "alert-003", "team": "platform"}),
    ("correlate_alerts", {"alert_ids": "alert-001,alert-002,alert-003"}),
    ("escalate", {"level": "on_call_lead"}),
    ("send_update", {"message": "Investigating API gateway outage affecting all routes", "channel": "incident_channel"}),
]

TASK2_ACTIONS = [
    ("acknowledge_alert", {"alert_id": "alert-101"}),
    ("investigate", {"alert_id": "alert-101"}),
    ("set_priority", {"alert_id": "alert-101", "priority": "P1"}),
    ("assign_team", {"alert_id": "alert-101", "team": "database"}),
    ("set_priority", {"alert_id": "alert-104", "priority": "P1"}),
    ("assign_team", {"alert_id": "alert-104", "team": "application"}),
    ("set_priority", {"alert_id": "alert-102", "priority": "P2"}),
    ("assign_team", {"alert_id": "alert-102", "team": "database"}),
    ("set_priority", {"alert_id": "alert-103", "priority": "P2"}),
    ("assign_team", {"alert_id": "alert-103", "team": "application"}),
    ("set_priority", {"alert_id": "alert-105", "priority": "P3"}),
    ("assign_team", {"alert_id": "alert-105", "team": "database"}),
    ("set_priority", {"alert_id": "alert-106", "priority": "P3"}),
    ("assign_team", {"alert_id": "alert-106", "team": "application"}),
    ("set_priority", {"alert_id": "alert-107", "priority": "P3"}),
    ("assign_team", {"alert_id": "alert-107", "team": "application"}),
    ("set_priority", {"alert_id": "alert-108", "priority": "P4"}),
    ("assign_team", {"alert_id": "alert-108", "team": "application"}),
    ("correlate_alerts", {"alert_ids": "alert-101,alert-102,alert-103,alert-104,alert-105,alert-106,alert-107,alert-108"}),
    ("escalate", {"level": "on_call_lead"}),
    ("send_update", {"message": "Root cause: DB connection pool exhaustion from stuck batch job", "channel": "incident_channel"}),
    ("send_update", {"message": "All teams engaged. ETA 30min for resolution", "channel": "stakeholder_email"}),
]

TASK3_ACTIONS = [
    ("investigate", {"alert_id": "alert-201"}),
    ("investigate", {"alert_id": "alert-208"}),
    ("investigate", {"alert_id": "alert-211"}),
    ("set_priority", {"alert_id": "alert-201", "priority": "P1"}),
    ("assign_team", {"alert_id": "alert-201", "team": "network"}),
    ("set_priority", {"alert_id": "alert-202", "priority": "P1"}),
    ("assign_team", {"alert_id": "alert-202", "team": "network"}),
    ("set_priority", {"alert_id": "alert-203", "priority": "P1"}),
    ("assign_team", {"alert_id": "alert-203", "team": "infrastructure"}),
    ("set_priority", {"alert_id": "alert-204", "priority": "P1"}),
    ("assign_team", {"alert_id": "alert-204", "team": "application"}),
    ("set_priority", {"alert_id": "alert-205", "priority": "P1"}),
    ("assign_team", {"alert_id": "alert-205", "team": "security"}),
    ("set_priority", {"alert_id": "alert-206", "priority": "P2"}),
    ("assign_team", {"alert_id": "alert-206", "team": "infrastructure"}),
    ("set_priority", {"alert_id": "alert-207", "priority": "P2"}),
    ("assign_team", {"alert_id": "alert-207", "team": "infrastructure"}),
    ("set_priority", {"alert_id": "alert-208", "priority": "P4"}),
    ("assign_team", {"alert_id": "alert-208", "team": "security"}),
    ("set_priority", {"alert_id": "alert-209", "priority": "P3"}),
    ("assign_team", {"alert_id": "alert-209", "team": "infrastructure"}),
    ("set_priority", {"alert_id": "alert-210", "priority": "P1"}),
    ("assign_team", {"alert_id": "alert-210", "team": "platform"}),
    ("set_priority", {"alert_id": "alert-211", "priority": "P4"}),
    ("assign_team", {"alert_id": "alert-211", "team": "application"}),
    ("set_priority", {"alert_id": "alert-212", "priority": "P2"}),
    ("assign_team", {"alert_id": "alert-212", "team": "database"}),
    ("set_priority", {"alert_id": "alert-213", "priority": "P4"}),
    ("assign_team", {"alert_id": "alert-213", "team": "infrastructure"}),
    ("set_priority", {"alert_id": "alert-214", "priority": "P2"}),
    ("assign_team", {"alert_id": "alert-214", "team": "platform"}),
    ("set_priority", {"alert_id": "alert-215", "priority": "P3"}),
    ("assign_team", {"alert_id": "alert-215", "team": "infrastructure"}),
    ("correlate_alerts", {"alert_ids": "alert-201,alert-202,alert-203,alert-204,alert-205,alert-206,alert-207,alert-209,alert-210,alert-212,alert-214,alert-215"}),
    ("escalate", {"level": "vp_eng"}),
    ("send_update", {"message": "Major network partition detected - core switch failure", "channel": "incident_channel"}),
    ("send_update", {"message": "Network team investigating hw failure on sw-core-02", "channel": "stakeholder_email"}),
    ("send_update", {"message": "Service degradation due to network partition. ETA 2hrs", "channel": "status_page"}),
]

SCRIPTED_TASKS = {
    "single_service_outage": TASK1_ACTIONS,
    "multi_service_degradation": TASK2_ACTIONS,
    "cascading_infrastructure_failure": TASK3_ACTIONS,
}


async def run_task(env, task_name):
    from incident_commander_env import CallToolAction
    actions = SCRIPTED_TASKS[task_name]
    rewards = []
    steps_taken = 0

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    try:
        await env.reset(task=task_name)
        score = 0.0
        success = False

        for step, (tool_name, tool_args) in enumerate(actions, 1):
            action_str = f"{tool_name}({json.dumps(tool_args)})"
            try:
                action = CallToolAction(tool_name=tool_name, arguments=tool_args)
                result = await env.step(action)
                
                reward = result.reward if result.reward is not None else 0.0
                done = result.done
                
                rewards.append(reward)
                steps_taken = step
                log_step(step=step, action=action_str, reward=reward, done=done, error=None)
                
                if done:
                    break
            except Exception as e:
                rewards.append(-0.05)
                steps_taken = step
                log_step(step=step, action=action_str, reward=-0.05, done=False, error=str(e)[:80])

        # Estimate score based on sum of the real rewards in the script
        score = max(0.0, min(1.0, sum(rewards) / max(1, len(rewards))))
        success = score > 0.3

    except Exception as e:
        print(f"[DEBUG] Task {task_name} failed: {e}")
        score = 0.0
        success = False

    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    return score


async def main():
    env = IncidentCommanderEnv(base_url="https://malikparth05-incident-commander-env.hf.space")

    all_scores = {}
    for task_name in ["single_service_outage", "multi_service_degradation", "cascading_infrastructure_failure"]:
        print(f"\n{'='*60}")
        print(f"Running task: {task_name}")
        print(f"{'='*60}")
        score = await run_task(env, task_name)
        all_scores[task_name] = score

    print(f"\n{'='*60}")
    print("FINAL SCORES:")
    print(f"{'='*60}")
    for task, score in all_scores.items():
        print(f"  {task}: {score:.2f}")
    avg = sum(all_scores.values()) / len(all_scores)
    print(f"  Average: {avg:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
