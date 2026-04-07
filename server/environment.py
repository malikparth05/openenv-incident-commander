"""
Incident Commander Environment — Server-side Implementation.

A pure MCP environment that simulates IT/infrastructure outage management.
Agents triage alerts, delegate to teams, and decide escalation order.

All interactions happen through MCP tools:
- acknowledge_alert(alert_id)
- set_priority(alert_id, priority)
- assign_team(alert_id, team)
- escalate(level)
- send_update(message, channel)
- mark_resolved(alert_id)
- investigate(alert_id)
- correlate_alerts(alert_ids)
- get_status()
"""

import copy
import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openenv.core.env_server.mcp_environment import MCPEnvironment
from openenv.core.env_server.types import Action, Observation, State

from fastmcp import FastMCP

# Import our models and scenario data — support both package and standalone modes
try:
    # Package mode (when installed as incident_commander_env package)
    from incident_commander_env.models import (
        Alert,
        AlertStatus,
        EscalationLevel,
        EscalationState,
        IncidentObservation,
        IncidentState,
        Priority,
        SLATimer,
        Team,
    )
    from incident_commander_env.scenarios import get_scenario, list_tasks
    from incident_commander_env.graders import grade_episode
    from incident_commander_env.runbooks import perform_search
except ImportError:
    # Standalone mode (inside Docker container where CWD is the env root)
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from models import (
        Alert,
        AlertStatus,
        EscalationLevel,
        EscalationState,
        IncidentObservation,
        IncidentState,
        Priority,
        SLATimer,
        Team,
    )
    from scenarios import get_scenario, list_tasks
    from graders import grade_episode
    from runbooks import perform_search


