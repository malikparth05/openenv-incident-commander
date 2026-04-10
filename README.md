---
title: Incident Commander Env
emoji: 🚨
colorFrom: red
colorTo: blue
sdk: docker
pinned: false
tags:
  - openenv
---
# IncidentCommanderEnv -- IT Outage Management OpenEnv Environment

**Live Space:** https://huggingface.co/spaces/malikparth05/incident-commander-env

> An AI agent manages simulated real-world IT outages -- triaging alerts, querying live metrics, and navigating cascading failures based on historic incidents.

[![OpenEnv](https://img.shields.io/badge/OpenEnv-compatible-brightgreen)](https://github.com/meta-pytorch/OpenEnv)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Environment Description

**IncidentCommanderEnv** simulates the real-world job of an IT Incident Commander / Site Reliability Engineer (SRE) during a production outage. Each scenario is modeled after a **real-world historic incident** (GitHub 2018, Fastly 2021, AWS EBS, SolarWinds 2020). The agent receives a flood of monitoring alerts and must:

1. **Triage** -- Acknowledge and prioritize alerts (P1-P4)
2. **Diagnose** -- Investigate alerts and query live service metrics to identify root cause
3. **Route** -- Assign alerts to the correct engineering team
4. **Correlate** -- Group related alerts into incidents
5. **Escalate** -- Decide when to page leadership (and avoid alert fatigue)
6. **Communicate** -- Send status updates to stakeholders
7. **Postmortem** -- Write a postmortem identifying the root cause alert

### Key Features

- **Temporal Alert Cascading** -- Alerts appear at different steps as the incident spreads. Fixing the root cause early prevents cascade.
- **Live Service Metrics** -- `get_metrics(service_name)` returns latency, error rate, CPU, memory, and saturation data.
- **Detailed Grading Feedback** -- At episode end, the grader explains every point deducted (e.g., "Over-escalated noise alerts. Cost: -0.09").
- **Real-World Scenarios** -- Based on documented post-incident reports from GitHub, Fastly, AWS, and SolarWinds.

### Why This Matters

Incident management is a genuine, high-stakes task that companies pay $100K+ engineers to do. Mistakes cost real money:
- Over-escalation leads to alert fatigue and leadership losing trust
- Under-escalation leads to SLA breach and customer impact
- Wrong team routing delays resolution
- Missing correlation causes symptoms to be treated as separate incidents

---

## Action Space (MCP Tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `acknowledge_alert` | `alert_id: str` | Acknowledge an incoming alert |
| `set_priority` | `alert_id: str, priority: P1\|P2\|P3\|P4` | Set alert priority level |
| `assign_team` | `alert_id: str, team: str` | Route to: platform, database, network, application, infrastructure, security |
| `escalate` | `level: on_call_lead\|vp_eng\|cto` | Escalate incident to leadership |
| `send_update` | `message: str, channel: str` | Send status to: incident_channel, stakeholder_email, status_page |
| `search_runbooks` | `query: str` | Search engineering wikis for troubleshooting steps and team ownership |
| `mark_resolved` | `alert_id: str` | Mark an alert as resolved |
| `investigate` | `alert_id: str` | Get detailed investigation findings |
| `correlate_alerts` | `alert_ids: str` | Group related alerts (comma-separated IDs) |
| `get_status` | *(none)* | Get current incident status summary (includes cascade warnings) |
| `get_metrics` | `service_name: str` | Query real-time performance metrics (latency, error rate, CPU, memory, saturation) |
| `write_postmortem` | `root_cause_alert_id, incident_severity, resolution_summary` | Write incident postmortem identifying root cause |

---

## Observation Space

Each step, the agent receives:

| Field | Type | Description |
|-------|------|-------------|
| `alerts` | `List[Alert]` | Currently visible alerts (filtered by temporal cascading) |
| `teams` | `List[TeamInfo]` | Available teams, their specialties, and current load |
| `escalation_state` | `EscalationState` | Current escalation level and history |
| `sla_timers` | `List[SLATimer]` | Steps remaining before SLA breach per alert |
| `action_log` | `List[str]` | Last 10 actions taken with results |
| `system_status` | `str` | Overall health summary |
| `investigation_results` | `Dict[str, str]` | Detailed findings from investigations |
| `new_alerts_this_step` | `int` | Count of new cascading alerts that appeared this step |
| `step_number` / `max_steps` | `int` | Current step and episode limit |

---

## Tasks (Easy to Expert)

### Task 1: GitHub Database Failover (Easy)

Based on GitHub's October 2018 outage. A 43-second network interruption during routine maintenance triggers MySQL Orchestrator to failover, causing data divergence across 23 clusters. Alerts cascade as user-facing impact spreads.

- **Alerts:** 4 (2 at T=0, 1 at T=1, 1 at T=2)
- **Root Cause:** Network interconnect interruption (alert-001)
- **Max Steps:** 15

### Task 2: Fastly CDN Configuration Defect (Medium)

Based on Fastly's June 2021 global outage. A latent Varnish bug, introduced weeks earlier, is triggered by a customer config change. 85% of edge nodes crash, causing a thundering herd on origin servers. Includes 1 noise alert.

- **Alerts:** 8 (3 at T=0, 2 at T=1, 2 at T=2, 1 at T=3) + 1 noise
- **Root Cause:** CDN edge config defect (alert-101)
- **Max Steps:** 25

### Task 3: AWS Network Partition (Hard)

Based on AWS US-EAST-1 EBS outage patterns. Core switch hardware failure causes AZ-2 partition. EBS volumes stuck, services cascading through DNS, Kubernetes, payment, auth, and storage. 3 noise alerts mixed in.

- **Alerts:** 15 (3 at T=0, cascading through T=6) + 3 noise
- **Root Cause:** Core switch ASIC failure (alert-201)
- **Max Steps:** 45

### Task 4: SolarWinds Supply Chain Attack (Expert)

Based on SolarWinds 2020 attack pattern. CI/CD pipeline compromise injects a backdoor via trusted software update. Attacker uses it for lateral movement, credential stuffing, and 48 GB data exfiltration. 2 noise alerts.

- **Alerts:** 11 (cascading over 5 steps) + 2 noise
- **Root Cause:** CI/CD pipeline compromise (alert-301)
- **Max Steps:** 35

---

## Reward Function

Rewards are provided at every step (not just episode end):

| Action | Reward | Condition |
|--------|--------|-----------|
| Correct priority | +0.15 | Matches ground truth |
| Correct team | +0.15 | Matches ground truth |
| Correct escalation | +0.20 | Matches required level |
| Alert correlation | +0.10 | Grouping related alerts |
| Investigation | +0.05 | Gathering information |
| Metrics query | +0.05 | Data-driven investigation |
| Status update | +0.05 | Stakeholder communication |
| Wrong priority | -0.05 | Does not match ground truth |
| Wrong team | -0.05 | Incorrect routing |
| Over-escalation | -0.10 | Escalating beyond needed level |
| Invalid action | -0.05 | Bad parameters or nonexistent alert |

**Final Episode Score** (grader, 0.0-1.0):
- Priority accuracy: 20%
- Team routing accuracy: 20%
- Correlation accuracy: 15%
- Escalation judgment: 15%
- Root cause identification: 10%
- Time efficiency: 8%
- Communication: 7%
- SLA compliance: 5%

**Detailed Feedback** is provided at episode end explaining every deduction:
```
Strengths: priority assignment, SLA compliance
Areas for improvement:
  - Escalation: Over-escalated to 'cto' (needed 'vp_eng'). Alert fatigue risk. Cost: -0.09
  - Root Cause: Postmortem identified 'alert-103' but actual root cause was {'alert-101'}. Cost: -0.10
```

---

## Setup and Usage

### Prerequisites
```bash
pip install openenv-core[core]
```

### Install the Environment
```bash
pip install -e .
```

### Run the Server Locally
```bash
uvicorn server.app:app --host 0.0.0.0 --port 7860
```

### Run with Docker
```bash
docker build -t incident-commander-env .
docker run -p 7860:7860 incident-commander-env
```

### Run the Inference Script
```bash
export API_KEY="your-api-key-here"  # Or use HF_TOKEN
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
python inference.py
```

---

## Baseline Scores

| Task | Estimated Score | Human Expert | Model |
|------|----------------|-------------|-------|
| github_database_failover | ~0.65 | ~0.92 | Qwen2.5-72B-Instruct |
| fastly_cdn_outage | ~0.42 | ~0.88 | Qwen2.5-72B-Instruct |
| aws_network_partition | ~0.28 | ~0.85 | Qwen2.5-72B-Instruct |
| solarwinds_supply_chain | ~0.19 | ~0.90 | Qwen2.5-72B-Instruct |

*Scores are estimated. Human Expert baseline represents a scripted agent following optimal runbook procedures.*

---

## Project Structure

```
incident_commander_env/
  __init__.py              # Package exports
  models.py                # Pydantic models (Alert, ServiceMetrics, IncidentObservation, etc.)
  client.py                # IncidentCommanderEnv(MCPToolClient)
  scenarios.py             # 4 historic task scenarios with ground truth and metrics
  graders.py               # Deterministic graders with detailed feedback (0.0-1.0)
  runbooks.py              # Engineering wiki for search_runbooks tool

server/
  __init__.py
  app.py                   # FastAPI app
  environment.py           # MCPEnvironment subclass (temporal cascading + get_metrics)

inference.py               # Baseline inference script
openenv.yaml               # OpenEnv manifest
scenario_design.md         # Historic incident research and design rationale
Dockerfile                 # Container image
pyproject.toml             # Package config
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_BASE_URL` | No | `https://router.huggingface.co/v1` | LLM API endpoint |
| `MODEL_NAME` | No | `Qwen/Qwen2.5-72B-Instruct` | Model identifier |
| `API_KEY` | Yes | -- | API Token (HF_TOKEN works as fallback) |
| `LOCAL_IMAGE_NAME` | No | -- | Docker image name (if using from_docker_image) |

---

## License

MIT
