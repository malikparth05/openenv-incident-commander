"""
Task Scenarios for the Incident Commander Environment.

Based on real-world infrastructure incidents:
- Task 1: GitHub 2018 Database Failover (Easy)
- Task 2: Fastly 2021 CDN Configuration Defect (Medium)
- Task 3: AWS-style Network Partition / EBS Event (Hard)
- Task 4: SolarWinds-pattern Supply Chain Attack (Expert)

Each scenario includes complete alert data, ground truth solutions,
temporal cascading (trigger_step), investigation data, and optional
metrics overrides for deterministic grading.
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
            specialties=["api_gateway", "load_balancer", "cdn", "reverse_proxy", "edge_cache"],
        ),
        TeamInfo(
            name="database",
            available=True,
            current_load=0,
            specialties=["postgresql", "mysql", "redis", "connection_pool", "replication", "failover"],
        ),
        TeamInfo(
            name="network",
            available=True,
            current_load=0,
            specialties=["dns", "vpn", "firewall", "switch", "router", "network_partition", "bgp"],
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
            specialties=["kubernetes", "docker", "vm", "cloud", "storage", "compute", "ebs"],
        ),
        TeamInfo(
            name="security",
            available=True,
            current_load=0,
            specialties=["auth", "ssl", "certificates", "firewall_rules", "access_control", "siem", "ids"],
        ),
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TASK 1 — EASY: GitHub 2018 Database Failover
#
# Based on: GitHub's October 21, 2018 outage.
# A 43-second network interruption during routine maintenance triggered
# an unintended MySQL failover. Orchestrator promoted West Coast replicas,
# causing data divergence between East and West Coast clusters.
#
# Learning objective: Identify that the root cause is the network blip,
# not the database per se. Correctly prioritize data integrity over speed.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK1_ALERTS = [
    # T=0: Initial network interruption (ROOT CAUSE)
    Alert(
        alert_id="alert-001",
        service="network_interconnect",
        severity=Severity.CRITICAL,
        title="East↔West DC Interconnect — 43-second Loss of Connectivity",
        description="Routine 100G optical equipment replacement in US-East hub caused a 43-second "
                    "loss of connectivity between US-East and US-West data centers. "
                    "All cross-DC traffic was interrupted. BGP sessions were torn down.",
        timestamp="2025-01-15T22:52:00Z",
        status=AlertStatus.NEW,
        trigger_step=0,
    ),
    # T=0: Orchestrator auto-failover (immediate consequence)
    Alert(
        alert_id="alert-002",
        service="mysql_orchestrator",
        severity=Severity.CRITICAL,
        title="MySQL Orchestrator — Unintended Primary Failover to US-West",
        description="Database orchestrator detected US-East primary as unreachable after 43s timeout. "
                    "Promoted US-West read replica to primary for 23 MySQL clusters. "
                    "US-East primary had uncommitted writes during the 43-second window.",
        timestamp="2025-01-15T22:54:00Z",
        status=AlertStatus.NEW,
        trigger_step=0,
    ),
    # T=1: Data divergence detected (cascading)
    Alert(
        alert_id="alert-003",
        service="mysql_replication",
        severity=Severity.CRITICAL,
        title="MySQL Replication — Data Divergence Across 23 Clusters",
        description="CRITICAL: US-East and US-West MySQL clusters have diverged. "
                    "East had ~40 seconds of uncommitted writes not replicated to West. "
                    "Estimated divergent rows: 15,000+. Data integrity at risk.",
        timestamp="2025-01-15T22:56:00Z",
        status=AlertStatus.NEW,
        trigger_step=1,
    ),
    # T=2: User-facing impact
    Alert(
        alert_id="alert-004",
        service="github_web",
        severity=Severity.WARNING,
        title="GitHub.com — Users Seeing Stale Data and 500 Errors",
        description="Users reporting outdated repository data, missing recent commits, "
                    "and intermittent 500 errors on github.com. Webhook deliveries are "
                    "failing. GitHub Pages builds are stalled.",
        timestamp="2025-01-15T23:00:00Z",
        status=AlertStatus.NEW,
        trigger_step=2,
    ),
]

TASK1_GROUND_TRUTH = ScenarioGroundTruth(
    task_name="github_database_failover",
    alert_truths=[
        AlertGroundTruth(
            alert_id="alert-001",
            correct_priority=Priority.P1,
            correct_team=Team.NETWORK,
            correlation_group="dc_failover_incident",
            is_root_cause=True,
        ),
        AlertGroundTruth(
            alert_id="alert-002",
            correct_priority=Priority.P1,
            correct_team=Team.DATABASE,
            correlation_group="dc_failover_incident",
        ),
        AlertGroundTruth(
            alert_id="alert-003",
            correct_priority=Priority.P1,
            correct_team=Team.DATABASE,
            correlation_group="dc_failover_incident",
        ),
        AlertGroundTruth(
            alert_id="alert-004",
            correct_priority=Priority.P2,
            correct_team=Team.APPLICATION,
            correlation_group="dc_failover_incident",
        ),
    ],
    required_escalation_level=EscalationLevel.ON_CALL_LEAD,
    required_status_updates=1,
    correlation_groups={
        "dc_failover_incident": ["alert-001", "alert-002", "alert-003", "alert-004"],
    },
    min_steps_possible=10,
)

TASK1_SLA_TIMERS = [
    SLATimer(alert_id="alert-001", steps_remaining=8, breached=False),
    SLATimer(alert_id="alert-002", steps_remaining=8, breached=False),
    SLATimer(alert_id="alert-003", steps_remaining=10, breached=False),
    SLATimer(alert_id="alert-004", steps_remaining=12, breached=False),
]

TASK1_INVESTIGATION_DATA = {
    "alert-001": (
        "Investigation: Routine hardware maintenance replaced a failing 100G optical transceiver "
        "on the US-East↔US-West DC interconnect link at 22:52Z. During the swap, connectivity "
        "was lost for exactly 43 seconds. All BGP sessions between DCs were torn down and "
        "re-established. This is the ROOT CAUSE — it triggered Orchestrator's failover logic."
    ),
    "alert-002": (
        "Investigation: MySQL Orchestrator uses a 30-second timeout to detect primary failure. "
        "The 43-second network interruption exceeded this threshold, causing Orchestrator to "
        "conclude the US-East primary was dead. It promoted the US-West replica to primary. "
        "The original East primary was actually healthy — it just couldn't reach West."
    ),
    "alert-003": (
        "Investigation: Data divergence analysis shows ~15,000 rows across 23 clusters were "
        "written to East primary during the 43-second window but never replicated to West. "
        "West primary has since accepted new writes. Both clusters have valid but conflicting "
        "data. Resolution requires careful row-by-row reconciliation to avoid data loss."
    ),
    "alert-004": (
        "Investigation: User-facing errors are caused by the application layer reading from "
        "both old East and new West primaries inconsistently. Some requests hit stale data, "
        "others hit the new primary. This will persist until data reconciliation is complete. "
        "Webhooks and Pages builds are queued and will replay once DB is consistent."
    ),
}

TASK1_METRICS_DATA = {
    "network_interconnect": {
        "latency_p50_ms": 9999.0,
        "latency_p99_ms": 9999.0,
        "error_rate_pct": 100.0,
        "cpu_utilization_pct": 5.0,
        "memory_utilization_pct": 10.0,
        "request_rate_rpm": 0.0,
        "saturation_pct": None,
        "status_summary": "TOTAL FAILURE — link down for 43s, now recovered but failover already triggered",
        "trend": "improving",
    },
    "mysql_orchestrator": {
        "latency_p50_ms": 15.0,
        "latency_p99_ms": 45.0,
        "error_rate_pct": 0.0,
        "cpu_utilization_pct": 35.0,
        "memory_utilization_pct": 40.0,
        "request_rate_rpm": 500.0,
        "saturation_pct": None,
        "status_summary": "ALERT — Orchestrator executed failover; topology now in unexpected state",
        "trend": "stable",
    },
    "mysql_replication": {
        "latency_p50_ms": 850.0,
        "latency_p99_ms": 12000.0,
        "error_rate_pct": 45.0,
        "cpu_utilization_pct": 92.0,
        "memory_utilization_pct": 88.0,
        "request_rate_rpm": 2400.0,
        "saturation_pct": 98.0,
        "status_summary": "CRITICAL — replication lag infinite (dual-primary divergence)",
        "trend": "critical",
    },
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TASK 2 — MEDIUM: Fastly 2021 CDN Edge Configuration Defect
#
# Based on: Fastly's June 8, 2021 global outage.
# A latent software bug shipped May 12 was triggered by a customer's
# valid configuration change on June 8. Varnish edge nodes crashed
# globally, taking down ~85% of the CDN network including major sites.
#
# Learning objective: Handle a service where the root cause is a config
# push, not an infrastructure failure. Multi-service cascading impact.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK2_ALERTS = [
    # T=0: Root cause — Varnish edge crash after config push
    Alert(
        alert_id="alert-101",
        service="cdn_edge",
        severity=Severity.CRITICAL,
        title="CDN Edge Nodes — 85% Returning 503 After Config Push",
        description="Varnish cache nodes across 58 global PoPs are returning HTTP 503 errors. "
                    "Crash logs show a latent software defect triggered by customer config change "
                    "at 09:47Z. Bug was introduced in release v2.41 (deployed May 12). "
                    "85% of CDN capacity is offline.",
        timestamp="2025-01-15T09:47:00Z",
        status=AlertStatus.NEW,
        trigger_step=0,
    ),
    # T=0: Immediate detection
    Alert(
        alert_id="alert-102",
        service="cdn_monitoring",
        severity=Severity.CRITICAL,
        title="CDN Health Check — 58/62 PoPs Failing",
        description="CDN health monitoring: 58 of 62 edge PoPs are failing health checks. "
                    "Only 4 PoPs (Tokyo, Sydney, São Paulo, Mumbai) remain operational — "
                    "these were on release v2.40 (pre-bug). Global cache hit ratio dropped to 2%.",
        timestamp="2025-01-15T09:48:00Z",
        status=AlertStatus.NEW,
        trigger_step=0,
    ),
    # T=1: Customer-facing cascade
    Alert(
        alert_id="alert-103",
        service="customer_websites",
        severity=Severity.CRITICAL,
        title="Major Customer Sites Down — NYT, Reddit, BBC, Twitch, GitHub",
        description="Customer escalation flood: 1,200+ support tickets in 3 minutes. "
                    "Major sites (New York Times, Reddit, BBC, Twitch, GitHub, Stack Overflow) "
                    "are returning 503 errors globally. Estimated revenue impact: $2.3M/hour.",
        timestamp="2025-01-15T09:50:00Z",
        status=AlertStatus.NEW,
        trigger_step=1,
    ),
    # T=1: Origin servers overwhelmed
    Alert(
        alert_id="alert-104",
        service="origin_servers",
        severity=Severity.WARNING,
        title="Origin Servers — 40x Traffic Surge (Cache Miss Storm)",
        description="With CDN cache offline, all requests are hitting origin servers directly. "
                    "Origin traffic has spiked 40x from baseline. Multiple customer origins are "
                    "buckling under the load. This is a secondary effect of the CDN failure.",
        timestamp="2025-01-15T09:52:00Z",
        status=AlertStatus.NEW,
        trigger_step=1,
    ),
    # T=2: DNS fallback issues
    Alert(
        alert_id="alert-105",
        service="dns",
        severity=Severity.WARNING,
        title="DNS Resolution — Elevated NXDOMAIN Rates for CDN CNAMEs",
        description="DNS NXDOMAIN rate for CDN CNAME records has spiked 300%. Clients that "
                    "cached stale DNS entries are getting timeouts. TTL-based recovery is slow.",
        timestamp="2025-01-15T09:55:00Z",
        status=AlertStatus.NEW,
        trigger_step=2,
    ),
    # T=2: SSL certificate rotation failure
    Alert(
        alert_id="alert-106",
        service="ssl_termination",
        severity=Severity.WARNING,
        title="SSL/TLS Termination — Handshake Failures on Recovering Nodes",
        description="Edge nodes that are restarting are failing SSL handshakes for ~30 seconds "
                    "during certificate loading. Affects the 4 remaining healthy PoPs during "
                    "their config reload cycle.",
        timestamp="2025-01-15T09:57:00Z",
        status=AlertStatus.NEW,
        trigger_step=2,
    ),
    # T=3: API gateway impact (downstream)
    Alert(
        alert_id="alert-107",
        service="api_gateway",
        severity=Severity.WARNING,
        title="API Gateway — Upstream Timeout Storm from CDN Bypass",
        description="API gateway is seeing 65% timeout rate as client traffic bypasses the CDN "
                    "and hits the API directly. Rate limiting is being triggered across all tiers.",
        timestamp="2025-01-15T10:00:00Z",
        status=AlertStatus.NEW,
        trigger_step=3,
    ),
    # Noise: Scheduled maintenance
    Alert(
        alert_id="alert-108",
        service="database_maintenance",
        severity=Severity.INFO,
        title="Scheduled Database Maintenance — analytics-db Vacuum (Normal)",
        description="Routine weekly VACUUM ANALYZE on analytics-db is running as scheduled. "
                    "Job started at 09:30Z, expected duration 45 minutes. "
                    "NOT related to the CDN incident.",
        timestamp="2025-01-15T09:30:00Z",
        status=AlertStatus.NEW,
        is_noise=True,
        trigger_step=0,
    ),
]

TASK2_GROUND_TRUTH = ScenarioGroundTruth(
    task_name="fastly_cdn_outage",
    alert_truths=[
        AlertGroundTruth(
            alert_id="alert-101",
            correct_priority=Priority.P1,
            correct_team=Team.PLATFORM,
            correlation_group="cdn_config_defect",
            is_root_cause=True,
        ),
        AlertGroundTruth(
            alert_id="alert-102",
            correct_priority=Priority.P1,
            correct_team=Team.PLATFORM,
            correlation_group="cdn_config_defect",
        ),
        AlertGroundTruth(
            alert_id="alert-103",
            correct_priority=Priority.P1,
            correct_team=Team.APPLICATION,
            correlation_group="cdn_config_defect",
        ),
        AlertGroundTruth(
            alert_id="alert-104",
            correct_priority=Priority.P2,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="cdn_config_defect",
        ),
        AlertGroundTruth(
            alert_id="alert-105",
            correct_priority=Priority.P3,
            correct_team=Team.NETWORK,
            correlation_group="cdn_config_defect",
        ),
        AlertGroundTruth(
            alert_id="alert-106",
            correct_priority=Priority.P3,
            correct_team=Team.SECURITY,
            correlation_group="cdn_config_defect",
        ),
        AlertGroundTruth(
            alert_id="alert-107",
            correct_priority=Priority.P2,
            correct_team=Team.PLATFORM,
            correlation_group="cdn_config_defect",
        ),
        AlertGroundTruth(
            alert_id="alert-108",
            correct_priority=Priority.P4,
            correct_team=Team.DATABASE,
            correlation_group="noise_maintenance",
            is_noise=True,
        ),
    ],
    required_escalation_level=EscalationLevel.VP_ENG,
    required_status_updates=2,
    correlation_groups={
        "cdn_config_defect": [
            "alert-101", "alert-102", "alert-103", "alert-104",
            "alert-105", "alert-106", "alert-107",
        ],
        "noise_maintenance": ["alert-108"],
    },
    min_steps_possible=18,
)

TASK2_SLA_TIMERS = [
    SLATimer(alert_id="alert-101", steps_remaining=8, breached=False),
    SLATimer(alert_id="alert-102", steps_remaining=8, breached=False),
    SLATimer(alert_id="alert-103", steps_remaining=6, breached=False),
    SLATimer(alert_id="alert-104", steps_remaining=14, breached=False),
    SLATimer(alert_id="alert-105", steps_remaining=18, breached=False),
    SLATimer(alert_id="alert-106", steps_remaining=18, breached=False),
    SLATimer(alert_id="alert-107", steps_remaining=14, breached=False),
    SLATimer(alert_id="alert-108", steps_remaining=50, breached=False),
]

TASK2_INVESTIGATION_DATA = {
    "alert-101": (
        "Investigation: Varnish crash dump analysis reveals a latent defect in VCL "
        "(Varnish Configuration Language) processing engine. Bug was introduced in release "
        "v2.41 (deployed May 12) but remained dormant. Triggered when customer 'acme-corp' "
        "pushed a valid config that exercised an untested code path combining: (1) custom "
        "Cache-Control override, (2) wildcard origin mapping, and (3) HTTP/3 alt-svc header. "
        "This combination causes a segfault in the VCL compiler. ROOT CAUSE. "
        "Fix: Revert customer config immediately, then patch the VCL engine."
    ),
    "alert-102": (
        "Investigation: 58 PoPs are on v2.41 (affected). 4 PoPs on v2.40 are healthy. "
        "The config push propagated globally within 8 seconds via the edge control plane. "
        "Once the defective config reached each PoP, the Varnish process crashed and couldn't "
        "restart because the config is loaded at startup. Fix requires disabling the customer's "
        "config at the control plane level before restarting nodes."
    ),
    "alert-103": (
        "Investigation: Customer impact is proportional to traffic volume through affected PoPs. "
        "Major sites are down because they depend on CDN for both caching and DDoS protection. "
        "Without CDN, origin servers are directly exposed. Some customers have DNS failover "
        "to backup providers, but most don't. Workaround: encourage customers to update DNS TTL."
    ),
    "alert-104": (
        "Investigation: Origin server traffic analysis confirms a 40x volume increase. "
        "This is the classic 'thundering herd' problem when a cache layer fails. Origin "
        "servers were not provisioned for this load. Auto-scaling has been triggered but "
        "won't fully compensate. This resolves automatically once CDN caching resumes."
    ),
    "alert-105": (
        "Investigation: DNS NXDOMAIN spike is caused by clients attempting to resolve CDN CNAME "
        "records for edge nodes that are currently offline. DNS health checks have correctly "
        "removed crashed nodes from resolution pools. This is a symptom, not a root cause."
    ),
    "alert-106": (
        "Investigation: SSL handshake failures are a transient issue during Varnish node restart. "
        "Certificate loading takes ~30 seconds per node. This affects the 4 healthy PoPs during "
        "their periodic config reload cycle. Not a root cause — resolves as nodes stabilize."
    ),
    "alert-107": (
        "Investigation: API gateway is rate-limiting legitimate traffic because the CDN is no "
        "longer absorbing the request volume. Gateway health is fine — it's just overwhelmed. "
        "This resolves once CDN is back online and absorbing traffic."
    ),
    "alert-108": (
        "Investigation: Scheduled VACUUM ANALYZE job on analytics-db. Started at 09:30Z as "
        "scheduled (cron job). Expected to complete by 10:15Z. This is routine maintenance "
        "and has NO relation to the CDN incident."
    ),
}

TASK2_METRICS_DATA = {
    "cdn_edge": {
        "latency_p50_ms": 9999.0,
        "latency_p99_ms": 30000.0,
        "error_rate_pct": 85.0,
        "cpu_utilization_pct": 0.0,
        "memory_utilization_pct": 0.0,
        "request_rate_rpm": 0.0,
        "saturation_pct": 0.0,
        "status_summary": "OFFLINE — 58/62 PoPs crashed (Varnish segfault)",
        "trend": "critical",
    },
    "origin_servers": {
        "latency_p50_ms": 2800.0,
        "latency_p99_ms": 15000.0,
        "error_rate_pct": 35.0,
        "cpu_utilization_pct": 96.0,
        "memory_utilization_pct": 91.0,
        "request_rate_rpm": 48000.0,
        "saturation_pct": 95.0,
        "status_summary": "CRITICAL — thundering herd from CDN failure; 40x normal traffic",
        "trend": "critical",
    },
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TASK 3 — HARD: AWS-style Network Partition / EBS Event
#
# Based on: AWS US-EAST-1 EBS outage patterns (2011, 2012, 2015).
# A core network switch failure causes a partition between availability
# zones. EBS volumes in the affected AZ become stuck. Services in other
# AZs are healthy but can't reach the partitioned zone.
#
# Learning objective: Handle 15 alerts with 3 noise alerts mixed in.
# Identify the network switch as root cause, not the individual services.
# Successfully filter noise from real cascading failures.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK3_ALERTS = [
    # T=0: Root cause — core switch failure
    Alert(
        alert_id="alert-201",
        service="network_switch",
        severity=Severity.CRITICAL,
        title="Core Switch Fabric — Partial Failure in AZ-2",
        description="Core switch sw-core-02 in Availability Zone 2 (AZ-2) is reporting partial "
                    "fabric failure. Links to AZ-3 and AZ-4 are flapping. BGP sessions are being "
                    "torn down. Affects cross-AZ communication for racks C, D, E.",
        timestamp="2025-01-15T03:00:00Z",
        status=AlertStatus.NEW,
        trigger_step=0,
    ),
    # T=0: EBS volumes stuck
    Alert(
        alert_id="alert-202",
        service="ebs_volumes",
        severity=Severity.CRITICAL,
        title="EBS Volumes — Stuck I/O in AZ-2 (500+ Volumes Affected)",
        description="500+ EBS volumes in AZ-2 are reporting stuck I/O operations. Volume status "
                    "checks are failing. Instances attached to these volumes are hanging on disk "
                    "operations. EBS control plane cannot reach storage nodes in AZ-2.",
        timestamp="2025-01-15T03:00:30Z",
        status=AlertStatus.NEW,
        trigger_step=0,
    ),
    # T=1: DNS cascading
    Alert(
        alert_id="alert-203",
        service="dns",
        severity=Severity.CRITICAL,
        title="Internal DNS Resolution — Intermittent Failures (AZ-2 Resolvers Down)",
        description="2 of 3 internal DNS resolvers are in AZ-2 and unreachable. DNS resolution "
                    "rate dropped to 40%. Services using DNS-based service discovery are affected "
                    "across all AZs because they can't resolve AZ-2 endpoints.",
        timestamp="2025-01-15T03:01:00Z",
        status=AlertStatus.NEW,
        trigger_step=1,
    ),
    # T=1: Kubernetes impact
    Alert(
        alert_id="alert-204",
        service="kubernetes",
        severity=Severity.CRITICAL,
        title="Kubernetes — 8/24 Nodes NotReady (AZ-2 Workers Isolated)",
        description="8 out of 24 Kubernetes worker nodes are in NotReady state. All affected "
                    "nodes are in AZ-2. Pods are being evicted and rescheduled to AZ-1 and AZ-3, "
                    "causing resource contention.",
        timestamp="2025-01-15T03:01:30Z",
        status=AlertStatus.NEW,
        trigger_step=1,
    ),
    # T=2: Payment service down
    Alert(
        alert_id="alert-205",
        service="payment_service",
        severity=Severity.CRITICAL,
        title="Payment Processing — Complete Failure (Revenue Impact ~$50K/hr)",
        description="Payment service pods in AZ-2 cannot reach the payment gateway API. "
                    "All payment transactions are failing. Revenue impact: ~$50K/hour. "
                    "Pods in AZ-1 are healthy but overwhelmed by redirect traffic.",
        timestamp="2025-01-15T03:02:00Z",
        status=AlertStatus.NEW,
        trigger_step=2,
    ),
    # T=2: Auth failures
    Alert(
        alert_id="alert-206",
        service="auth_service",
        severity=Severity.CRITICAL,
        title="Authentication — 50% Login Failures (IdP in AZ-2)",
        description="Auth service pods in AZ-1/AZ-3 cannot reach the identity provider "
                    "running in AZ-2. 50% of login attempts are failing. Sessions already "
                    "established still work.",
        timestamp="2025-01-15T03:02:30Z",
        status=AlertStatus.NEW,
        trigger_step=2,
    ),
    # T=3: RabbitMQ split brain
    Alert(
        alert_id="alert-207",
        service="message_queue",
        severity=Severity.WARNING,
        title="RabbitMQ Cluster — Split Brain Detected (AZ-2 Partition)",
        description="RabbitMQ cluster has split into two partitions. Nodes in AZ-2 formed "
                    "a separate cluster from AZ-1/AZ-3 nodes. Messages may be duplicated or lost "
                    "across the partition boundary.",
        timestamp="2025-01-15T03:03:00Z",
        status=AlertStatus.NEW,
        trigger_step=3,
    ),
    # T=3: Storage replication degraded
    Alert(
        alert_id="alert-208",
        service="storage",
        severity=Severity.WARNING,
        title="Ceph Storage — Replication Factor Dropped from 3→2",
        description="Ceph storage cluster replication factor has dropped from 3 to 2. "
                    "OSDs in AZ-2 are marked DOWN. Data is safe but less resilient "
                    "until AZ-2 storage nodes rejoin the cluster.",
        timestamp="2025-01-15T03:03:30Z",
        status=AlertStatus.NEW,
        trigger_step=3,
    ),
    # Noise: Scheduled SSL cert expiry (staging)
    Alert(
        alert_id="alert-209",
        service="ssl_certificate",
        severity=Severity.WARNING,
        title="SSL Certificate Expiry Warning — staging.example.com (7 days)",
        description="SSL certificate for staging.example.com will expire in 7 days. "
                    "Staging environment only. No production impact.",
        timestamp="2025-01-15T03:04:00Z",
        status=AlertStatus.NEW,
        is_noise=True,
        trigger_step=0,
    ),
    # T=4: Monitoring blind spot
    Alert(
        alert_id="alert-210",
        service="monitoring",
        severity=Severity.WARNING,
        title="Prometheus — Unable to Scrape 12/45 Targets in AZ-2",
        description="Prometheus in AZ-1 cannot reach exporters in AZ-2. Monitoring coverage "
                    "for AZ-2 services is incomplete. Alerting for AZ-2 is unreliable.",
        timestamp="2025-01-15T03:04:30Z",
        status=AlertStatus.NEW,
        trigger_step=4,
    ),
    # T=4: API Gateway overwhelmed
    Alert(
        alert_id="alert-211",
        service="api_gateway",
        severity=Severity.CRITICAL,
        title="API Gateway — 60% Upstream Timeout Storm",
        description="API gateway is timing out on 60% of requests. All failed requests are "
                    "targeting services in AZ-2. Healthy AZ-1/AZ-3 backends are overloaded "
                    "from redirected traffic.",
        timestamp="2025-01-15T03:05:00Z",
        status=AlertStatus.NEW,
        trigger_step=4,
    ),
    # Noise: Scheduled deployment (approved)
    Alert(
        alert_id="alert-212",
        service="deployment",
        severity=Severity.INFO,
        title="Scheduled Deployment — analytics-pipeline v3.2.1 (Approved)",
        description="Scheduled deployment of analytics-pipeline v3.2.1 proceeding as planned. "
                    "Approved in change management ticket CM-2025-0142. Running in AZ-1.",
        timestamp="2025-01-15T03:05:30Z",
        status=AlertStatus.NEW,
        is_noise=True,
        trigger_step=1,
    ),
    # T=5: DB replica failure
    Alert(
        alert_id="alert-213",
        service="database",
        severity=Severity.CRITICAL,
        title="PostgreSQL Replica — Connection Refused (AZ-2 Replica Down)",
        description="PostgreSQL read replica pg-replica-03 (AZ-2) is refusing connections. "
                    "Primary in AZ-1 is operational. Read traffic redirected to remaining replicas.",
        timestamp="2025-01-15T03:06:00Z",
        status=AlertStatus.NEW,
        trigger_step=5,
    ),
    # Noise: HPA auto-scaling (normal behavior)
    Alert(
        alert_id="alert-214",
        service="kubernetes",
        severity=Severity.INFO,
        title="HPA Scale-Up — frontend-web 6→10 Pods (Normal Auto-Scaling)",
        description="Horizontal Pod Autoscaler scaled frontend-web from 6 to 10 pods due to "
                    "increased CPU. This is normal auto-scaling behavior in response to AZ-2 "
                    "pod evictions.",
        timestamp="2025-01-15T03:06:30Z",
        status=AlertStatus.NEW,
        is_noise=True,
        trigger_step=2,
    ),
    # T=6: CDN origin failures
    Alert(
        alert_id="alert-215",
        service="cdn",
        severity=Severity.WARNING,
        title="CDN Origin Fetch Failures — Cache Hit Ratio 95%→60%",
        description="CDN cannot reach origin servers in AZ-2 for cache misses. Serving stale "
                    "content where possible. API-driven content is failing.",
        timestamp="2025-01-15T03:07:00Z",
        status=AlertStatus.NEW,
        trigger_step=6,
    ),
]

TASK3_GROUND_TRUTH = ScenarioGroundTruth(
    task_name="aws_network_partition",
    alert_truths=[
        AlertGroundTruth(
            alert_id="alert-201",
            correct_priority=Priority.P1,
            correct_team=Team.NETWORK,
            correlation_group="az2_partition",
            is_root_cause=True,
        ),
        AlertGroundTruth(
            alert_id="alert-202",
            correct_priority=Priority.P1,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="az2_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-203",
            correct_priority=Priority.P1,
            correct_team=Team.NETWORK,
            correlation_group="az2_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-204",
            correct_priority=Priority.P1,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="az2_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-205",
            correct_priority=Priority.P1,
            correct_team=Team.APPLICATION,
            correlation_group="az2_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-206",
            correct_priority=Priority.P1,
            correct_team=Team.SECURITY,
            correlation_group="az2_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-207",
            correct_priority=Priority.P2,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="az2_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-208",
            correct_priority=Priority.P2,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="az2_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-209",
            correct_priority=Priority.P4,
            correct_team=Team.SECURITY,
            correlation_group="noise_cert",
            is_noise=True,
        ),
        AlertGroundTruth(
            alert_id="alert-210",
            correct_priority=Priority.P3,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="az2_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-211",
            correct_priority=Priority.P1,
            correct_team=Team.PLATFORM,
            correlation_group="az2_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-212",
            correct_priority=Priority.P4,
            correct_team=Team.APPLICATION,
            correlation_group="noise_deployment",
            is_noise=True,
        ),
        AlertGroundTruth(
            alert_id="alert-213",
            correct_priority=Priority.P2,
            correct_team=Team.DATABASE,
            correlation_group="az2_partition",
        ),
        AlertGroundTruth(
            alert_id="alert-214",
            correct_priority=Priority.P4,
            correct_team=Team.INFRASTRUCTURE,
            correlation_group="noise_autoscale",
            is_noise=True,
        ),
        AlertGroundTruth(
            alert_id="alert-215",
            correct_priority=Priority.P2,
            correct_team=Team.PLATFORM,
            correlation_group="az2_partition",
        ),
    ],
    required_escalation_level=EscalationLevel.VP_ENG,
    required_status_updates=3,
    correlation_groups={
        "az2_partition": [
            "alert-201", "alert-202", "alert-203", "alert-204", "alert-205",
            "alert-206", "alert-207", "alert-208", "alert-210", "alert-211",
            "alert-213", "alert-215",
        ],
        "noise_cert": ["alert-209"],
        "noise_deployment": ["alert-212"],
        "noise_autoscale": ["alert-214"],
    },
    min_steps_possible=20,
)

TASK3_SLA_TIMERS = [
    SLATimer(alert_id="alert-201", steps_remaining=12, breached=False),
    SLATimer(alert_id="alert-202", steps_remaining=10, breached=False),
    SLATimer(alert_id="alert-203", steps_remaining=12, breached=False),
    SLATimer(alert_id="alert-204", steps_remaining=12, breached=False),
    SLATimer(alert_id="alert-205", steps_remaining=8, breached=False),
    SLATimer(alert_id="alert-206", steps_remaining=10, breached=False),
    SLATimer(alert_id="alert-207", steps_remaining=18, breached=False),
    SLATimer(alert_id="alert-208", steps_remaining=18, breached=False),
    SLATimer(alert_id="alert-209", steps_remaining=50, breached=False),
    SLATimer(alert_id="alert-210", steps_remaining=20, breached=False),
    SLATimer(alert_id="alert-211", steps_remaining=10, breached=False),
    SLATimer(alert_id="alert-212", steps_remaining=50, breached=False),
    SLATimer(alert_id="alert-213", steps_remaining=14, breached=False),
    SLATimer(alert_id="alert-214", steps_remaining=50, breached=False),
    SLATimer(alert_id="alert-215", steps_remaining=16, breached=False),
]

TASK3_INVESTIGATION_DATA = {
    "alert-201": (
        "Investigation: Core switch sw-core-02 ASIC shows partial fabric failure. "
        "Ports 25-48 are down, affecting uplinks to AZ-3 and AZ-4. Hardware fault — "
        "Juniper QFX5200 ASIC failure. Vendor RMA should be initiated. "
        "This is the ROOT CAUSE of the cascading failure across all affected AZs. "
        "Based on similar pattern to AWS US-EAST-1 2011 EBS outage."
    ),
    "alert-202": (
        "Investigation: EBS volumes are stuck because the EBS control plane lost "
        "connectivity to storage nodes in AZ-2. Volumes can't commit I/O operations "
        "and are in a 'stuck' state. EC2 instances are hanging on disk write syscalls. "
        "Recovery requires restoring network connectivity to AZ-2 storage nodes."
    ),
    "alert-203": (
        "Investigation: DNS failures — 2 of 3 internal resolvers are in AZ-2. "
        "Only the AZ-1 resolver is reachable. Cross-AZ DNS lookups fail for AZ-2 "
        "endpoints. Fix: add emergency resolver in AZ-3."
    ),
    "alert-204": (
        "Investigation: Kubernetes control plane is in AZ-1 (healthy). Workers in AZ-2 "
        "lost kubelet heartbeat. Pods evicted per NoExecute taint. Don't restart nodes — "
        "fix the network first."
    ),
    "alert-205": (
        "Investigation: Payment service depends on payment gateway API. AZ-2 instances "
        "can't reach it through the partition. AZ-1 instances are fine but overwhelmed. "
        "Reroute all traffic to AZ-1 temporarily."
    ),
    "alert-206": (
        "Investigation: Auth service LDAP/IdP in AZ-2 is unreachable from AZ-1/AZ-3. "
        "50% failure rate correlates with half of traffic hitting pods that can't reach IdP."
    ),
    "alert-207": (
        "Investigation: RabbitMQ split-brain. Both partitions think they're authoritative. "
        "Requires manual intervention after network restoration."
    ),
    "alert-208": (
        "Investigation: Ceph OSDs in AZ-2 marked DOWN. Replication factor 3→2. "
        "No data loss as long as AZ-1 storage remains operational."
    ),
    "alert-209": (
        "Investigation: Routine staging certificate expiry warning. No production impact. "
        "NOT related to the current incident."
    ),
    "alert-210": (
        "Investigation: Prometheus in AZ-1 can't scrape AZ-2 exporters. Monitoring gap "
        "is a symptom of the network partition, not a separate problem."
    ),
    "alert-211": (
        "Investigation: API gateway load-balances across all backends including AZ-2 "
        "unreachable ones. Timeout rate = AZ-2 pods / total pods. Update routing to exclude "
        "AZ-2 backends."
    ),
    "alert-212": (
        "Investigation: Approved scheduled deployment running in AZ-1. Unaffected by "
        "the partition. NOT related to the current incident."
    ),
    "alert-213": (
        "Investigation: PostgreSQL replica in AZ-2 lost streaming replication. Primary in "
        "AZ-1 is healthy. Will auto-recover when network is restored."
    ),
    "alert-214": (
        "Investigation: HPA scale-up is normal — fewer pods available means higher per-pod "
        "CPU. Autoscaler working correctly. NOT a separate issue."
    ),
    "alert-215": (
        "Investigation: CDN can't reach AZ-2 origins for cache misses. Serving stale content "
        "where TTL hasn't expired. Low priority — resolves with network fix."
    ),
}

TASK3_METRICS_DATA = {
    "network_switch": {
        "latency_p50_ms": 9999.0,
        "latency_p99_ms": 30000.0,
        "error_rate_pct": 100.0,
        "cpu_utilization_pct": 0.0,
        "memory_utilization_pct": 0.0,
        "request_rate_rpm": 0.0,
        "saturation_pct": None,
        "status_summary": "HARDWARE FAILURE — ASIC partial failure, ports 25-48 down",
        "trend": "critical",
    },
    "ebs_volumes": {
        "latency_p50_ms": 30000.0,
        "latency_p99_ms": 60000.0,
        "error_rate_pct": 100.0,
        "cpu_utilization_pct": 0.0,
        "memory_utilization_pct": 0.0,
        "request_rate_rpm": 0.0,
        "saturation_pct": 100.0,
        "status_summary": "STUCK I/O — 500+ volumes in AZ-2 cannot complete operations",
        "trend": "critical",
    },
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TASK 4 — EXPERT: SolarWinds-Pattern Supply Chain / Credential Attack
#
# Based on: SolarWinds 2020 attack pattern + 2020 Twitter/FireEye incidents.
# Attackers compromise a build pipeline, inject a backdoor via a
# software update, then use stolen credentials for lateral movement
# and data exfiltration. Includes sophisticated persistence.
#
# Learning objective: Identify attack chain (supply chain compromise →
# lateral movement → data exfiltration). Filter routine security noise.
# Escalate to CTO. Write postmortem identifying the supply chain entry.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK4_ALERTS = [
    # T=0: Initial anomaly — build pipeline compromise (ROOT CAUSE)
    Alert(
        alert_id="alert-301",
        service="ci_cd_pipeline",
        severity=Severity.CRITICAL,
        title="CI/CD — Unauthorized Build Artifact Modification Detected",
        description="SIEM alert: Build artifact checksum mismatch for 'platform-agent v4.2.1'. "
                    "Expected SHA-256 does not match published artifact. Build log shows an "
                    "injected step that was not in the approved Jenkinsfile. "
                    "Artifact was published to internal registry 6 hours ago.",
        timestamp="2025-01-15T02:10:00Z",
        status=AlertStatus.NEW,
        trigger_step=0,
    ),
    # T=0: Credential harvesting
    Alert(
        alert_id="alert-302",
        service="auth_service",
        severity=Severity.CRITICAL,
        title="Brute Force + Credential Stuffing — 50K Failed Logins/min from Tor",
        description="Auth service receiving 50,000 failed login attempts per minute from "
                    "Tor exit nodes (185.220.x.x/24). Rate limiting partially bypassed via "
                    "distributed source IPs. Attack started at 02:14Z.",
        timestamp="2025-01-15T02:14:00Z",
        status=AlertStatus.NEW,
        trigger_step=0,
    ),
    # T=1: Compromised accounts
    Alert(
        alert_id="alert-303",
        service="auth_service",
        severity=Severity.CRITICAL,
        title="Credential Stuffing — 2,400 Accounts Compromised (14 Admin-Tier)",
        description="Cross-referencing attack IPs with successful logins: 2,412 accounts "
                    "authenticated from attacker IP ranges. Includes 14 admin-tier accounts. "
                    "Immediate forced password reset and session invalidation required.",
        timestamp="2025-01-15T02:17:00Z",
        status=AlertStatus.NEW,
        trigger_step=1,
    ),
    # T=1: WAF detecting injection attempts
    Alert(
        alert_id="alert-304",
        service="waf",
        severity=Severity.CRITICAL,
        title="WAF — SQL Injection Patterns on /api/login (18K Attempts Blocked)",
        description="Web Application Firewall logged 18,000 SQL injection attempts against "
                    "/api/login. Attack toolkit identified as 'SQLMapAuth-v3'. "
                    "99.7% blocked, but 54 reached the application layer.",
        timestamp="2025-01-15T02:16:00Z",
        status=AlertStatus.NEW,
        trigger_step=1,
    ),
    # T=2: Lateral movement via backdoor
    Alert(
        alert_id="alert-305",
        service="internal_network",
        severity=Severity.CRITICAL,
        title="IDS Alert — Lateral Movement via Backdoored platform-agent",
        description="Intrusion Detection System detected C2 (Command & Control) beaconing from "
                    "12 internal hosts running 'platform-agent v4.2.1'. The backdoored build "
                    "artifact includes a reverse shell that phones home every 60 seconds. "
                    "Attacker has gained internal network access via supply chain compromise.",
        timestamp="2025-01-15T02:25:00Z",
        status=AlertStatus.NEW,
        trigger_step=2,
    ),
    # T=3: Data exfiltration
    Alert(
        alert_id="alert-306",
        service="data_pipeline",
        severity=Severity.CRITICAL,
        title="Anomalous Data Exfiltration — 48 GB to Tor Exit Node",
        description="Data pipeline egress monitoring: 48.3 GB transferred to 185.220.101.47 "
                    "(Tor exit node) over 22 minutes. Transfer pattern matches database dump. "
                    "Likely exfiltration of user credential database. "
                    "This is an ACTIVE DATA BREACH.",
        timestamp="2025-01-15T02:31:00Z",
        status=AlertStatus.NEW,
        trigger_step=3,
    ),
    # T=3: OAuth token abuse
    Alert(
        alert_id="alert-307",
        service="auth_service",
        severity=Severity.WARNING,
        title="OAuth Token Issuance 900% Above Baseline",
        description="OAuth tokens issued at 9x baseline since 02:14Z. Tokens from compromised "
                    "accounts. Scopes include read:payment_methods on 340 unique tokens.",
        timestamp="2025-01-15T02:20:00Z",
        status=AlertStatus.NEW,
        trigger_step=3,
    ),
    # T=4: CDN cache purge via compromised admin
    Alert(
        alert_id="alert-308",
        service="cdn",
        severity=Severity.WARNING,
        title="CDN Edge Cache Purge — Unauthorized Origin (Compromised Admin)",
        description="CDN purge request from API key of compromised admin account (usr-00847). "
                    "Cleared cached auth responses across 12 edge nodes. Forces fresh auth "
                    "checks that attacker could intercept.",
        timestamp="2025-01-15T02:22:00Z",
        status=AlertStatus.NEW,
        trigger_step=4,
    ),
    # T=4: API traffic anomaly
    Alert(
        alert_id="alert-309",
        service="api_gateway",
        severity=Severity.WARNING,
        title="API Gateway — 89% Traffic from Tor Exit Nodes",
        description="89% of API gateway traffic in the last 15 minutes from known Tor exit "
                    "node ranges. Normal Tor traffic is <0.1%. Consistent with coordinated "
                    "attack infrastructure.",
        timestamp="2025-01-15T02:18:00Z",
        status=AlertStatus.NEW,
        trigger_step=4,
    ),
    # Noise: Scheduled compliance scan
    Alert(
        alert_id="alert-310",
        service="security_scanner",
        severity=Severity.INFO,
        title="Scheduled Security Scan — compliance-scan-weekly (Normal)",
        description="Weekly SOC 2 compliance scanner run (scheduled every Sunday 02:00Z). "
                    "Scanning internal endpoints per compliance requirements. "
                    "NOT related to the active security incident.",
        timestamp="2025-01-15T02:00:00Z",
        status=AlertStatus.NEW,
        is_noise=True,
        trigger_step=0,
    ),
    # Noise: Dev certificate expiry
    Alert(
        alert_id="alert-311",
        service="ssl_certificate",
        severity=Severity.INFO,
        title="SSL Certificate Expiry — dev.internal.example.com (14 Days)",
        description="TLS certificate for dev.internal.example.com expires in 14 days. "
                    "Developer environment only. NOT related to the active incident.",
        timestamp="2025-01-15T02:05:00Z",
        status=AlertStatus.NEW,
        is_noise=True,
        trigger_step=0,
    ),
]

TASK4_GROUND_TRUTH = ScenarioGroundTruth(
    task_name="solarwinds_supply_chain",
    alert_truths=[
        AlertGroundTruth(
            alert_id="alert-301",
            correct_priority=Priority.P1,
            correct_team=Team.SECURITY,
            correlation_group="supply_chain_attack",
            is_root_cause=True,
        ),
        AlertGroundTruth(
            alert_id="alert-302",
            correct_priority=Priority.P1,
            correct_team=Team.SECURITY,
            correlation_group="supply_chain_attack",
        ),
        AlertGroundTruth(
            alert_id="alert-303",
            correct_priority=Priority.P1,
            correct_team=Team.SECURITY,
            correlation_group="supply_chain_attack",
        ),
        AlertGroundTruth(
            alert_id="alert-304",
            correct_priority=Priority.P1,
            correct_team=Team.SECURITY,
            correlation_group="supply_chain_attack",
        ),
        AlertGroundTruth(
            alert_id="alert-305",
            correct_priority=Priority.P1,
            correct_team=Team.SECURITY,
            correlation_group="supply_chain_attack",
        ),
        AlertGroundTruth(
            alert_id="alert-306",
            correct_priority=Priority.P1,
            correct_team=Team.SECURITY,
            correlation_group="supply_chain_attack",
        ),
        AlertGroundTruth(
            alert_id="alert-307",
            correct_priority=Priority.P2,
            correct_team=Team.SECURITY,
            correlation_group="supply_chain_attack",
        ),
        AlertGroundTruth(
            alert_id="alert-308",
            correct_priority=Priority.P2,
            correct_team=Team.SECURITY,
            correlation_group="supply_chain_attack",
        ),
        AlertGroundTruth(
            alert_id="alert-309",
            correct_priority=Priority.P2,
            correct_team=Team.SECURITY,
            correlation_group="supply_chain_attack",
        ),
        # Noise
        AlertGroundTruth(
            alert_id="alert-310",
            correct_priority=Priority.P4,
            correct_team=Team.SECURITY,
            correlation_group="noise_scan",
            is_noise=True,
        ),
        AlertGroundTruth(
            alert_id="alert-311",
            correct_priority=Priority.P4,
            correct_team=Team.SECURITY,
            correlation_group="noise_cert",
            is_noise=True,
        ),
    ],
    required_escalation_level=EscalationLevel.CTO,
    required_status_updates=2,
    correlation_groups={
        "supply_chain_attack": [
            "alert-301", "alert-302", "alert-303", "alert-304",
            "alert-305", "alert-306", "alert-307", "alert-308", "alert-309",
        ],
        "noise_scan": ["alert-310"],
        "noise_cert": ["alert-311"],
    },
    min_steps_possible=24,
)

TASK4_SLA_TIMERS = [
    SLATimer(alert_id="alert-301", steps_remaining=6, breached=False),
    SLATimer(alert_id="alert-302", steps_remaining=6, breached=False),
    SLATimer(alert_id="alert-303", steps_remaining=6, breached=False),
    SLATimer(alert_id="alert-304", steps_remaining=6, breached=False),
    SLATimer(alert_id="alert-305", steps_remaining=6, breached=False),
    SLATimer(alert_id="alert-306", steps_remaining=6, breached=False),
    SLATimer(alert_id="alert-307", steps_remaining=12, breached=False),
    SLATimer(alert_id="alert-308", steps_remaining=12, breached=False),
    SLATimer(alert_id="alert-309", steps_remaining=12, breached=False),
    SLATimer(alert_id="alert-310", steps_remaining=50, breached=False),
    SLATimer(alert_id="alert-311", steps_remaining=50, breached=False),
]

TASK4_INVESTIGATION_DATA = {
    "alert-301": (
        "Investigation: CRITICAL FINDING — CI/CD pipeline compromise detected. "
        "Build artifact 'platform-agent v4.2.1' was modified post-compilation. "
        "An unauthorized build step injected a reverse shell backdoor into the binary. "
        "The Jenkinsfile was modified by service account 'ci-bot' whose credentials "
        "were rotated 3 days ago — the OLD credentials were still valid (not revoked). "
        "This is the SUPPLY CHAIN ENTRY POINT — ROOT CAUSE of the entire attack. "
        "Pattern matches SolarWinds SUNBURST technique: inject at build, distribute via "
        "trusted update channel. All 12 hosts running v4.2.1 are compromised."
    ),
    "alert-302": (
        "Investigation: Auth service logs show systematic credential stuffing from Tor exit "
        "nodes (185.220.x.x/24). Attack started at 02:14Z. Rate limiting partially bypassed. "
        "This is PHASE 2 of the attack — attacker is using credentials harvested from the "
        "backdoored platform-agent to access additional accounts."
    ),
    "alert-303": (
        "Investigation: 2,412 accounts compromised. 14 admin-tier. Attacker has active "
        "sessions for 340+ accounts. All must be force-logged-out and passwords reset."
    ),
    "alert-304": (
        "Investigation: WAF SQL injection attempts are a smokescreen — the real attack vector "
        "is the supply chain backdoor (alert-301). SQL injection is a distraction to consume "
        "incident response resources. WAF rules are effective — no successful SQLi detected."
    ),
    "alert-305": (
        "Investigation: IDS detected C2 beaconing from 12 internal hosts. All are running "
        "'platform-agent v4.2.1' (the backdoored build). The reverse shell phones home to "
        "185.220.101.47 every 60 seconds. Attacker has used this access for lateral movement "
        "to database servers and credential stores. This is PHASE 3 of the attack chain."
    ),
    "alert-306": (
        "Investigation: 48.3 GB exfiltrated to Tor exit node. Transfer matches user_credentials "
        "table schema (41 GB) and payment_tokens table (7 GB). This is an ACTIVE DATA BREACH. "
        "Compliance/legal notification required under breach notification laws. "
        "Transfer has completed — focus on containment and breach notification."
    ),
    "alert-307": (
        "Investigation: OAuth tokens issued to compromised accounts. Scopes include "
        "read:payment_methods — could expose partial card data. All tokens issued after "
        "02:14Z should be revoked immediately."
    ),
    "alert-308": (
        "Investigation: CDN purge from compromised admin account usr-00847. Forces downstream "
        "services to re-authenticate against origin, creating MITM opportunity. "
        "Account must be immediately suspended."
    ),
    "alert-309": (
        "Investigation: 89% Tor traffic from the same attack campaign. Blocking Tor exit "
        "nodes at gateway will stop most attack traffic. Acceptable collateral impact."
    ),
    "alert-310": (
        "Investigation: Weekly SOC 2 compliance scan. Running normally. NOT related to "
        "the active security incident. Do not cancel."
    ),
    "alert-311": (
        "Investigation: Dev environment SSL cert expiry. Zero production traffic. "
        "NOT related to the active breach."
    ),
}

TASK4_METRICS_DATA = {
    "auth_service": {
        "latency_p50_ms": 850.0,
        "latency_p99_ms": 12000.0,
        "error_rate_pct": 78.0,
        "cpu_utilization_pct": 95.0,
        "memory_utilization_pct": 88.0,
        "request_rate_rpm": 52000.0,
        "saturation_pct": 97.0,
        "status_summary": "CRITICAL — under active brute force attack; 50K failed logins/min",
        "trend": "critical",
    },
    "ci_cd_pipeline": {
        "latency_p50_ms": 25.0,
        "latency_p99_ms": 120.0,
        "error_rate_pct": 0.0,
        "cpu_utilization_pct": 15.0,
        "memory_utilization_pct": 30.0,
        "request_rate_rpm": 45.0,
        "saturation_pct": None,
        "status_summary": "COMPROMISED — build artifacts modified; reverse shell injected",
        "trend": "critical",
    },
    "data_pipeline": {
        "latency_p50_ms": 200.0,
        "latency_p99_ms": 800.0,
        "error_rate_pct": 0.0,
        "cpu_utilization_pct": 45.0,
        "memory_utilization_pct": 60.0,
        "request_rate_rpm": 150.0,
        "saturation_pct": 40.0,
        "status_summary": "DATA EXFILTRATION — 48.3 GB transferred to external Tor node",
        "trend": "critical",
    },
}


# ─── Scenario Registry ───────────────────────────────────────────────────────

SCENARIOS = {
    "github_database_failover": {
        "alerts": TASK1_ALERTS,
        "ground_truth": TASK1_GROUND_TRUTH,
        "sla_timers": TASK1_SLA_TIMERS,
        "investigation_data": TASK1_INVESTIGATION_DATA,
        "metrics_data": TASK1_METRICS_DATA,
        "max_steps": 15,
        "description": (
            "Easy: Based on GitHub's October 2018 outage. A 43-second network interruption "
            "during maintenance triggers MySQL Orchestrator failover, causing data divergence "
            "across 23 clusters. Alerts cascade as user-facing impact spreads."
        ),
    },
    "fastly_cdn_outage": {
        "alerts": TASK2_ALERTS,
        "ground_truth": TASK2_GROUND_TRUTH,
        "sla_timers": TASK2_SLA_TIMERS,
        "investigation_data": TASK2_INVESTIGATION_DATA,
        "metrics_data": TASK2_METRICS_DATA,
        "max_steps": 25,
        "description": (
            "Medium: Based on Fastly's June 2021 global CDN outage. A latent Varnish bug, "
            "introduced weeks earlier, is triggered by a customer config change. 85% of edge "
            "nodes crash, taking down major websites. Origin servers are overwhelmed by "
            "thundering herd. Must filter 1 noise alert."
        ),
    },
    "aws_network_partition": {
        "alerts": TASK3_ALERTS,
        "ground_truth": TASK3_GROUND_TRUTH,
        "sla_timers": TASK3_SLA_TIMERS,
        "investigation_data": TASK3_INVESTIGATION_DATA,
        "metrics_data": TASK3_METRICS_DATA,
        "max_steps": 45,
        "description": (
            "Hard: Based on AWS US-EAST-1 EBS outage patterns. Core switch failure causes "
            "AZ-2 partition — EBS volumes stuck, services cascading. 15 alerts with 3 noise "
            "mixed in. Temporal cascading: new alerts appear at steps 0-6 as the failure "
            "propagates through the infrastructure stack."
        ),
    },
    "solarwinds_supply_chain": {
        "alerts": TASK4_ALERTS,
        "ground_truth": TASK4_GROUND_TRUTH,
        "sla_timers": TASK4_SLA_TIMERS,
        "investigation_data": TASK4_INVESTIGATION_DATA,
        "metrics_data": TASK4_METRICS_DATA,
        "max_steps": 35,
        "description": (
            "Expert: Based on SolarWinds 2020 supply chain attack pattern. Compromised CI/CD "
            "pipeline injects a backdoor into a trusted software update. Attacker uses stolen "
            "credentials for lateral movement, then exfiltrates 48 GB of data. Must identify "
            "supply chain entry point as root cause, not the downstream credential stuffing."
        ),
    },
}


def get_scenario(task_name: str) -> dict:
    """Get a scenario by name. Returns a copy to avoid mutation."""
    if task_name not in SCENARIOS:
        raise ValueError(
            f"Unknown task: {task_name!r}. Available tasks: {list(SCENARIOS.keys())}"
        )
    scenario = SCENARIOS[task_name]
    import copy
    return {
        "alerts": copy.deepcopy(scenario["alerts"]),
        "ground_truth": scenario["ground_truth"],  # immutable reference OK
        "sla_timers": copy.deepcopy(scenario["sla_timers"]),
        "investigation_data": scenario["investigation_data"],  # read-only dict OK
        "metrics_data": scenario.get("metrics_data", {}),
        "max_steps": scenario["max_steps"],
        "description": scenario["description"],
    }


def list_tasks() -> List[str]:
    """List all available task names."""
    return list(SCENARIOS.keys())
