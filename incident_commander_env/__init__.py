"""
Incident Commander Environment — IT Outage Management OpenEnv Environment.

An agent manages simulated IT/infrastructure outages by triaging alerts,
delegating to teams, and deciding escalation order.

MCP Tools:
- acknowledge_alert(alert_id): Acknowledge an incoming alert
- set_priority(alert_id, priority): Set alert priority (P1/P2/P3/P4)
- assign_team(alert_id, team): Route alert to a team
- escalate(level): Escalate incident to leadership
- send_update(message, channel): Communicate status
- mark_resolved(alert_id): Resolve an alert
- investigate(alert_id): Get more details about an alert
- correlate_alerts(alert_ids): Group related alerts
- get_status(): Get current system status summary

Example:
    >>> from incident_commander_env import IncidentCommanderEnv
    >>>
    >>> with IncidentCommanderEnv(base_url="http://localhost:8000") as env:
    ...     env.reset()
    ...     tools = env.list_tools()
    ...     result = env.call_tool("acknowledge_alert", alert_id="alert-001")
"""

from openenv.core.env_server.mcp_types import CallToolAction, ListToolsAction

from .client import IncidentCommanderEnv

__all__ = ["IncidentCommanderEnv", "CallToolAction", "ListToolsAction"]
