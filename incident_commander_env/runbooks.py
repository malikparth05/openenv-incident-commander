"""
Internal Engineering Runbooks for the Incident Commander Environment.

Agents use the `search_runbooks` tool to query this knowledge base
in order to determine the correct teams to assign, SLAs, or mitigation steps.
"""

RUNBOOKS = [
    {
        "title": "API Gateway Troubleshooting",
        "keywords": ["api gateway", "503", "5xx", "gateway", "proxy"],
        "content": (
            "RUNBOOK: API Gateway Troubleshooting\\n"
            "Owner Team: 'platform'\\n"
            "SLA: P1 (Resolve within 15 mins) if affecting multiple downstream services.\\n"
            "Common causes for 5xx errors:\\n"
            "1. Port conflicts during deployment (check container logs for 'address already in use').\\n"
            "2. Upstream timeouts (if downstream services are slow, gateway drops connections).\\n"
            "Action plan: Restart crashing pods, check deployment history, rollback if necessary."
        )
    },
    {
        "title": "Database Connection Pool Exhaustion",
        "keywords": ["database", "postgresql", "connection pool", "replica", "replication", "postgres"],
        "content": (
            "RUNBOOK: PostgreSQL Connection Management\\n"
            "Owner Team: 'database'\\n"
            "SLA: P1 if primary is unresponsive; P2 if replica is lagging.\\n"
            "Symptom: Connections at 100% capacity.\\n"
            "Common causes: Stuck batch jobs holding transactions open, connection leaks in app code.\\n"
            "Action plan: Query pg_stat_activity to find stuck queries, kill conflicting backend pids, alert application teams."
        )
    },
    {
        "title": "Network Fabric Partitions & Hardware",
        "keywords": ["network", "switch", "fabric", "partition", "bgp", "connectivity"],
        "content": (
            "RUNBOOK: Core Switch / Fabric Failure\\n"
            "Owner Team: 'network'\\n"
            "SLA: P1 (Critical Issue).\\n"
            "Symptom: BGP sessions flapping, partial rack isolation, cross-rack communication failure.\\n"
            "Action plan: Verify ASIC health on suspected switch (e.g., sw-core-0x). "
            "If hardware fault, isolate the switch to force redundant path routing. Engage vendor for RMA.\\n"
            "Note: Network partitions will cause cascading failures in Kubernetes, Databases, and Storage."
        )
    },
    {
        "title": "Kubernetes Cluster Health",
        "keywords": ["kubernetes", "node", "notready", "eviction", "pod", "hpa", "autoscaler"],
        "content": (
            "RUNBOOK: Kubernetes Node Troubleshooting\\n"
            "Owner Team: 'infrastructure'\\n"
            "SLA: P2 for partial node loss if HPA can compensate.\\n"
            "Symptom: Nodes in NotReady state.\\n"
            "Note: If NotReady correlates with network alerts, it is likely the kubelet lost connection to the control plane. "
            "Do NOT restart the nodes; fix the network. HPA scale-up events are expected noise during pod evictions."
        )
    },
    {
        "title": "Authentication & Identity Management",
        "keywords": ["auth", "authentication", "identity", "login", "ssl", "certificate"],
        "content": (
            "RUNBOOK: Authentication Service & Secrets\\n"
            "Owner Team: 'security'\\n"
            "SLA: P1 for production login failures. P4 for staging certificate warnings.\\n"
            "Symptom: 50% login failures usually indicate half the fleet cannot reach the LDAP/IdP server. "
            "Cert warnings require ticket creation but not immediate escalation unless expiring in < 24h."
        )
    },
    {
        "title": "Backend Service Reliability",
        "keywords": ["application", "user_service", "order_service", "frontend", "deployment", "timeout"],
        "content": (
            "RUNBOOK: Microservice Degradation\\n"
            "Owner Team: 'application'\\n"
            "SLA: P1 if revenue-impacting (e.g. order_service). P3/P4 for minor backend errors.\\n"
            "Note: Frontend errors are almost always symptoms of backend APIs timing out. "
            "Backend timeouts are often symptoms of Database or Network issues. Look for root causes before restarting backend pods."
        )
    }
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
        return f"No runbooks found matching '{query}'. Try searching for specific services like 'database', 'network', 'api gateway', or 'kubernetes'."
        
    # Sort by score descending
    results.sort(key=lambda x: x[0], reverse=True)
    
    # Return the top 2 results to keep context length reasonable
    best_matches = [res[1] for res in results[:2]]
    
    ret = f"--- Found {len(results)} relevant runbooks for '{query}' ---\\n\\n"
    ret += "\\n\\n".join(best_matches)
    return ret
