"""The `studbook-agent` command.

studbook-agent index           build the index and print what it holds
studbook-agent ask "question"  answer one question, with citations
studbook-agent search "words"  run one search, no model
studbook-agent mcp             serve the agent to other agents over MCP (stdio)
"""

import argparse
import json
import sys

from studbook_agent.graph import ask, corpus_path, load_index


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(prog="studbook-agent", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("index", help="build the index and print what it holds")
    ask_cmd = sub.add_parser("ask", help="answer one question")
    ask_cmd.add_argument("question")
    ask_cmd.add_argument("--json", action="store_true", help="print the whole result as JSON")
    search = sub.add_parser("search", help="run one search without a model")
    search.add_argument("query")
    search.add_argument("--repo")
    sub.add_parser("mcp", help="serve over MCP on stdio")
    args = parser.parse_args(argv)

    if args.command == "index":
        index = load_index()
        print(f"{corpus_path()}: {len(index.sections)} sections")
        for repo, count in sorted(index.repos().items()):
            print(f"  {repo}: {count}")
        return 0
    if args.command == "search":
        for section, score in load_index().search(args.query, repo=args.repo):
            print(f"{score:6.1f}  {section.id}\n        {section.heading}")
        return 0
    if args.command == "mcp":
        from studbook_agent.mcp_server import server

        server().run("stdio")
        return 0
    result = ask(args.question)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    print(result["answer"])
    for number, citation in enumerate(result["citations"], start=1):
        print(f"  [{number}] {citation['repo']}/{citation['path']} ({citation['heading']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
