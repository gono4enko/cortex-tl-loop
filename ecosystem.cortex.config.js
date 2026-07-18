module.exports = {
  apps: [{
    name: "hermes-cortex",
    script: "/home/hermes/cortex/orchestrator.py",
    interpreter: "/home/hermes/.hermes-venv/bin/python",
    cwd: "/home/hermes/cortex",
    env: {
      CORTEX_PORT: "9015",
      CORTEX_DB_PATH: "/home/hermes/cortex/cortex.db",
      KANBAN_URL: "http://localhost:9011",
    },
    max_memory_restart: "1500M",
    autorestart: true,
    max_restarts: 10,
    min_uptime: "30s",
    restart_delay: 5000,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "/home/hermes/cortex/logs/error.log",
    out_file: "/home/hermes/cortex/logs/output.log",
    merge_logs: true,
  }]
};

// TL Orchestration Loop
module.exports.apps.push({
  name: "cortex-tl-loop",
  script: "/home/hermes/cortex/tl_loop/main.py",
  interpreter: "/home/hermes/.hermes-venv/bin/python",
  cwd: "/home/hermes/cortex",
  env: {
    TL_LOOP_INTERVAL: "300",
    DAILY_COST_LIMIT_USD: "70",
    CORTEX_PORT: "9015",
  },
  max_memory_restart: "500M",
  autorestart: true,
  restart_delay: 10000,
  log_date_format: "YYYY-MM-DD HH:mm:ss",
  error_file: "/home/hermes/cortex/logs/tl-loop-error.log",
  out_file: "/home/hermes/cortex/logs/tl-loop-output.log",
  merge_logs: true,
});
