# Studbook agent

**Ask why a project was built the way it was, and get an answer that quotes the project's own
records, or an honest "Not in the record".**

Every project I build leaves a written trail: design notes, decision records, change briefs,
retrospectives. The answer to "why did we do it this way?" is usually in there, spread across
files and repositories. This agent reads that trail for me. It searches the records, reads what
it finds, searches again if the first pass was not enough, and answers with numbered citations
back to the exact section. If the records do not say, it refuses instead of guessing.

It is the second agent measured with [Flywheel](https://github.com/muhibm1/flywheel), my
LangSmith regression gate. It also serves its answers to other agents over MCP (the Model
Context Protocol, a standard way for one agent to call another's tools).

## What it covers

The default corpus is the published snapshots of five of my projects: AgentOps (an
incident-response agent), WorkHorse (a delivery workflow for coding agents), Studbook (the
original single-pass version of this idea), Paddock (WorkHorse's desktop app) and this
portfolio site. That is 1,052 sections of Markdown. Point it at your own clones with a corpus
file (see `corpus.example.toml`) to cover private repositories too.

## How it works

It is a LangGraph graph with three nodes:

1. **research** lets the model call two tools: `search` (ranked keyword search over the records,
   optionally limited to one repository or one kind of document) and `read` (the full text of
   one section). It may search up to 6 rounds.
2. **tools** runs those calls. The round limit is enforced in code, not in the prompt.
3. **answer** writes the reply. Every citation must name a section the agent was actually shown
   during this question. If it cites anything else, the answer is rejected and retried once; if
   it fails again, the agent refuses. So a citation can be wrong about what a section *means*,
   but never points at a section the agent did not read.

The search index is BM25 (the standard keyword-ranking formula), built locally with no external
service: headings count three times, `snake_case` names are split into words, and common word
endings are stripped. Documents are split at their second- and third-level headings, capped at
600 words a section.

The model is Claude Sonnet 5.5 by default, or Claude Haiku 4.5 with `STUDBOOK_DEV=1`, through
`langchain-anthropic`. `STUDBOOK_MODEL` overrides both.

## How good it is

Measured on 2026-10-13 with Flywheel on Claude Haiku 4.5: 36 questions, each asked 3 times.
The questions are of four kinds. "Decision" questions ask why something was chosen. "Factual"
questions ask what a record states. "Cross-document" questions need two records together.
"Unanswerable" questions sound plausible but the records do not answer them; the right reply is
a refusal.

| Check | Result |
|---|---|
| Answer judged correct against the reference (a model judge) | 95 of 108 runs |
| Cited the section that holds the answer | 99 of 108 |
| Refused exactly when it should | 108 of 108 |

By kind of question, correct answers were: decision 41 of 42, factual 24 of 30, cross-document
12 of 18, unanswerable 18 of 18. Cross-document questions are the weak spot.

## A change the gate stopped

The obvious fix for the cross-document weakness was a prompt paragraph telling the agent how to
compare two records. I tried it. On averages it looked like a small dip that could be noise:
correct answers went from 95 to 91 of 108.

Flywheel compares question by question, and showed something different. The new paragraph
**fixed 3 questions completely** (0 of 3 runs right before, 3 of 3 after) and **broke 5**: three
went from 3 of 3 to 0 of 3, one from 2 of 3 to 0 of 3, and one from 3 of 3 to 1 of 3. One broken question was
unanswerable: the agent started inventing which paging service feeds alerts into AgentOps,
instead of refusing. A wrong answer delivered with confidence is the failure this agent exists to
avoid. The gate blocked the change and I kept the original prompt. The report is in
[docs/results/comparison-prompt-2026-10-13.md](docs/results/comparison-prompt-2026-10-13.md).

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt && pip install --no-deps -e .
sh scripts/fetch_public_corpus.sh          # clones the five public snapshots into ./corpus
export ANTHROPIC_API_KEY=...               # your key
studbook-agent index                        # what the index holds
studbook-agent search "approval interrupt"  # one search, no model
studbook-agent ask "Why does AgentOps stop for a human before it acts?"
```

**As a LangGraph server.** `langgraph dev` serves the graph as the `studbook` assistant, with
LangGraph Studio for stepping through a run:

```bash
langgraph dev
curl -X POST localhost:2024/runs/wait -H 'content-type: application/json' \
  -d '{"assistant_id":"studbook","input":{"question":"Why does Studbook refuse instead of guessing?"}}'
```

`langgraph.json` also builds the deployable image, fetching the public corpus at build time.
It has not been deployed to LangSmith's hosted platform: that needs LangSmith Deployment
enabled on the account's plan.

**For other agents, over MCP.** `studbook-agent mcp` serves two tools on standard input and
output: `ask_record` (the full agent) and `search_record` (one search, no model call). Add it to
any MCP client:

```json
{ "mcpServers": { "studbook": { "command": "studbook-agent", "args": ["mcp"] } } }
```

**Measure a change.** From `flywheel/`, with [Flywheel](https://github.com/muhibm1/flywheel)
installed:

```bash
STUDBOOK_DEV=1 STUDBOOK_JUDGE=1 flywheel run --backend langsmith --repetitions 3 --label base --out base.json
# make the change, then the same command with --label head --out head.json
flywheel gate --base base.json --head head.json
```

## Repository

| Path | What it is |
|---|---|
| `src/studbook_agent/graph.py` | The graph, the round limit, citation checking and refusal |
| `src/studbook_agent/index.py` | The keyword index |
| `src/studbook_agent/corpus.py` | Reading repositories into sections; what is never indexed |
| `src/studbook_agent/prompts.py` | The two prompts |
| `src/studbook_agent/mcp_server.py` | The MCP server |
| `flywheel/` | The 36 questions, the checks and the Flywheel config |
| `tests/` | Tests with a scripted model; no key needed |

Tests: `pytest`. Lint: `ruff check . && ruff format --check .`.

## Limits

- Keyword search misses a question worded very differently from the record. The agent can search
  again with other words, which helps, but it is not semantic search.
- The answer judge is itself a model (Claude Haiku 4.5). Its verdicts have not been audited by a
  person.
- 36 questions is enough to catch a change that breaks several of them, not to rank close
  versions.

MIT licensed.
