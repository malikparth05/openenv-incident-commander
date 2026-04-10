"""
Internal Engineering Runbooks for the Incident Commander Environment.

Agents use the `search_runbooks` tool to query this knowledge base
in order to determine the correct teams to assign, SLAs, or mitigation steps.
"""

RUNBOOKS = [
    {
        "title": "Database Failover & Replication",
        "keywords": [
            "database", "mysql", "postgresql", "connection pool", "replica", "replication",
            "postgres", "failover", "orchestrator", "divergence", "data integrity",
        ],
        "content": (
            "RUNBOOK: Database Failover & Replication\\n"
            "Owner Team: 'database'\\n"
            "SLA: P1 if primary is unreachable or data divergence detected; P2 for replica lag.\\n"
            "Symptom: Unintended failover after network interruption.\\n"
            "ROOT CAUSE PATTERN: If orchestrator triggered failover due to network blip "
            "(not actual DB failure), the ROOT CAUSE is the network interruption — not the DB.\\n"
            "Key: Check if the original primary was actually healthy. If yes, don't restart DB — "
            "fix the network and reconcile data row-by-row to prevent data loss.\\n"
            "Action plan: (1) Identify which writes diverged, (2) halt writes to both sides, "
            "(3) reconcile data before promoting one side."
        )
    },
    {
        "title": "CDN / Edge Cache Failures",
        "keywords": [
            "cdn", "edge", "cache", "varnish", "503", "config", "pop", "origin",
            "thundering herd", "cache miss", "cdn_edge", "ssl_termination",
        ],
        "content": (
            "RUNBOOK: CDN Edge Failure\\n"
            "Owner Team: 'platform'\\n"
            "SLA: P1 if >50% of PoPs are affected.\\n"
            "Symptom: Edge nodes returning 503, cache hit ratio collapsing.\\n"
            "ROOT CAUSE PATTERN: If crash correlates with a config push, the root cause "
            "is the config change triggering a latent bug — NOT infrastructure failure.\\n"
            "Action plan: (1) Identify and revert the triggering config, (2) restart affected "
            "edge nodes AFTER reverting config (they will crash again on startup otherwise), "
            "(3) monitor origin server load (thundering herd from cache miss storm).\\n"
            "Note: Origin traffic surge is a SYMPTOM — it resolves when CDN is back online."
        )
    },
    {
        "title": "Network Fabric Partitions & Hardware",
        "keywords": [
            "network", "switch", "fabric", "partition", "bgp", "connectivity",
            "az", "availability zone", "ebs", "stuck", "asic",
        ],
        "content": (
            "RUNBOOK: Core Switch / Network Partition\\n"
            "Owner Team: 'network'\\n"
            "SLA: P1 (Critical Issue).\\n"
            "Symptom: BGP sessions flapping, AZ isolation, cross-zone communication failure.\\n"
            "ROOT CAUSE PATTERN: If multiple services in the same AZ fail simultaneously, "
            "look for a core switch or interconnect failure FIRST.\\n"
            "Action plan: (1) Check ASIC health on suspected switch, (2) isolate the switch "
            "to force redundant path routing, (3) engage vendor for RMA if hardware fault.\\n"
            "Note: Network partitions cause cascading failures in Kubernetes, EBS, Databases, "
            "and Storage. Fix the network — don't restart individual services."
        )
    },
    {
        "title": "Kubernetes Cluster Health",
        "keywords": [
            "kubernetes", "node", "notready", "eviction", "pod", "hpa", "autoscaler",
            "kubelet", "worker",
        ],
        "content": (
            "RUNBOOK: Kubernetes Node Troubleshooting\\n"
            "Owner Team: 'infrastructure'\\n"
            "SLA: P2 for partial node loss if HPA can compensate.\\n"
            "Symptom: Nodes in NotReady state, pod evictions.\\n"
            "Note: If NotReady correlates with network alerts, it is likely kubelet lost "
            "connection to the control plane. Do NOT restart nodes — fix the network. "
            "HPA scale-up events are expected noise during pod evictions."
        )
    },
    {
        "title": "Authentication & Identity Management",
        "keywords": [
            "auth", "authentication", "identity", "login", "ssl", "certificate",
            "ldap", "idp",
        ],
        "content": (
            "RUNBOOK: Authentication Service & Secrets\\n"
            "Owner Team: 'security'\\n"
            "SLA: P1 for production login failures, P4 for staging/dev certificate warnings.\\n"
            "Symptom: 50% login failures usually indicate half the fleet can't reach IdP.\\n"
            "Cert warnings require ticket creation but NOT immediate escalation unless "
            "expiring in < 24 hours."
        )
    },
    {
        "title": "Supply Chain & Security Breach Response",
        "keywords": [
            "brute force", "credential stuffing", "data exfiltration", "waf", "sql injection",
            "oauth", "token", "tor", "cdn", "cache purge", "security breach", "attack",
            "intrusion", "unauthorized", "suspicious", "rate limit", "bot", "scanner",
            "supply chain", "ci/cd", "pipeline", "backdoor", "c2", "lateral movement",
            "solarwinds", "reverse shell", "ids", "siem",
        ],
        "content": (
            "RUNBOOK: Active Security Breach / Supply Chain Attack\\n"
            "Owner Team: 'security'\\n"
            "Escalation: CTO REQUIRED for any confirmed data exfiltration, credential "
            "compromise at scale, or supply chain compromise.\\n"
            "ROOT CAUSE PATTERN: In supply chain attacks, the CI/CD pipeline or build artifact "
            "compromise is the ENTRY POINT — credential stuffing and WAF alerts are PHASE 2.\\n"
            "Alert correlation: build artifact modification → credential harvesting → lateral "
            "movement via backdoor → data exfiltration. This is ONE attack chain.\\n"
            "Noise to filter: Scheduled security scans (P4) and dev/staging SSL certs (P4).\\n"
            "Response order: (1) Investigate CI/CD alert FIRST (supply chain entry), "
            "(2) block attacker IPs at WAF, (3) revoke compromised OAuth tokens, "
            "(4) quarantine hosts running backdoored software, (5) escalate to CTO, "
            "(6) send stakeholder update, (7) write postmortem naming the CI/CD alert as root cause."
        )
    },
    {
        "title": "Backend Service Reliability",
        "keywords": [
            "application", "user_service", "order_service", "frontend", "deployment",
            "timeout", "payment", "api_gateway",
        ],
        "content": (
            "RUNBOOK: Microservice Degradation\\n"
            "Owner Team: 'application'\\n"
            "SLA: P1 if revenue-impacting (e.g. payment_service). P3/P4 for minor errors.\\n"
            "Note: Frontend/API errors are almost always symptoms of backend issues "
            "or upstream infrastructure failures (database, network). "
            "Look for root causes before restarting backend pods."
        )
    },
    {
        "title": "Data Center Interconnect & Cross-DC Communication",
        "keywords": [
            "interconnect", "dc", "data center", "cross-dc", "optical", "bgp", "100g",
            "maintenance", "network_interconnect",
        ],
        "content": (
            "RUNBOOK: DC Interconnect Maintenance & Failures\\n"
            "Owner Team: 'network'\\n"
            "SLA: P1 if cross-DC connectivity is lost.\\n"
            "Symptom: BGP sessions torn down, cross-DC traffic interrupted.\\n"
            "CRITICAL: If database orchestrator triggers failover during a brief network "
            "interruption, the root cause is the NETWORK INTERRUPTION, not the database. "
            "The orchestrator's timeout threshold was exceeded, causing an unintended failover.\\n"
            "Action plan: (1) Verify physical link status, (2) check if orchestrator "
            "triggered failover, (3) if yes, halt DB writes and begin data reconciliation."
        )
    },
]

def perform_search(query: str) -> str:
    """Perform a simple keyword search across the runbooks."""
    query_lower = query.lower()

    # Simple scoring: count how many words from query match the keywords or title
    query_words = query_lower.split()
    results = []

    for book in RUNBOOKS:
        score = 0
        text_to_search = book["title"].lower() + " " + " ".join(book["keywords"]) + " " + book["content"].lower()

        # Check direct keyword matches
        for kw in book["keywords"]:
            if kw in query_lower:
                score += 5

        # Check title matches
        if query_lower in book["title"].lower():
            score += 10

        # Word level matches
        for word in query_words:
            if len(word) > 2 and word in text_to_search:
                score += 1

        if score > 0:
            results.append((score, book["content"]))

    if not results:
        return f"No runbooks found matching '{query}'. Try searching for specific services like 'database', 'network', 'cdn', 'security', or 'kubernetes'."

    # Sort by score descending
    results.sort(key=lambda x: x[0], reverse=True)

    # Return the top 2 results to keep context length reasonable
    best_matches = [res[1] for res in results[:2]]

    ret = f"--- Found {len(results)} relevant runbooks for '{query}' ---\\n\\n"
    ret += "\\n\\n".join(best_matches)
    return ret
