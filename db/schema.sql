-- Hermes Cortex: State Database Schema
-- SQLite WAL mode

PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS cortex_tasks (
    id TEXT PRIMARY KEY,                    -- unique task id (cortex-YYYYMMDD-NNN)
    title TEXT NOT NULL,
    body TEXT,                              -- full task description
    project_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ingest',  -- ingest|planning|ready|in_progress|verify|review|merge|done|failed|blocked|stuck
    phase TEXT NOT NULL DEFAULT 'ingest',   -- current 8-phase stage
    priority INTEGER DEFAULT 3,             -- 1=low, 5=critical
    wave_id TEXT,                           -- FK to waves
    executor_agent TEXT,                    -- mac-opencode|mac-kilo|kilo-hermes|hermes-opencode|hermes-bot
    touched_files TEXT DEFAULT '[]',        -- JSON array of file paths
    forbidden_files TEXT DEFAULT '[]',
    acceptance_criteria TEXT DEFAULT '[]',
    verify_command TEXT,
    git_branch TEXT,
    artifact_uri TEXT,
    diary_path TEXT,
    complexity TEXT DEFAULT 'low',          -- low|med|high
    cost_estimate REAL DEFAULT 0,
    needs_human INTEGER DEFAULT 0,          -- 0|1 — requires human approval for destructive ops
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3
);

CREATE TABLE IF NOT EXISTS waves (
    id TEXT PRIMARY KEY,                    -- wave-YYYYMMDD-NN
    project_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',          -- pending|in_progress|completed|failed
    plan_yaml TEXT,                         -- full wave_plan.yaml content
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES cortex_tasks(id),
    agent TEXT NOT NULL,
    assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    exit_code INTEGER,
    stdout_path TEXT,
    stderr_path TEXT
);

CREATE TABLE IF NOT EXISTS heartbeats (
    agent TEXT PRIMARY KEY,
    last_seen TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT DEFAULT 'alive',            -- alive|stale|dead
    current_task_id TEXT,
    cpu_percent REAL,
    mem_mb REAL
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES cortex_tasks(id),
    tier TEXT NOT NULL,                     -- t1|t2
    reviewer_model TEXT,
    passed INTEGER NOT NULL DEFAULT 0,
    complexity TEXT,
    checklist_json TEXT,                    -- 10 boolean items
    notes TEXT,
    reviewed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS kb_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES cortex_tasks(id),
    obsidian_path TEXT,                     -- path in Obsidian KB
    chroma_id TEXT,                         -- ChromaDB chunk id
    ledger_id TEXT,                         -- ledger entry id
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cost_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    provider TEXT,                          -- openrouter|deepinfra|deepseek
    model TEXT,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0,
    logged_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pending_waves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wave_id TEXT NOT NULL,
    queued_at TEXT NOT NULL DEFAULT (datetime('now')),
    priority INTEGER DEFAULT 3
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON cortex_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON cortex_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_wave ON cortex_tasks(wave_id);
CREATE INDEX IF NOT EXISTS idx_waves_status ON waves(status);
CREATE INDEX IF NOT EXISTS idx_assignments_task ON assignments(task_id);
CREATE INDEX IF NOT EXISTS idx_heartbeats_agent ON heartbeats(agent);
CREATE INDEX IF NOT EXISTS idx_reviews_task ON reviews(task_id);
CREATE INDEX IF NOT EXISTS idx_cost_task ON cost_log(task_id);

-- TL Loop events table
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    type TEXT,
    payload TEXT,
    ts TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
