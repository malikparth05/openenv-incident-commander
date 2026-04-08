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
# IncidentCommanderEnv — IT Outage Management OpenEnv Environment

> An AI agent manages simulated IT/infrastructure outages — triaging alerts, delegating to teams, and deciding escalation order.

[![OpenEnv](https://img.shields.io/badge/OpenEnv-compatible-brightgreen)](https://github.com/meta-pytorch/OpenEnv)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Environment Description

**IncidentCommanderEnv** simulates the real-world job of an IT Incident Commander / Site Reliability Engineer (SRE) during a production outage. The agent receives a flood of monitoring alerts and must:

1. **Triage** — Acknowledge and prioritize alerts (P1–P4)
2. **Diagnose** — Investigate alerts to identify root cause vs. symptoms
3. **Route** — Assign alerts to the correct engineering team
4. **Correlate** — Group related alerts into incidents
5. **Escalate** — Decide when to page leadership (and avoid alert fatigue)
6. **Communicate** — Send status updates to stakeholders

### Why This Matters

Incident management is a **genuine, high-stakes task** that companies pay $100K+ engineers to do. Mistakes cost real money:
- Over-escalation → alert fatigue, leadership loses trust
- Under-escalation → SLA breach, customer impact
- Wrong team routing → delayed resolution
- Missing correlation → symptoms treated as separate incidents

This environment provides a **realistic training and evaluation ground** for AI agents in production operations.

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
| `get_status` | *(none)* | Get current incident status summary |

---

## Observation Space

Each step, the agent receives:

| Field | Type | Description |
|-------|------|-------------|
| `alerts` | `List[Alert]` | All active alerts with id, service, severity, title, description, status, assigned_priority, assigned_team |
| `teams` | `List[TeamInfo]` | Available teams, their specialties, and current load |
| `escalation_state` | `EscalationState` | Current escalation level and history |
| `sla_timers` | `List[SLATimer]` | Steps remaining before SLA breach per alert |
| `action_log` | `List[str]` | Last 10 actions taken with results |
| `system_status` | `str` | Overall health summary |
| `investigation_results` | `Dict[str, str]` | Detailed findings from investigations |
| `step_number` / `max_steps` | `int` | Current step and episode limit |

---

## Tasks (Easy → Medium → Hard)

### Task 1: Single Service Outage (Easy)
- **Alerts:** 3 alerts from a single API gateway outage
- **Objective:** Acknowledge, prioritize P1, route to platform team, send update
- **Max Steps:** 10
- **Expected Difficulty:** Most models should score 0.6+

### Task 2: Multi-Service Degradation (Medium)
- **Alerts:** 8 alerts across database, cache, and application services
- **Objective:** Identify DB connection pool as root cause, correlate all 8 alerts, route to correct teams (DB team for root cause, App team for symptoms), escalate to on-call lead
- **Expected Difficulty:** Good models should score 0.4–0.7

### Task 3: Cascading Infrastructure Failure (Hard)
- **Alerts:** 15 alerts across 6+ services, including 3 noise/false positives
- **Objective:** Filter noise (cert expiry, scheduled deployment, auto-scaling), identify network partition as root cause, correlate 12 real alerts, escalate to VP Eng, communicate updates
- **Expected Difficulty:** Frontier models may score 0.3–0.6

---

## Reward Function

Rewards are provided at **every step** (not just episode end):

| Action | Reward | Condition |
|--------|--------|-----------|
| Correct priority | +0.15 | Matches ground truth |
| Correct team | +0.15 | Matches ground truth |
| Correct escalation | +0.20 | Matches required level |
| Alert correlation | +0.10 | Grouping related alerts |
| Investigation | +0.05 | Gathering information |
| Status update | +0.05 | Stakeholder communication |
| Wrong priority | -0.05 | Does not match ground truth |
| Wrong team | -0.05 | Incorrect routing |
| Over-escalation | -0.10 | Escalating beyond needed level |
| Invalid action | -0.05 | Bad parameters or nonexistent alert |

**Final Episode Score** (grader, 0.0–1.0):
- Priority accuracy: 25%
- Team routing accuracy: 25%
- Correlation accuracy: 20%
- Escalation judgment: 15%
- Time efficiency: 10%
- Communication: 5%

---

## Setup & Usage

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

| Task | Score | Model |
|------|-------|-------|
| single_service_outage | ~0.60 | Qwen2.5-72B-Instruct |
| multi_service_degradation | ~0.40 | Qwen2.5-72B-Instruct |
| cascading_infrastructure_failure | ~0.25 | Qwen2.5-72B-Instruct |

*Scores are approximate and vary with model temperature and version. A perfect scripted agent scores ~0.82 (Task 1), ~0.85 (Task 2), ~0.73 (Task 3).*

---

## Project Structure

```
incident_commander_env/
├── __init__.py              # Package exports
├── models.py                # Pydantic Action, Observation, State models
├── client.py                # IncidentCommanderEnv(MCPToolClient)
├── scenarios.py             # 3 task scenarios with ground truth
├── graders.py               # Deterministic graders (0.0–1.0)
├── runbooks.py              # Engineering wiki data for search_runbooks tool
├── openenv.yaml             # OpenEnv manifest
├── pyproject.toml            # Package config
├── README.md                # This file
└── server/
    ├── __init__.py
    ├── app.py               # FastAPI app
    ├── environment.py        # MCPEnvironment subclass
    └── Dockerfile            # Container image
inference.py                  # Baseline inference script (root)
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_BASE_URL` | No | `https://router.huggingface.co/v1` | LLM API endpoint |
| `MODEL_NAME` | No | `Qwen/Qwen2.5-72B-Instruct` | Model identifier |
| `API_KEY` | Yes | — | API Token (HF_TOKEN works as fallback) |
| `LOCAL_IMAGE_NAME` | No | — | Docker image name (if using from_docker_image) |
| `ENV_BASE_URL` | No | `http://localhost:8000` | Environment server URL |

---

## License

MIT
