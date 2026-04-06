"""
FastAPI application for the Incident Commander Environment.

This module creates an HTTP server that exposes the IncidentCommanderEnvironment
over HTTP and WebSocket endpoints, compatible with MCPToolClient.

Usage:
    # Development:
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000
"""

try:
    from openenv.core.env_server.http_server import create_app
    from openenv.core.env_server.mcp_types import CallToolAction, CallToolObservation

    from .environment import IncidentCommanderEnvironment
except ImportError:
    from openenv.core.env_server.http_server import create_app
    from openenv.core.env_server.mcp_types import CallToolAction, CallToolObservation
    from incident_commander_env.server.environment import IncidentCommanderEnvironment

# Create the app with MCP types
app = create_app(
    IncidentCommanderEnvironment,
    CallToolAction,
    CallToolObservation,
    env_name="incident_commander_env",
)


def main():
    """Entry point for direct execution."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