class IncidentCommanderEnvironment(MCPEnvironment):
    """
    IT Incident Commander — an MCP environment for outage management.

    The agent receives system alerts and must:
    1. Acknowledge and prioritize alerts
    2. Route to correct engineering teams
    3. Correlate related alerts
    4. Escalate appropriately
    5. Communicate status updates

    Reward is shaped around correctness, speed, and avoiding alert fatigue.
    """

    def __init__(self):
        """Initialize the environment with MCP tools."""
        mcp = FastMCP("incident_commander_env")

        # Store reference to self for tool closures
        env = self

        @mcp.tool
        def acknowledge_alert(alert_id: str) -> str:
            """
            Acknowledge an incoming alert to signal you've seen it.

            Args:
                alert_id: The ID of the alert to acknowledge (e.g., 'alert-001')

            Returns:
                Result message confirming the acknowledgment
            """
            return env._handle_acknowledge(alert_id)

        @mcp.tool
        def set_priority(alert_id: str, priority: str) -> str:
            """
            Set or change the priority level of an alert.

            Args:
                alert_id: The ID of the alert
                priority: Priority level — one of 'P1' (critical), 'P2' (high), 'P3' (medium), 'P4' (low)

            Returns:
                Result message confirming the priority change
            """
            return env._handle_set_priority(alert_id, priority)

        @mcp.tool
        def assign_team(alert_id: str, team: str) -> str:
            """
            Route an alert to an engineering team for resolution.

            Args:
                alert_id: The ID of the alert
                team: Team name — one of 'platform', 'database', 'network', 'application', 'infrastructure', 'security'

            Returns:
                Result message confirming the team assignment
            """
            return env._handle_assign_team(alert_id, team)

        @mcp.tool
        def escalate(level: str) -> str:
            """
            Escalate the overall incident to a higher authority.

            Args:
                level: Escalation level — one of 'on_call_lead', 'vp_eng', 'cto'

            Returns:
                Result message confirming the escalation
            """
            return env._handle_escalate(level)

        @mcp.tool
        def send_update(message: str, channel: str) -> str:
            """
            Send a status update about the incident to stakeholders.

            Args:
                message: The status update message to send
                channel: Channel — one of 'incident_channel', 'stakeholder_email', 'status_page'

            Returns:
                Result message confirming the update was sent
            """
            return env._handle_send_update(message, channel)

        @mcp.tool
        def search_runbooks(query: str) -> str:
            """
            Search the engineering runbooks and wiki for troubleshooting steps and team ownership.

            Args:
                query: Keywords to search for (e.g., 'api gateway', 'database replication')

            Returns:
                Relevant runbook excerpts
            """
            return env._handle_search_runbooks(query)

        @mcp.tool
        def mark_resolved(alert_id: str) -> str:
            """
            Mark an alert as resolved.

            Args:
                alert_id: The ID of the alert to resolve

            Returns:
                Result message confirming the resolution
            """
            return env._handle_mark_resolved(alert_id)

        @mcp.tool
        def investigate(alert_id: str) -> str:
            """
            Investigate an alert to get more detailed information about it.

            Args:
                alert_id: The ID of the alert to investigate

            Returns:
                Detailed investigation findings about the alert
            """
            return env._handle_investigate(alert_id)

        @mcp.tool
        def correlate_alerts(alert_ids: str) -> str:
            """
            Group related alerts together as part of the same incident.

            Args:
                alert_ids: Comma-separated alert IDs to group together (e.g., 'alert-001,alert-002,alert-003')

            Returns:
                Result message confirming the correlation
            """
            return env._handle_correlate(alert_ids)

        @mcp.tool
        def get_status() -> str:
            """
            Get a summary of the current incident status.

            Returns:
                Current status summary including active alerts, teams, and escalation state
            """
            return env._handle_get_status()

        super().__init__(mcp)

        # Internal state
        self._env_state = IncidentState()
        self._scenario: Optional[dict] = None
        self._ground_truth = None
        self._sla_timers: List[SLATimer] = []
        self._investigation_data: Dict[str, str] = {}
        self._investigation_results: Dict[str, str] = {}
        self._max_steps: int = 10
        self._step_rewards: List[float] = []
        self._correlated_groups: Dict[str, List[str]] = {}
        self._correlation_counter: int = 0
        self._updates_sent: int = 0
        self._teams = []
        self._last_action_result: str = ""
        self._last_action_error: Optional[str] = None

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Observation:
        """Reset the environment with a specific task scenario."""
        task_name = kwargs.get("task", "single_service_outage")

        # Load scenario
        scenario = get_scenario(task_name)

        self._scenario = scenario
        self._ground_truth = scenario["ground_truth"]
        self._sla_timers = scenario["sla_timers"]
        self._investigation_data = scenario["investigation_data"]
        self._investigation_results = {}
        self._max_steps = scenario["max_steps"]
        self._step_rewards = []
        self._correlated_groups = {}
        self._correlation_counter = 0
        self._updates_sent = 0
        self._last_action_result = f"Incident Commander initialized. Task: {task_name}. You have {len(scenario['alerts'])} alerts to manage."
        self._last_action_error = None

        # Import teams
        try:
            from incident_commander_env.scenarios import get_teams
        except ImportError:
            from scenarios import get_teams
        self._teams = get_teams()

        # Initialize state
        self._env_state = IncidentState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_name=task_name,
            done=False,
            total_reward=0.0,
            alerts=scenario["alerts"],
            escalation_state=EscalationState(),
            action_log=[],
            correlated_groups={},
            updates_sent=0,
        )

        return self._make_observation()

    def _make_observation(self) -> Observation:
        """Create an observation from current state."""
        # Filter out hidden fields from alerts for the agent
        visible_alerts = []
        for alert in self._env_state.alerts:
            visible = alert.model_copy()
            # Agent shouldn't see internal metadata
            visible.is_noise = False  # Hide this from agent
            visible.correlation_group = None  # Hide this from agent
            visible_alerts.append(visible)

        obs_data = IncidentObservation(
            alerts=visible_alerts,
            teams=self._teams,
            escalation_state=self._env_state.escalation_state,
            sla_timers=self._sla_timers,
            action_log=self._env_state.action_log[-10:],  # Last 10 actions
            system_status=self._compute_system_status(),
            step_number=self._env_state.step_count,
            max_steps=self._max_steps,
            task_name=self._env_state.task_name,
            last_action_result=self._last_action_result,
            last_action_error=self._last_action_error,
            investigation_results=self._investigation_results,
        )

        reward = self._step_rewards[-1] if self._step_rewards else 0.0

        return Observation(
            done=self._env_state.done,
            reward=reward,
            metadata=obs_data.model_dump(),
        )

    def _compute_system_status(self) -> str:
        """Compute overall system status summary."""
        critical_count = sum(
            1 for a in self._env_state.alerts
            if a.severity.value == "critical" and a.status != AlertStatus.RESOLVED
        )
        warning_count = sum(
            1 for a in self._env_state.alerts
            if a.severity.value == "warning" and a.status != AlertStatus.RESOLVED
        )
        resolved_count = sum(
            1 for a in self._env_state.alerts
            if a.status == AlertStatus.RESOLVED
        )
        total = len(self._env_state.alerts)

        if critical_count == 0 and warning_count == 0:
            return f"ALL CLEAR — {resolved_count}/{total} alerts resolved"
        elif critical_count > 3:
            return f"MAJOR INCIDENT — {critical_count} critical, {warning_count} warning, {resolved_count} resolved"
        elif critical_count > 0:
            return f"ACTIVE INCIDENT — {critical_count} critical, {warning_count} warning, {resolved_count} resolved"
        else:
            return f"DEGRADED — {warning_count} warnings active, {resolved_count} resolved"

    def _find_alert(self, alert_id: str) -> Optional[Alert]:
        """Find an alert by ID."""
        for alert in self._env_state.alerts:
            if alert.alert_id == alert_id:
                return alert
        return None

    def _compute_step_reward(self, action_type: str, success: bool, details: dict = None) -> float:
        """Compute reward for a single step action."""
        if not success:
            return -0.05  # Small penalty for invalid actions

        details = details or {}
        reward = 0.0

        if action_type == "acknowledge":
            reward = 0.05  # Small reward for acknowledging

        elif action_type == "set_priority":
            # Check if priority is correct
            alert_id = details.get("alert_id")
            priority = details.get("priority")
            if self._ground_truth:
                for truth in self._ground_truth.alert_truths:
                    if truth.alert_id == alert_id:
                        if priority == truth.correct_priority.value:
                            reward = 0.15  # Correct priority
                        elif _priority_near(priority, truth.correct_priority.value):
                            reward = 0.05  # Close but not exact
                        else:
                            reward = -0.05  # Wrong priority
                        break

        elif action_type == "assign_team":
            alert_id = details.get("alert_id")
            team = details.get("team")
            if self._ground_truth:
                for truth in self._ground_truth.alert_truths:
                    if truth.alert_id == alert_id:
                        if team.lower() == truth.correct_team.value.lower():
                            reward = 0.15  # Correct team
                        else:
                            reward = -0.05  # Wrong team
                        break

        elif action_type == "escalate":
            level = details.get("level")
            if self._ground_truth:
                required = self._ground_truth.required_escalation_level.value
                if level == required:
                    reward = 0.2  # Perfect escalation
                elif _escalation_near(level, required):
                    reward = 0.05  # Close
                else:
                    reward = -0.1  # Over or under escalation

        elif action_type == "correlate":
            # Reward for grouping alerts correctly
            reward = 0.1  # Base reward for attempting correlation

        elif action_type == "send_update":
            reward = 0.05  # Reward for communication

        elif action_type == "investigate":
            reward = 0.05  # Reward for investigation

        elif action_type == "mark_resolved":
            reward = 0.05

        return reward

    # ─── MCP Tool Handlers ────────────────────────────────────────────────────

    def _handle_acknowledge(self, alert_id: str) -> str:
        alert = self._find_alert(alert_id)
        if alert is None:
            self._record_action(f"acknowledge({alert_id}) — FAILED: alert not found", -0.05)
            return f"Error: Alert '{alert_id}' not found."

        if alert.status != AlertStatus.NEW:
            self._record_action(f"acknowledge({alert_id}) — already acknowledged", 0.0)
            return f"Alert '{alert_id}' is already in status '{alert.status.value}'."

        alert.status = AlertStatus.ACKNOWLEDGED
        reward = self._compute_step_reward("acknowledge", True)
        self._record_action(f"acknowledge({alert_id}) — OK", reward)
        return f"Alert '{alert_id}' acknowledged. Status changed to 'acknowledged'. Title: {alert.title}"

    def _handle_set_priority(self, alert_id: str, priority: str) -> str:
        alert = self._find_alert(alert_id)
        if alert is None:
            self._record_action(f"set_priority({alert_id}, {priority}) — FAILED: alert not found", -0.05)
            return f"Error: Alert '{alert_id}' not found."

        priority = priority.upper()
        valid_priorities = ["P1", "P2", "P3", "P4"]
        if priority not in valid_priorities:
            self._record_action(f"set_priority({alert_id}, {priority}) — FAILED: invalid priority", -0.05)
            return f"Error: Invalid priority '{priority}'. Must be one of: {valid_priorities}"

        old_priority = alert.assigned_priority
        alert.assigned_priority = Priority(priority)
        reward = self._compute_step_reward("set_priority", True, {"alert_id": alert_id, "priority": priority})
        self._record_action(f"set_priority({alert_id}, {priority}) — OK (was {old_priority})", reward)
        return f"Alert '{alert_id}' priority set to {priority}."

    def _handle_assign_team(self, alert_id: str, team: str) -> str:
        alert = self._find_alert(alert_id)
        if alert is None:
            self._record_action(f"assign_team({alert_id}, {team}) — FAILED: alert not found", -0.05)
            return f"Error: Alert '{alert_id}' not found."

        team_lower = team.lower()
        valid_teams = [t.name for t in self._teams]
        if team_lower not in valid_teams:
            self._record_action(f"assign_team({alert_id}, {team}) — FAILED: invalid team", -0.05)
            return f"Error: Invalid team '{team}'. Must be one of: {valid_teams}"

        alert.assigned_team = team_lower
        alert.status = AlertStatus.ASSIGNED
        reward = self._compute_step_reward("assign_team", True, {"alert_id": alert_id, "team": team_lower})

        # Update team load
        for t in self._teams:
            if t.name == team_lower:
                t.current_load += 1

        self._record_action(f"assign_team({alert_id}, {team_lower}) — OK", reward)
        return f"Alert '{alert_id}' assigned to team '{team_lower}'. Team notified and investigating."

    def _handle_escalate(self, level: str) -> str:
        level_lower = level.lower()
        valid_levels = ["on_call_lead", "vp_eng", "cto"]
        if level_lower not in valid_levels:
            self._record_action(f"escalate({level}) — FAILED: invalid level", -0.05)
            return f"Error: Invalid escalation level '{level}'. Must be one of: {valid_levels}"

        escalation_level = EscalationLevel(level_lower)
        old_level = self._env_state.escalation_state.current_level

        self._env_state.escalation_state.current_level = escalation_level
        self._env_state.escalation_state.escalation_history.append(
            f"Escalated to {level_lower} (from {old_level.value})"
        )

        reward = self._compute_step_reward("escalate", True, {"level": level_lower})
        self._record_action(f"escalate({level_lower}) — OK (was {old_level.value})", reward)
        return f"Incident escalated to {level_lower}. {level_lower.replace('_', ' ').title()} has been paged."

    def _handle_send_update(self, message: str, channel: str) -> str:
        valid_channels = ["incident_channel", "stakeholder_email", "status_page"]
        channel_lower = channel.lower()
        if channel_lower not in valid_channels:
            self._record_action(f"send_update(channel={channel}) — FAILED: invalid channel", -0.05)
            return f"Error: Invalid channel '{channel}'. Must be one of: {valid_channels}"

        self._updates_sent += 1
        self._env_state.updates_sent = self._updates_sent
        reward = self._compute_step_reward("send_update", True)
        self._record_action(f"send_update({channel_lower}, len={len(message)}) — OK", reward)
        return f"Status update sent to {channel_lower}. Message delivered to all subscribers."

    def _handle_search_runbooks(self, query: str) -> str:
        if not query or len(query.strip()) < 3:
            self._record_action(f"search_runbooks({query}) — FAILED: query too short", -0.05)
            return "Error: Search query must be at least 3 characters long."
            
        result = perform_search(query)
        reward = 0.05 # small reward for consulting documentation
        self._record_action(f"search_runbooks({query}) — OK", reward)
        return result

    def _handle_mark_resolved(self, alert_id: str) -> str:
        alert = self._find_alert(alert_id)
        if alert is None:
            self._record_action(f"mark_resolved({alert_id}) — FAILED: alert not found", -0.05)
            return f"Error: Alert '{alert_id}' not found."

        alert.status = AlertStatus.RESOLVED
        reward = self._compute_step_reward("mark_resolved", True)
        self._record_action(f"mark_resolved({alert_id}) — OK", reward)

        # Check if all alerts resolved → episode done
        all_resolved = all(a.status == AlertStatus.RESOLVED for a in self._env_state.alerts)
        if all_resolved:
            self._env_state.done = True

        return f"Alert '{alert_id}' marked as resolved."

    def _handle_investigate(self, alert_id: str) -> str:
        alert = self._find_alert(alert_id)
        if alert is None:
            self._record_action(f"investigate({alert_id}) — FAILED: alert not found", -0.05)
            return f"Error: Alert '{alert_id}' not found."

        alert.status = AlertStatus.INVESTIGATING
        result = self._investigation_data.get(
            alert_id,
            f"No additional investigation data available for alert '{alert_id}'."
        )
        self._investigation_results[alert_id] = result
        reward = self._compute_step_reward("investigate", True)
        self._record_action(f"investigate({alert_id}) — OK", reward)
        return result

    def _handle_correlate(self, alert_ids_str: str) -> str:
        alert_ids = [aid.strip() for aid in alert_ids_str.split(",") if aid.strip()]

        if len(alert_ids) < 2:
            self._record_action(f"correlate({alert_ids_str}) — FAILED: need 2+ alerts", -0.05)
            return "Error: Need at least 2 alert IDs to correlate. Provide comma-separated IDs."

        # Verify all IDs exist
        for aid in alert_ids:
            if self._find_alert(aid) is None:
                self._record_action(f"correlate({alert_ids_str}) — FAILED: {aid} not found", -0.05)
                return f"Error: Alert '{aid}' not found."

        self._correlation_counter += 1
        group_name = f"incident_group_{self._correlation_counter}"
        self._correlated_groups[group_name] = alert_ids
        self._env_state.correlated_groups = self._correlated_groups

        reward = self._compute_step_reward("correlate", True)
        self._record_action(f"correlate({alert_ids_str}) -> {group_name}", reward)
        return f"Alerts {alert_ids} correlated as '{group_name}'. These alerts will be tracked as a single incident."

    def _handle_get_status(self) -> str:
        status = self._compute_system_status()
        total = len(self._env_state.alerts)
        ack = sum(1 for a in self._env_state.alerts if a.status != AlertStatus.NEW)
        assigned = sum(1 for a in self._env_state.alerts if a.status == AlertStatus.ASSIGNED)
        resolved = sum(1 for a in self._env_state.alerts if a.status == AlertStatus.RESOLVED)
        esc = self._env_state.escalation_state.current_level.value
        groups = len(self._correlated_groups)

        return (
            f"=== INCIDENT STATUS ===\n"
            f"Overall: {status}\n"
            f"Alerts: {total} total, {ack} acknowledged, {assigned} assigned, {resolved} resolved\n"
            f"Escalation: {esc}\n"
            f"Correlation groups: {groups}\n"
            f"Status updates sent: {self._updates_sent}\n"
            f"Step: {self._env_state.step_count}/{self._max_steps}\n"
            f"========================"
        )

    def _record_action(self, log_entry: str, reward: float):
        """Record an action in the log and add its reward."""
        self._env_state.action_log.append(f"[Step {self._env_state.step_count}] {log_entry} (reward: {reward:+.2f})")
        self._step_rewards.append(reward)
        self._env_state.total_reward += reward
        self._last_action_result = log_entry
        self._last_action_error = None if reward >= 0 else log_entry

    def _tick_sla_timers(self):
        """Decrement SLA timers each step."""
        for timer in self._sla_timers:
            if not timer.breached:
                timer.steps_remaining -= 1
                if timer.steps_remaining <= 0:
                    timer.breached = True

    def _step_impl(
        self,
        action: Action,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> Observation:
        """Handle non-MCP actions."""
        return Observation(
            done=False,
            reward=0.0,
            metadata={
                "error": f"Unknown action type: {type(action).__name__}. "
                "Use MCP tools: acknowledge_alert, set_priority, assign_team, "
                "escalate, send_update, mark_resolved, investigate, correlate_alerts, get_status."
            },
        )

    def step(
        self,
        action: Action,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> Observation:
        """Execute a step in the environment."""
        self._env_state.step_count += 1

        # Check if episode should end (max steps reached)
        if self._env_state.step_count >= self._max_steps:
            self._env_state.done = True

        # Tick SLA timers
        self._tick_sla_timers()

        # Get result from MCP tool handler (reward/done will be None in the returned obs)
        result = super().step(action, timeout_s=timeout_s, **kwargs)

        # Inject our computed reward and done status into the observation
        reward = self._step_rewards[-1] if self._step_rewards else 0.0
        result.reward = reward
        result.done = self._env_state.done
        return result

    async def step_async(
        self,
        action: Action,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> Observation:
        """Async step used by the WebSocket handler."""
        self._env_state.step_count += 1

        if self._env_state.step_count >= self._max_steps:
            self._env_state.done = True

        self._tick_sla_timers()

        # Get result from MCP tool handler (reward/done will be None in the returned obs)
        result = await super().step_async(action, timeout_s=timeout_s, **kwargs)

        # Inject our computed reward and done status into the observation
        reward = self._step_rewards[-1] if self._step_rewards else 0.0
        result.reward = reward
        result.done = self._env_state.done
        return result

    @property
    def state(self) -> State:
        """Get the current environment state."""
        return State(
            episode_id=self._env_state.episode_id,
            step_count=self._env_state.step_count,
        )

    def get_grading_state(self) -> IncidentState:
        """Get the full internal state for grading purposes."""
        return self._env_state

    def get_ground_truth(self):
        """Get the ground truth for the current scenario."""
        return self._ground_truth

    def get_max_steps(self) -> int:
        """Get the max steps for the current scenario."""
        return self._max_steps


def _priority_near(a: str, b: str) -> bool:
    """Check if two priorities are within 1 level."""
    order = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
    return abs(order.get(a, 0) - order.get(b, 0)) <= 1


def _escalation_near(a: str, b: str) -> bool:
    """Check if two escalation levels are within 1 level."""
    order = {"none": 0, "on_call_lead": 1, "vp_eng": 2, "cto": 3}
    return abs(order.get(a, 0) - order.get(b, 0)) <= 1
