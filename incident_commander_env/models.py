"""
Typed Pydantic models for the Incident Commander Environment.

Defines the Action, Observation, and State models used by the environment
for type-safe data exchange between agent and environment.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─── Enums ────────────────────────────────────────────────────────────────────

class Priority(str, Enum):
    """Alert priority levels."""
    P1 = "P1"  # Critical — immediate attention
    P2 = "P2"  # High — urgent
    P3 = "P3"  # Medium — important but not urgent
    P4 = "P4"  # Low — informational


class AlertStatus(str, Enum):
    """Current status of an alert."""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"


class Severity(str, Enum):
    """Raw severity as reported by monitoring system."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class EscalationLevel(str, Enum):
    """Escalation hierarchy."""
    NONE = "none"
    ON_CALL_LEAD = "on_call_lead"
    VP_ENG = "vp_eng"
    CTO = "cto"


class Team(str, Enum):
    """Available engineering teams."""
    PLATFORM = "platform"
    DATABASE = "database"
    NETWORK = "network"
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"


class Channel(str, Enum):
    """Communication channels for status updates."""
    INCIDENT_CHANNEL = "incident_channel"
    STAKEHOLDER_EMAIL = "stakeholder_email"
    STATUS_PAGE = "status_page"


# ─── Sub-models ───────────────────────────────────────────────────────────────

class Alert(BaseModel):
    """A single monitoring alert."""
    alert_id: str = Field(description="Unique alert identifier")
    service: str = Field(description="Service that generated the alert")
    severity: Severity = Field(description="Raw severity from monitoring")
    title: str = Field(description="Short alert title")
    description: str = Field(description="Detailed alert description")
    timestamp: str = Field(description="ISO timestamp when alert fired")
    status: AlertStatus = Field(default=AlertStatus.NEW, description="Current status")
    assigned_priority: Optional[Priority] = Field(default=None, description="Agent-assigned priority")
    assigned_team: Optional[str] = Field(default=None, description="Team the alert was assigned to")
    is_noise: bool = Field(default=False, description="Whether this is a false positive/noise (hidden from agent)")
    correlation_group: Optional[str] = Field(default=None, description="Which incident group this belongs to (hidden)")
    trigger_step: int = Field(default=0, description="Step at which this alert becomes visible (for temporal cascading)")


class TeamInfo(BaseModel):
    """Status of an engineering team."""
    name: str = Field(description="Team name")
    available: bool = Field(default=True, description="Whether team is available")
    current_load: int = Field(default=0, description="Number of alerts currently assigned")
    specialties: List[str] = Field(default_factory=list, description="What services this team handles")


class EscalationState(BaseModel):
    """Current escalation state."""
    current_level: EscalationLevel = Field(default=EscalationLevel.NONE)
    escalation_history: List[str] = Field(default_factory=list, description="History of escalations")


class SLATimer(BaseModel):
    """SLA deadline tracker for an alert."""
    alert_id: str
    priority: Optional[Priority] = None
    steps_remaining: int = Field(description="Steps remaining before SLA breach")
    breached: bool = Field(default=False)


class ServiceMetrics(BaseModel):
    """Time-series performance metrics for a service, returned by get_metrics()."""
    service: str = Field(description="Service name")
    latency_p50_ms: float = Field(description="Median latency in milliseconds")
    latency_p99_ms: float = Field(description="99th percentile latency in milliseconds")
    error_rate_pct: float = Field(description="Current error rate percentage")
    cpu_utilization_pct: float = Field(description="CPU utilization percentage")
    memory_utilization_pct: float = Field(description="Memory utilization percentage")
    request_rate_rpm: float = Field(description="Requests per minute")
    saturation_pct: Optional[float] = Field(default=None, description="Resource saturation (e.g., connection pool usage)")
    status_summary: str = Field(default="healthy", description="Human-readable status")
    trend: str = Field(default="stable", description="Trend direction: improving, stable, degrading, critical")


try:
    from openenv.core.env_server.types import Observation
except ImportError:
    # Use fallback base class if openenv is not installed (e.g. during local tests)
    from pydantic import BaseModel as Observation

class IncidentObservation(Observation):
    """What the agent observes each step.

    Contains all visible state: active alerts, team status, escalation state,
    SLA timers, and action history.
    """
    alerts: List[Alert] = Field(default_factory=list, description="Currently active alerts")
    teams: List[TeamInfo] = Field(default_factory=list, description="Available teams and their status")
    escalation_state: EscalationState = Field(default_factory=EscalationState)
    sla_timers: List[SLATimer] = Field(default_factory=list, description="SLA countdown per alert")
    action_log: List[str] = Field(default_factory=list, description="Log of actions taken this episode")
    system_status: str = Field(default="normal", description="Overall system health summary")
    step_number: int = Field(default=0)
    max_steps: int = Field(default=10)
    task_name: str = Field(default="")
    last_action_result: str = Field(default="", description="Result message from last action")
    last_action_error: Optional[str] = Field(default=None, description="Error from last action if any")
    investigation_results: Dict[str, str] = Field(default_factory=dict, description="Results from investigate actions")
    new_alerts_this_step: int = Field(default=0, description="Number of new alerts that appeared this step (cascading)")


# ─── Ground truth (for grading — not shown to agent) ─────────────────────────

class AlertGroundTruth(BaseModel):
    """The correct handling for a single alert."""
    alert_id: str
    correct_priority: Priority
    correct_team: Team
    correlation_group: str = Field(description="Which alerts are related")
    is_noise: bool = Field(default=False, description="If True, should NOT be escalated")
    is_root_cause: bool = Field(default=False, description="If True, this is the root cause alert")


class ScenarioGroundTruth(BaseModel):
    """Complete ground truth for a scenario."""
    task_name: str
    alert_truths: List[AlertGroundTruth]
    required_escalation_level: EscalationLevel
    required_status_updates: int = Field(description="Min status updates expected")
    correlation_groups: Dict[str, List[str]] = Field(
        description="Group name -> list of alert IDs that belong together"
    )
    min_steps_possible: int = Field(description="Minimum steps to complete perfectly")


# ─── Postmortem ──────────────────────────────────────────────────────────────

class PostmortemData(BaseModel):
    """Agent-written postmortem for the incident."""
    root_cause_alert_id: str = Field(description="Alert ID the agent identified as root cause")
    incident_severity: str = Field(description="Agent-assessed severity: low, medium, high, critical")
    resolution_summary: str = Field(description="Brief summary of what was done to resolve")


# ─── Internal State ──────────────────────────────────────────────────────────

class IncidentState(BaseModel):
    """Full internal state of the environment (used for state() endpoint)."""
    episode_id: str = Field(default="")
    step_count: int = Field(default=0)
    task_name: str = Field(default="")
    done: bool = Field(default=False)
    total_reward: float = Field(default=0.0)
    alerts: List[Alert] = Field(default_factory=list)
    escalation_state: EscalationState = Field(default_factory=EscalationState)
    action_log: List[str] = Field(default_factory=list)
    correlated_groups: Dict[str, List[str]] = Field(default_factory=dict)
    updates_sent: int = Field(default=0)
    investigation_results: Dict[str, str] = Field(
        default_factory=dict,
        description="Results from investigate() calls — alert_id -> findings"
    )
    postmortem: Optional[PostmortemData] = Field(
        default=None,
        description="Agent-written postmortem, if submitted via write_postmortem()"
    )
