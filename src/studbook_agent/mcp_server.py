"""The agent as an MCP server, so a coding agent can ask the record before it changes code.

Two tools: `ask_record` runs the whole agent and returns a cited answer; `search_record` is the
cheap keyword search with no model call, for an agent that wants to read for itself.
"""

from typing import Any

from mcp.server.mcpserver import MCPServer

from studbook_agent.graph import ask, load_index

INSTRUCTIONS = (
    "Answers questions about why the team made its engineering decisions, citing the decision "
    "records, specs, plans and retrospectives. Ask before changing something whose reason "
    "you do not know. Answers starting 'Not in the record' mean the record is silent."
)


def server() -> MCPServer:
    """The configured server."""
    mcp = MCPServer(name="studbook", instructions=INSTRUCTIONS)

    @mcp.tool()
    def ask_record(question: str) -> dict[str, Any]:
        """Answer a question about the engineering record, citing the sections relied on."""
        return ask(question)

    @mcp.tool()
    def search_record(query: str, repo: str | None = None) -> list[dict[str, Any]]:
        """Keyword search over the record; returns section ids, headings and snippets."""
        return [
            {
                "id": section.id,
                "repo": section.repo,
                "path": section.path,
                "heading": section.heading,
                "snippet": " ".join(section.text.split())[:400],
                "score": round(score, 2),
            }
            for section, score in load_index().search(query, repo=repo)
        ]

    return mcp
