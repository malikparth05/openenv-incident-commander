"""
Task Scenarios for the Incident Commander Environment.

Defines 3 scenarios (Easy → Medium → Hard) with complete alert data
and ground truth solutions for deterministic grading.
"""

from typing import Dict, List, Tuple

try:
    from .models import (
        Alert,
        AlertGroundTruth,
        AlertStatus,
        Channel,
        EscalationLevel,
        Priority,
        ScenarioGroundTruth,
        Severity,
        SLATimer,
        Team,
        TeamInfo,
    )
except ImportError:
    from models import (
        Alert,
        AlertGroundTruth,
        AlertStatus,
        Channel,
        EscalationLevel,
        Priority,
        ScenarioGroundTruth,
        Severity,
        SLATimer,
        Team,
        TeamInfo,
    )


# ─── Available Teams (shared across all scenarios) ────────────────────────────

def get_teams() -> List[TeamInfo]:
    """Return the standard set of engineering teams."""
    return [
        TeamInfo(
            name="platform",
            available=True,
            current_load=0,
            specialties=["api_gateway", "load_balancer", "cdn", "reverse_proxy"],
        ),
        TeamInfo(
            name="database",
            available=True,
            current_load=0,
            specialties=["postgresql", "mysql", "redis", "connection_pool", "replication"],
        ),
        TeamInfo(
            name="network",
            available=True,
            current_load=0,
            specialties=["dns", "vpn", "firewall", "switch", "router", "network_partition"],
        ),
        TeamInfo(
            name="application",
            available=True,
            current_load=0,
            specialties=["backend", "frontend", "microservice", "api", "deployment"],
        ),
        TeamInfo(
            name="infrastructure",
            available=True,
            current_load=0,
            specialties=["kubernetes", "docker", "vm", "cloud", "storage", "compute"],
        ),
        TeamInfo(
            name="security",
            available=True,
            current_load=0,
            specialties=["auth", "ssl", "certificates", "firewall_rules", "access_control"],
        ),
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TASK 1 — EASY: Single Service Outage
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK1_ALERTS = [
    Alert(
        alert_id="alert-001",
        service="api_gateway",
        severity=Severity.CRITICAL,
        title="API Gateway Health Check Failure",
        description="Health check endpoint /healthz returning 503 for the past 3 minutes. "
                    "All upstream services are timing out through the gateway.",
        timestamp="2025-01-15T14:30:00Z",
        status=AlertStatus.NEW,
    ),
    Alert(
        alert_id="alert-002",
        service="api_gateway",
        severity=Severity.CRITICAL,
        title="5xx Error Rate Spike — API Gateway",
        description="HTTP 502/503 error rate has spiked to 78% on the API gateway. "
                    "Normal baseline is <0.1%. Affecting all routes.",
        timestamp="2025-01-15T14:30:45Z",
        status=AlertStatus.NEW,
    ),
    Alert(
        alert_id="alert-003",
        service="api_gateway",
        severity=Severity.WARNING,
        title="API Gateway Latency P99 > 10s",
        description="99th percentile latency on API gateway has exceeded 10 seconds. "
                    "Normal P99 is ~200ms. Likely correlated with the health check failures.",
        timestamp="2025-01-15T14:31:10Z",
        status=AlertStatus.NEW,
    ),
]

TASK1_GROUND_TRUTH = ScenarioGroundTruth(
    task_name="single_service_outage",
    alert_truths=[
        AlertGroundTruth(
            alert_id="alert-001",
            correct_priority=Priority.P1,
            correct_team=Team.PLATFORM,
            correlation_group="api_gateway_outage",
            is_root_cause=True,
        ),
        AlertGroundTruth(
            alert_id="alert-002",
            correct_priority=Priority.P1,
            correct_team=Team.PLATFORM,
            correlation_group="api_gateway_outage",
        ),
        AlertGroundTruth(
            alert_id="alert-003",
            correct_priority=Priority.P2,
            correct_team=Team.PLATFORM,
            correlation_group="api_gateway_outage",
        ),
    ],
    required_escalation_level=EscalationLevel.ON_CALL_LEAD,
    required_status_updates=1,
    correlation_groups={
        "api_gateway_outage": ["alert-001", "alert-002", "alert-003"],
    },
    min_steps_possible=6,  # ack x3 + set_priority x3 + assign x3 + correlate + escalate + update = ~6 condensed
)

TASK1_SLA_TIMERS = [
    SLATimer(alert_id="alert-001", steps_remaining=8, breached=False),
    SLATimer(alert_id="alert-002", steps_remaining=8, breached=False),
    SLATimer(alert_id="alert-003", steps_remaining=12, breached=False),
]

TASK1_INVESTIGATION_DATA = {
    "alert-001": "Investigation: API Gateway pods are in CrashLoopBackOff state. Last restart was 3 minutes ago. "
                 "Container logs show: 'FATAL: unable to bind to port 8080 — address already in use'. "
                 "Root cause appears to be a port conflict after the latest deployment (v2.4.1).",
    "alert-002": "Investigation: 5xx errors began exactly when alert-001 fired. Error breakdown: "
                 "82% are HTTP 503 (service unavailable), 18% are HTTP 502 (bad gateway). "
                 "All errors trace back to the gateway's inability to establish upstream connections.",
    "alert-003": "Investigation: Latency spike is a downstream effect of the health check failures. "
                 "Requests that do get through are being load-balanced to the single remaining healthy pod, "
                 "causing resource contention. This is a symptom, not a separate issue.",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TASK 2 — MEDIUM: Multi-Service Degradation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK2_ALERTS = [
    # Root cause: DB connection pool exhaustion
    Alert(
        alert_id="alert-101",
        service="postgresql",
        severity=Severity.CRITICAL,
        title="PostgreSQL Connection Pool Exhausted",
        description="Connection pool is at 100% capacity (500/500 connections). "
                    "New connection requests are being rejected. Active queries show "
                    "multiple long-running transactions holding connections.",
        timestamp="2025-01-15T09:00:00Z",
        status=AlertStatus.NEW,
    ),
    Alert(
        alert_id="alert-102",
        service="postgresql",
        severity=Severity.WARNING,
        title="PostgreSQL Replication Lag Increasing",
        description="Replication lag between primary and read replicas has increased to 45 seconds. "
                    "Normal lag is <1 second. May cause stale reads from replicas.",
        timestamp="2025-01-15T09:01:30Z",
        status=AlertStatus.NEW,
    ),
    # Symptom: App server timeouts due to DB
    Alert(
        alert_id="alert-103",
        service="user_service",
        severity=Severity.CRITICAL,
        title="User Service — Database Timeout Errors",
        description="User service is experiencing database connection timeouts. "
                    "95% of requests to /api/users/* are failing with timeout errors. "
                    "Connection pool on app side shows 0 available connections.",
        timestamp="2025-01-15T09:02:00Z",
        status=AlertStatus.NEW,
    ),
    Alert(
        alert_id="alert-104",
        service="order_service",
        severity=Severity.CRITICAL,
        title="Order Service — Transaction Failures",
        description="Order processing is failing due to inability to acquire database connections. "
                    "Order creation success rate has dropped to 5%. Revenue impact estimated.",
        timestamp="2025-01-15T09:02:30Z",
        status=AlertStatus.NEW,
    ),
    # Symptom: Cache misses spike because app falls back to DB
    Alert(
        alert_id="alert-105",
        service="redis",
        severity=Severity.WARNING,
        title="Redis Cache Miss Rate Spike",
        description="Cache miss rate has increased from 5% to 65%. Applications are falling through "
                    "to database queries, which is amplifying the DB connection pool problem.",
        timestamp="2025-01-15T09:03:00Z",
        status=AlertStatus.NEW,
    ),
    # Symptom: Frontend errors
    Alert(
        alert_id="alert-106",
        service="frontend",
        severity=Severity.WARNING,
        title="Frontend — Elevated Error Rate",
        description="Frontend is showing elevated error rates. Users are seeing 'Service Unavailable' "
                    "messages. Error rate is 40% (normal <0.5%).",
        timestamp="2025-01-15T09:03:30Z",
        status=AlertStatus.NEW,
    ),
    # Related but less critical
    Alert(
        alert_id="alert-107",
        service="search_service",
        severity=Severity.WARNING,
        title="Search Service — Degraded Performance",
        description="Search queries are taking 8-15 seconds instead of normal 200ms. "
                    "Search relies on PostgreSQL for indexing metadata.",
        timestamp="2025-01-15T09:04:00Z",
        status=AlertStatus.NEW,
    ),
    Alert(
        alert_id="alert-108",
        service="notification_service",
        severity=Severity.INFO,
        title="Notification Queue Backlog Growing",
        description="Email/SMS notification queue depth has grown to 15,000 messages. "
                    "Normal depth is <100. Notifications are being delayed but not lost.",
        timestamp="2025-01-15T09:05:00Z",
        status=AlertStatus.NEW,
    ),
]

TASK2_GROUND_TRUTH = ScenarioGroundTruth(
    task_name="multi_service_degradation",
    alert_truths=[
        AlertGroundTruth(
            alert_id="alert-101",
            correct_priority=Priority.P1,
            correct_team=Team.DATABASE,
            correlation_group="db_connection_crisis",
            is_root_cause=True,
        ),
        AlertGroundTruth(
            alert_id="alert-102",
            correct_priority=Priority.P2,
            correct_team=Team.DATABASE,
            correlation_group="db_connection_crisis",
        ),
        AlertGroundTruth(
            alert_id="alert-103",
            correct_priority=Priority.P2,
            correct_team=Team.APPLICATION,
            correlation_group="db_connection_crisis",
        ),
        AlertGroundTruth(
            alert_id="alert-104",
            correct_priority=Priority.P1,
            correct_team=Team.APPLICATION,
            correlation_group="db_connection_crisis",
        ),
        AlertGroundTruth(
            alert_id="alert-105",
            correct_priority=Priority.P3,
            correct_team=Team.DATABASE,
            correlation_group="db_connection_crisis",
        ),
        AlertGroundTruth(
            alert_id="alert-106",
            correct_priority=Priority.P3,
            correct_team=Team.APPLICATION,
            correlation_group="db_connection_crisis",
        ),
        AlertGroundTruth(
            alert_id="alert-107",
            correct_priority=Priority.P3,
            correct_team=Team.APPLICATION,
            correlation_group="db_connection_crisis",
        ),
        AlertGroundTruth(
            alert_id="alert-108",
            correct_priority=Priority.P4,
            correct_team=Team.APPLICATION,
            correlation_group="db_connection_crisis",
        ),
    ],
    required_escalation_level=EscalationLevel.ON_CALL_LEAD,
    required_status_updates=2,
    correlation_groups={
        "db_connection_crisis": [
            "alert-101", "alert-102", "alert-103", "alert-104",
            "alert-105", "alert-106", "alert-107", "alert-108",
        ],
    },
    min_steps_possible=12,
)

TASK2_SLA_TIMERS = [
    SLATimer(alert_id="alert-101", steps_remaining=10, breached=False),
    SLATimer(alert_id="alert-102", steps_remaining=15, breached=False),
    SLATimer(alert_id="alert-103", steps_remaining=10, breached=False),
    SLATimer(alert_id="alert-104", steps_remaining=8, breached=False),
    SLATimer(alert_id="alert-105", steps_remaining=18, breached=False),
    SLATimer(alert_id="alert-106", steps_remaining=15, breached=False),
    SLATimer(alert_id="alert-107", steps_remaining=18, breached=False),
    SLATimer(alert_id="alert-108", steps_remaining=25, breached=False),
]

TASK2_INVESTIGATION_DATA = {
    "alert-101": "Investigation: PostgreSQL connection pool analysis shows 487 of 500 connections are held by "
                 "long-running analytical queries from a batch job that started at 08:55. The batch job is "
                 "'reports_daily_aggregate' which normally completes in 2 minutes but is now stuck in a deadlock. "
                 "This is the ROOT CAUSE of all downstream failures.",
    "alert-102": "Investigation: Replication lag is caused by the primary being overwhelmed with connection requests. "
                 "WAL shipping is delayed because the primary can't process writes efficiently. "
                 "This will self-resolve once connection pool pressure is relieved.",
    "alert-103": "Investigation: User service logs show 'ConnectionPoolExhausted' exceptions. Services are configured "
                 "with a 5-second connection timeout. Once DB connections are available again, this will recover.",
    "alert-104": "Investigation: Order service transactions are failing at the DB connection acquisition step. "
                 "No data corruption detected — orders are simply not being created. Will auto-recover with DB fix.",
    "alert-105": "Investigation: Cache miss spike is because cache invalidation is happening normally but cache "
                 "refill is failing (refill queries to DB are timing out). Existing cached data is still being served.",
    "alert-106": "Investigation: Frontend errors are all from failed API calls to user_service and order_service. "
                 "Frontend itself is healthy — it's just displaying error responses from backend.",
    "alert-107": "Investigation: Search indexer relies on PostgreSQL for metadata lookups. With DB connections "
                 "unavailable, search is falling back to stale index data and timing out on new queries.",
    "alert-108": "Investigation: Notification service queues messages in Redis and processes via worker. "
                 "Workers can't complete notifications that require DB lookups (e.g., user preferences). "
                 "Messages are safe in queue and will process once DB recovers.",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TASK 3 — HARD: Cascading Infrastructure Failure
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK3_ALERTS = [
    # ── Incident A: Network Partition (ROOT CAUSE of most issues) ──
    Alert(
        alert_id="alert-201",
        service="network_switch",
        severity=Severity.CRITICAL,
        title="Core Switch Fabric — Partial Failure",
        description="Core switch sw-core-02 in rack B is reporting partial fabric failure. "
                    "Links to racks C, D, E are flapping. BGP sessions are being torn down.",
        timestamp="2025-01-15T03:00:00Z",
        status=AlertStatus.NEW,
    ),
    Alert(
        alert_id="alert-202",
        service="dns",
        severity=Severity.CRITICAL,
        title="Internal DNS Resolution Failures",
        description="Internal DNS queries are failing intermittently. Resolution rate has dropped "
                    "to 40%. Services using DNS-based service discovery are affected. "
                    "Affects services in racks C, D, E only.",
        timestamp="2025-01-15T03:00:30Z",
        status=AlertStatus.NEW,
    ),
    Alert(
        alert_id="alert-203",
        service="kubernetes",
        severity=Severity.CRITICAL,
        title="Kubernetes Node NotReady — Multiple Nodes",
        description="8 out of 24 Kubernetes nodes are in NotReady state. Affected nodes are in racks C and D. "
                    "Pods are being evicted and rescheduled, causing service disruptions.",
        timestamp="2025-01-15T03:01:00Z",
        status=AlertStatus.NEW,
    ),
    # ── Symptoms of Incident A ──
    Alert(
        alert_id="alert-204",
        service="payment_service",
        severity=Severity.CRITICAL,
        title="Payment Processing — Complete Failure",
        description="Payment service is unable to reach payment gateway API. All payment "
                    "transactions are failing. Revenue impact: ~$50K/hour.",
        timestamp="2025-01-15T03:01:30Z",
        status=AlertStatus.NEW,
    ),
    Alert(
        alert_id="alert-205",
        service="auth_service",
        severity=Severity.CRITICAL,
        title="Authentication Service — Intermittent Failures",
        description="Auth service pods on racks C/D cannot reach the identity provider. "
                    "50% of login attempts are failing. Pods on racks A/B are fine.",
        timestamp="2025-01-15T03:02:00Z",
        status=AlertStatus.NEW,
    ),
    Alert(
        alert_id="alert-206",
        service="message_queue",
        severity=Severity.WARNING,
        title="RabbitMQ Cluster — Split Brain Detected",
        description="RabbitMQ cluster has detected a network partition. Nodes in rack C/D have "
                    "formed a separate cluster from nodes in rack A/B. Messages may be duplicated.",
        timestamp="2025-01-15T03:02:30Z",
        status=AlertStatus.NEW,
    ),
    Alert(
        alert_id="alert-207",
        service="storage",
        severity=Severity.WARNING,
        title="Distributed Storage — Degraded Replication",
        description="Ceph storage cluster replication factor has dropped from 3 to 2. "
                    "Storage nodes in racks C/D are unreachable from racks A/B.",
        timestamp="2025-01-15T03:03:00Z",
        status=AlertStatus.NEW,
    ),
    # ── Incident B: Unrelated — Scheduled Certificate Expiry ──
    Alert(
        alert_id="alert-208",
        service="ssl_certificate",
        severity=Severity.WARNING,
        title="SSL Certificate Expiry Warning — staging.example.com",
        description="SSL certificate for staging.example.com will expire in 7 days. "
                    "This is the staging environment only. Production certificates are valid.",
        timestamp="2025-01-15T03:03:30Z",
        status=AlertStatus.NEW,
        is_noise=True,
    ),
    # ── More symptoms of Incident A ──
    Alert(
        alert_id="alert-209",
        service="monitoring",
        severity=Severity.WARNING,
        title="Prometheus — Scrape Target Failures",
        description="Prometheus is unable to scrape 12 out of 45 targets. All failing targets "
                    "are in racks C, D, E. Monitoring data for these services is incomplete.",
        timestamp="2025-01-15T03:04:00Z",
        status=AlertStatus.NEW,
    ),
    Alert(
        alert_id="alert-210",
        service="api_gateway",
        severity=Severity.CRITICAL,
        title="API Gateway — Upstream Timeout Storm",
        description="API gateway is experiencing massive upstream timeouts. 60% of requests are "
                    "timing out. Affected services are those running on racks C/D/E.",
        timestamp="2025-01-15T03:04:30Z",
        status=AlertStatus.NEW,
    ),
    # ── Noise: Scheduled maintenance alert ──
    Alert(
        alert_id="alert-211",
        service="deployment",
        severity=Severity.INFO,
        title="Scheduled Deployment — analytics-pipeline v3.2.1",
        description="Scheduled deployment of analytics-pipeline v3.2.1 is proceeding as planned. "
                    "This deployment was approved in change management ticket CM-2025-0142.",
        timestamp="2025-01-15T03:05:00Z",
        status=AlertStatus.NEW,
        is_noise=True,
    ),
    # ── More Incident A symptoms ──
    Alert(
        alert_id="alert-212",
        service="database",
        severity=Severity.CRITICAL,
        title="PostgreSQL Replica — Connection Refused",
        description="PostgreSQL read replica pg-replica-03 (rack D) is refusing connections. "
                    "Primary in rack A is still operational. Read traffic is being redirected "
                    "to remaining replicas, causing increased load.",
        timestamp="2025-01-15T03:05:30Z",
        status=AlertStatus.NEW,
    ),
    # ── Noise: Auto-scaling event ──
    Alert(
        alert_id="alert-213",
        service="kubernetes",
        severity=Severity.INFO,
        title="Horizontal Pod Autoscaler — Scale Up Event",
        description="HPA for frontend-web has triggered a scale-up from 6 to 10 pods due to "
                    "increased CPU utilization. This is normal auto-scaling behavior.",
        timestamp="2025-01-15T03:06:00Z",
        status=AlertStatus.NEW,
        is_noise=True,
    ),
    Alert(
        alert_id="alert-214",
        service="cdn",
        severity=Severity.WARNING,
        title="CDN Origin Fetch Failures",
        description="CDN is reporting increased origin fetch failures. Cache hit ratio has dropped "
                    "from 95% to 60%. Origin servers in affected racks are not responding.",
        timestamp="2025-01-15T03:06:30Z",
        status=AlertStatus.NEW,
    ),
    Alert(
        alert_id="alert-215",
        service="logging",
        severity=Severity.INFO,
        title="Log Ingestion Pipeline — Backpressure Warning",
        description="Elasticsearch log ingestion pipeline is experiencing backpressure. "
                    "Log delivery latency has increased to 5 minutes. No data loss, "
                    "logs are buffered in Kafka.",
        timestamp="2025-01-15T03:07:00Z",
        status=AlertStatus.NEW,
    ),
]

TASK3_GROUND_TRUTH = ScenarioGroundTruth(
    task_name="cascading_infrastructure_failure",
    alert_truths=[
        # ── Network partition (root cause cluster) ──
        AlertGroundTruth(
            alert_id="alert-201",
            correct_priority=Priority.P1,
            correct_team=Team.NETWORK,
            correlation_group="network_partition",
            is_root_cause=True,
        ),
        AlertGroundTruth(
            alert_id="alert-202",
            correct_priority=Priority.P1,
            correct_team=Team.NETWORK,
            correlation_group="network_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-203",
            correct_priority=Priority.P1,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="network_partition",
        ),
        # ── Downstream symptoms ──
        AlertGroundTruth(
            alert_id="alert-204",
            correct_priority=Priority.P1,
            correct_team=Team.APPLICATION,
            correlation_group="network_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-205",
            correct_priority=Priority.P1,
            correct_team=Team.SECURITY,
            correlation_group="network_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-206",
            correct_priority=Priority.P2,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="network_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-207",
            correct_priority=Priority.P2,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="network_partition",
        ),
        # ── Noise: certificate expiry (should be low-priority, NOT escalated) ──
        AlertGroundTruth(
            alert_id="alert-208",
            correct_priority=Priority.P4,
            correct_team=Team.SECURITY,
            correlation_group="noise_cert",
            is_noise=True,
        ),
        # ── More symptoms ──
        AlertGroundTruth(
            alert_id="alert-209",
            correct_priority=Priority.P3,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="network_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-210",
            correct_priority=Priority.P1,
            correct_team=Team.PLATFORM,
            correlation_group="network_partition",
        ),
        # ── Noise: scheduled deployment ──
        AlertGroundTruth(
            alert_id="alert-211",
            correct_priority=Priority.P4,
            correct_team=Team.APPLICATION,
            correlation_group="noise_deployment",
            is_noise=True,
        ),
        AlertGroundTruth(
            alert_id="alert-212",
            correct_priority=Priority.P2,
            correct_team=Team.DATABASE,
            correlation_group="network_partition",
        ),
        # ── Noise: auto-scaling ──
        AlertGroundTruth(
            alert_id="alert-213",
            correct_priority=Priority.P4,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="noise_autoscale",
            is_noise=True,
        ),
        AlertGroundTruth(
            alert_id="alert-214",
            correct_priority=Priority.P2,
            correct_team=Team.PLATFORM,
            correlation_group="network_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-215",
            correct_priority=Priority.P3,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="network_partition",
        ),
    ],
    required_escalation_level=EscalationLevel.VP_ENG,
    required_status_updates=3,
    correlation_groups={
        "network_partition": [
            "alert-201", "alert-202", "alert-203", "alert-204", "alert-205",
            "alert-206", "alert-207", "alert-209", "alert-210", "alert-212",
            "alert-214", "alert-215",
        ],
        "noise_cert": ["alert-208"],
        "noise_deployment": ["alert-211"],
        "noise_autoscale": ["alert-213"],
    },
    min_steps_possible=20,
)

TASK3_SLA_TIMERS = [
    SLATimer(alert_id="alert-201", steps_remaining=12, breached=False),
    SLATimer(alert_id="alert-202", steps_remaining=12, breached=False),
    SLATimer(alert_id="alert-203", steps_remaining=12, breached=False),
    SLATimer(alert_id="alert-204", steps_remaining=8, breached=False),
    SLATimer(alert_id="alert-205", steps_remaining=10, breached=False),
    SLATimer(alert_id="alert-206", steps_remaining=18, breached=False),
    SLATimer(alert_id="alert-207", steps_remaining=18, breached=False),
    SLATimer(alert_id="alert-208", steps_remaining=50, breached=False),
    SLATimer(alert_id="alert-209", steps_remaining=20, breached=False),
    SLATimer(alert_id="alert-210", steps_remaining=10, breached=False),
    SLATimer(alert_id="alert-211", steps_remaining=50, breached=False),
    SLATimer(alert_id="alert-212", steps_remaining=14, breached=False),
    SLATimer(alert_id="alert-213", steps_remaining=50, breached=False),
    SLATimer(alert_id="alert-214", steps_remaining=16, breached=False),
    SLATimer(alert_id="alert-215", steps_remaining=25, breached=False),
]

TASK3_INVESTIGATION_DATA = {
    "alert-201": "Investigation: Core switch sw-core-02 ASIC shows partial fabric failure. "
                 "Ports 25-48 are down, affecting uplinks to racks C, D, E. Hardware fault suspected. "
                 "Switch is a Juniper QFX5200. Vendor RMA process should be initiated. "
                 "This is the ROOT CAUSE of the cascading failure across all affected racks.",
    "alert-202": "Investigation: DNS failures are because 2 of 3 internal DNS resolvers are in rack C. "
                 "Only the resolver in rack A is reachable. DNS resolution works for services in racks A/B "
                 "but fails for cross-rack lookups involving racks C/D/E.",
    "alert-203": "Investigation: Kubernetes control plane is in rack A (healthy). Worker nodes in racks C/D "
                 "have lost heartbeat connectivity to the API server. kubelet cannot reach kube-apiserver "
                 "through the failed switch fabric. Pods are being evicted per NoExecute taint policy.",
    "alert-204": "Investigation: Payment service instances in rack D cannot reach the payment gateway "
                 "through the network partition. Instances in rack A are fine but overwhelmed. "
                 "Consider rerouting all payment traffic to rack A instances temporarily.",
    "alert-205": "Investigation: Auth service depends on LDAP/identity provider in rack C. Instances in "
                 "racks A/B can't reach it through the partitioned network. 50% failure rate correlates "
                 "with 50% of traffic hitting rack A/B instances that can't reach the IdP.",
    "alert-206": "Investigation: RabbitMQ uses Erlang distribution protocol for cluster communication. "
                 "Nodes in racks C/D have formed their own cluster. Both sides think they are authoritative. "
                 "This requires manual intervention to resolve the split-brain once network is restored.",
    "alert-207": "Investigation: Ceph OSDs in racks C/D are marked DOWN by the monitors in rack A. "
                 "Replication factor drop from 3→2 means data is still safe but less resilient. "
                 "No data loss as long as rack A storage remains operational.",
    "alert-208": "Investigation: This is a routine certificate expiry warning for the STAGING environment. "
                 "Certificate for staging.example.com expires in 7 days. No production impact. "
                 "This is NOT related to the current incident.",
    "alert-209": "Investigation: Prometheus in rack A cannot reach exporters in racks C/D/E through the "
                 "partitioned network. Monitoring gaps are a symptom of the network issue, not a separate problem.",
    "alert-210": "Investigation: API gateway is load-balancing across all upstream pods, including those in "
                 "unreachable racks. Timeout rate = (pods in C/D/E) / (total pods). Need to update routing "
                 "to exclude unreachable backends.",
    "alert-211": "Investigation: This is a scheduled, approved deployment. Change management ticket CM-2025-0142 "
                 "was approved in last week's CAB meeting. Deployment is running in rack A, unaffected by "
                 "the network partition. This is NOT related to the current incident.",
    "alert-212": "Investigation: PostgreSQL replica pg-replica-03 is in rack D, which is partitioned from rack A "
                 "where the primary runs. The replica has lost streaming replication. "
                 "It will recover automatically once network connectivity is restored.",
    "alert-213": "Investigation: HPA scale-up is a normal response to increased per-pod CPU usage. "
                 "With fewer pods available (some evicted from affected racks), remaining pods are handling "
                 "more traffic. This is the autoscaler working correctly. NOT a separate issue.",
    "alert-214": "Investigation: CDN cannot reach origin servers in racks C/D/E for cache misses. "
                 "Serving stale content where possible (cache TTL not yet expired). "
                 "Images and static assets still largely cached, but API-driven content is failing.",
    "alert-215": "Investigation: Log ingestion Elasticsearch nodes in rack C are unreachable. "
                 "Kafka is buffering logs safely. Once network recovers, logs will be ingested "
                 "with a delay but no data loss. Low priority — monitoring gap, not data loss.",
}


# ─── Scenario Registry ───────────────────────────────────────────────────────

SCENARIOS = {
    "single_service_outage": {
        "alerts": TASK1_ALERTS,
        "ground_truth": TASK1_GROUND_TRUTH,
        "sla_timers": TASK1_SLA_TIMERS,
        "investigation_data": TASK1_INVESTIGATION_DATA,
        "max_steps": 10,
        "description": "Easy: A single API gateway outage with 3 related alerts. "
                      "Correctly triage, prioritize, and route to the platform team.",
    },
    "multi_service_degradation": {
        "alerts": TASK2_ALERTS,
        "ground_truth": TASK2_GROUND_TRUTH,
        "sla_timers": TASK2_SLA_TIMERS,
        "investigation_data": TASK2_INVESTIGATION_DATA,
        "max_steps": 20,
        "description": "Medium: Database connection pool exhaustion causing cascading failures "
                      "across 5 services. Identify root cause, correlate alerts, escalate.",
    },
    "cascading_infrastructure_failure": {
        "alerts": TASK3_ALERTS,
        "ground_truth": TASK3_GROUND_TRUTH,
        "sla_timers": TASK3_SLA_TIMERS,
        "investigation_data": TASK3_INVESTIGATION_DATA,
        "max_steps": 30,
        "description": "Hard: Network switch failure causing cascading failures across 6+ services. "
                      "Includes 3 noise/false-positive alerts. Filter noise, correlate 12 real alerts.",
    },
}


def get_scenario(task_name: str) -> dict:
    """Get a scenario by name. Returns a copy to avoid mutation."""
    if task_name not in SCENARIOS:
        raise ValueError(
            f"Unknown task: {task_name!r}. Available tasks: {list(SCENARIOS.keys())}"
        )
    scenario = SCENARIOS[task_name]
    # Deep-copy alerts to avoid mutating the originals
    import copy
    return {
        "alerts": copy.deepcopy(scenario["alerts"]),
        "ground_truth": scenario["ground_truth"],  # immutable reference OK
        "sla_timers": copy.deepcopy(scenario["sla_timers"]),
        "investigation_data": scenario["investigation_data"],  # read-only dict OK
        "max_steps": scenario["max_steps"],
        "description": scenario["description"],
    }


def list_tasks() -> List[str]:
    """List all available task names."""
    return list(SCENARIOS.keys())
