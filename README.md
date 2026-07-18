# Cortex TL Loop

AI coding agency orchestrator. Task conveyor with 3-runner execution, 2-tier review, expert council, cost tracking, and ChromaDB knowledge base.

## Pipeline

```
NEW → PLANNING → READY → DISPATCHED → RUNNING → VERIFYING → REVIEWING → MERGING → DONE
```

13 statuses, state machine in `tl_loop/schema.py`.

## Architecture

| Module | Role |
|--------|------|
| `tl_loop/loop.py` | Orchestrator: gather → dispatch → verify → review → merge → KB + ChromaDB |
| `tl_loop/verify_gate.py` | ruff + pytest real subprocess |
| `tl_loop/reviewer.py` | T1: DeepSeek V4 Flash checklist, T2: Qwen3-235B architectural |
| `tl_loop/council.py` | 3-expert council: GLM-5.2 + Claude Fable-5 + DeepSeek V4 Pro |
| `tl_loop/cost_tracker.py` | Per-task token cost tracking (cost_log.db) |
| `tl_loop/runner.py` | 3 runners: kilo-hermes, hermes-opencode, mac-opencode (SSH) |
| `tl_loop/mcp.py` | Adapters: Firecrawl, GitHub, Context7, Serena |
| `tl_loop/wave_planner.py` | Parallel wave DAG validator |
| `tl_loop/reporter.py` | Daily Telegram + weekly email digest |
| `phases/` | 8 phase modules: ingest, plan, dispatch, execute, verify, review, merge, kb_write |

## Models

- DeepSeek V4 Flash — T1 review (fast, cheap)
- Qwen3-235B-A22B — T2 review (architectural)
- GLM-5.2 — Expert council (system architect)
- Claude Fable-5 — Expert council (strategist)
- DeepSeek V4 Pro — Expert council + synthesis

## Server

- **Host:** hermes-assistant (155.212.228.160)
- **PM2:** cortex-orchestrator, cortex-runner-kilo, cortex-tl-loop, hermes-cortex
- **Tick:** every 5 minutes
- **State:** cortex.db + tl_loop_state.db (SQLite WAL)
- **ChromaDB:** /home/hermes/.chroma_cortex (persistent)

## Recovery

```bash
git clone https://github.com/gono4enko/cortex-tl-loop.git /home/hermes/cortex
cd /home/hermes/cortex
pip install -r requirements.txt
pm2 start tl_loop/main.py --name cortex-orchestrator --interpreter python3
pm2 start agent_runner.py --name cortex-runner-kilo --interpreter python3
```

## Requirements

- Python 3.12+
- chromadb, requests, httpx
- DeepSeek API key (DEEPSEEK_API_KEY env)
- DeepInfra API key (DEEPINFRA_API_KEY env)
