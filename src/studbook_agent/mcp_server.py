"""The agent as an MCP server, so a coding agent can ask the record before it changes code.

Three tools: `ask_record` runs the whole agent and returns a cited answer (a paid model call);
`search_record` is the keyword search and `read_record` returns one section in full, both with
no model call, for an agent that wants to read for itself. Only `ask_record` loads the graph.
"""

from typing import Any

from mcp.server.mcpserver import MCPServer

from studbook_agent import record
from studbook_agent.record import load_index

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
        from studbook_agent.graph import ask

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

    @mcp.tool()
    def read_record(section_id: str) -> dict[str, Any]:
        """One section in full by its id, or an `error` naming an id the record does not hold."""
        return record.read(section_id)

    return mcp
