# Scenario Design Document

> Each scenario in the Incident Commander Environment is modeled after a real-world infrastructure incident.
> This document explains the historical basis, learning objectives, and difficulty calibration for each task.

---

## Task 1: GitHub Database Failover (Easy)

**Historical basis:** GitHub's October 21, 2018 outage.

**What happened:** During routine hardware maintenance, a 100G optical transceiver replacement caused a 43-second loss of connectivity between GitHub's US-East and US-West data centers. MySQL Orchestrator, which monitors database health, detected the East Coast primary as unreachable (its timeout is 30 seconds). It automatically promoted the West Coast replica to primary. However, the original East Coast primary had accepted ~40 seconds of uncommitted writes that were never replicated to West. This caused data divergence across 23 MySQL clusters, leading to 24 hours of degraded service while engineers manually reconciled data.

**Learning objective:** The agent must identify that the **network interruption** (not the database) is the root cause. The orchestrator acted correctly given its configuration — the fault is upstream.

**Difficulty:** Easy — only 4 alerts, 2 of which cascade in at later steps. Straightforward root cause identification.

---

## Task 2: Fastly CDN Configuration Defect (Medium)

**Historical basis:** Fastly's June 8, 2021 global outage.

**What happened:** A latent software bug was introduced in Varnish release v2.41 on May 12, 2021. It remained dormant for 27 days. On June 8, a customer pushed a valid configuration change that exercised an untested code path, triggering a segfault in the VCL (Varnish Configuration Language) compiler. Because Fastly's architecture propagates configurations instantly across its global edge network, 85% of edge nodes crashed within seconds. Major websites including NYT, Reddit, BBC, and Twitch went down. Fastly detected the issue within 1 minute but it took 49 minutes for 95% recovery.

**Learning objective:** The root cause is a **configuration push triggering a latent bug**, not a hardware or network failure. The agent must recognize the "thundering herd" effect on origin servers as a secondary symptom, not a separate incident. Must filter 1 noise alert (scheduled maintenance).

**Difficulty:** Medium — 8 alerts with temporal cascading over 4 steps. Requires understanding of CDN architecture and cache miss storms.

---

## Task 3: AWS Network Partition / EBS Event (Hard)

**Historical basis:** AWS US-EAST-1 EBS outage patterns (2011, 2012, 2015).

**What happened:** A core network switch (ASIC hardware failure) causes a partition between availability zones. EBS volumes in the affected AZ become stuck — they can't complete I/O operations because the EBS control plane can't reach storage nodes. Services in other AZs are healthy but can't communicate with the partitioned zone. The failure cascades through DNS, Kubernetes, payment processing, authentication, message queuing, storage replication, and CDN.

**Learning objective:** Handle 15 alerts with 3 noise alerts mixed in. The agent must identify the **core switch failure** as the root cause (not individual service failures), correctly filter noise (SSL cert expiry, scheduled deployment, HPA scale-up), and correlate 12 real alerts into a single incident group. Temporal cascading introduces new alerts over 7 steps.

**Difficulty:** Hard — 15 alerts, 3 noise, 12 cascading. Requires prioritizing under time pressure (tight SLA timers) and resisting the urge to over-escalate noise.

---

## Task 4: SolarWinds-Pattern Supply Chain Attack (Expert)

**Historical basis:** SolarWinds SUNBURST attack (2020) + Twitter internal tools hack (2020) + FireEye breach (2020).

**What happened:** Attackers compromise a CI/CD pipeline by using old, unrevoked service account credentials. They inject a reverse shell backdoor into a trusted software update (`platform-agent v4.2.1`). The backdoored artifact is distributed to 12 internal hosts via the normal update channel. Simultaneously, attackers launch a credential stuffing attack from Tor exit nodes to harvest additional accounts. Using the backdoor for lateral movement, they exfiltrate 48 GB of user credential and payment token data to a Tor exit node.

**Learning objective:** Identify the **CI/CD pipeline compromise as the root cause**, not the downstream credential stuffing. The attack chain follows a specific pattern: supply chain entry → credential harvesting → lateral movement → data exfiltration. The agent must filter routine security noise (weekly compliance scan, dev SSL cert) and escalate to CTO due to confirmed data breach. Writing a postmortem identifying the correct root cause is critical.

**Difficulty:** Expert — 11 alerts (2 noise), cascading over 5 steps. Requires understanding of attack chains and supply chain security. Tight SLA timers (6 steps for P1 alerts) create pressure. The CI/CD alert may not be immediately obvious as the root cause since the credential stuffing is more "dramatic."

---

## Difficulty Calibration

| Task | Alerts | Noise | Cascading Steps | Max Steps | Root Cause Complexity |
|------|--------|-------|-----------------|-----------|----------------------|
| GitHub DB Failover | 4 | 0 | 2 | 15 | Low — network interruption |
| Fastly CDN Outage | 8 | 1 | 4 | 25 | Medium — config bug trigger |
| AWS Network Partition | 15 | 3 | 7 | 45 | High — hardware fault cascade |
| SolarWinds Supply Chain | 11 | 2 | 5 | 35 | Expert — attack chain analysis |
