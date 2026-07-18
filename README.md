# Hermes Cortex

Autonomous AI Development Agency Orchestrator.
Team Lead: GLM-5.2. 8-phase workflow.

## Quick Start
```bash
cd /home/hermes/cortex
pm2 start ecosystem.cortex.config.js
pm2 save
curl http://localhost:9015/health
```

## Architecture
- Port: 9015
- State: cortex.db (SQLite WAL)
- Kanban: localhost:9011

## Waves
0. Foundation (current)
1. INGEST + DISPATCH
2. PLAN + EXECUTE
3. VERIFY + REVIEW
4. MERGE + KB-WRITE
5. Recovery & Stability
6. Research Agent
7. Reporting
8. Scaling
