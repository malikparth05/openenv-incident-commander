"""
Incident Commander Environment Client.

This module provides the client for connecting to an Incident Commander server.
IncidentCommanderEnv extends MCPToolClient to provide tool-calling style interactions.

Example:
    >>> with IncidentCommanderEnv(base_url="http://localhost:8000") as env:
    ...     env.reset()
    ...     tools = env.list_tools()
    ...     result = env.call_tool("acknowledge_alert", alert_id="alert-001")
    ...     result = env.call_tool("set_priority", alert_id="alert-001", priority="P1")
    ...     result = env.call_tool("assign_team", alert_id="alert-001", team="platform")

Example with Docker:
    >>> env = await IncidentCommanderEnv.from_docker_image("incident-commander-env:latest")
    >>> try:
    ...     await env.reset()
    ...     tools = await env.list_tools()
    ...     result = await env.call_tool("acknowledge_alert", alert_id="alert-001")
    ... finally:
    ...     await env.close()
"""

from openenv.core.mcp_client import MCPToolClient


class IncidentCommanderEnv(MCPToolClient):
    """
    Client for the Incident Commander Environment.

    Inherits all functionality from MCPToolClient:
    - list_tools(): Discover available tools
    - call_tool(name, **kwargs): Call a tool by name
    - reset(**kwargs): Reset the environment
    - step(action): Execute an action
    """

    pass  # MCPToolClient provides all needed functionality
