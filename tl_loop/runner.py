"""Agent Runner — all runner types."""
from __future__ import annotations
import subprocess, tempfile, os, logging, json
from cortex.tl_loop.schema import Task, Runner

logger = logging.getLogger(__name__)


class KiloRunner:
    """Kilo CLI on server."""
    name = "kilo-hermes"

    def run(self, task: Task) -> dict:
        contract = self._build_contract(task)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(contract)
            contract_path = f.name
        try:
            result = subprocess.run(
                ["kilo", "run", "--prompt", contract],
                capture_output=True, text=True, timeout=1800,
                cwd="/home/hermes",
                env={**os.environ, "NO_COLOR": "1"},
            )
            return {"ok": result.returncode == 0, "exit_code": result.returncode,
                    "stdout": result.stdout[-10000:], "stderr": result.stderr[-5000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            try: os.unlink(contract_path)
            except: pass

    def cancel(self, task_id: str) -> bool:
        return True

    def _build_contract(self, task: Task) -> str:
        return f"""# Task: {task.id}
## Objective
{task.body or task.title}
## Project: {task.project_id}
## Priority: {task.priority}
## Verification: {task.verify_cmd or 'pytest tests/ -v --tb=short'}
## Rules
- Write code, run tests, commit
- Do NOT touch .env, secrets, ecosystem.config.js
"""


class HermesOpenCodeRunner:
    """OpenCode on hermes-assistant server."""
    name = "hermes-opencode"

    def run(self, task: Task) -> dict:
        contract = f"Task: {task.title}\n{task.body or ''}\nProject: {task.project_id or 'hermes'}\nVerify: {task.verify_cmd or 'pytest'}"
        try:
            result = subprocess.run(
                ["opencode", "run", "--prompt", contract, "--model", "deepseek/deepseek-v4-flash"],
                capture_output=True, text=True, timeout=3600,
                cwd=f"/home/hermes/{task.project_id}" if task.project_id else "/home/hermes",
                env={**os.environ, "NO_COLOR": "1"},
            )
            return {"ok": result.returncode == 0, "exit_code": result.returncode,
                    "stdout": result.stdout[-10000:], "stderr": result.stderr[-5000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout (1h)"}
        except FileNotFoundError:
            return {"ok": False, "error": "opencode not installed"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def cancel(self, task_id: str) -> bool:
        return True


class MacOpenCodeRunner:
    """OpenCode on MacBook via SSH."""
    name = "mac-opencode"

    def run(self, task: Task) -> dict:
        contract = f"Task: {task.title}\n{task.body or ''}\nProject: {task.project_id or 'hermes'}\nVerify: {task.verify_cmd or 'pytest'}"
        try:
            result = subprocess.run(
                ["ssh", "mac",
                 f"cd ~/code/{task.project_id or 'hermes'} && opencode run --prompt '{contract[:2000]}' --model deepseek/deepseek-v4-flash"],
                capture_output=True, text=True, timeout=3600,
            )
            return {"ok": result.returncode == 0, "exit_code": result.returncode,
                    "stdout": result.stdout[-5000:], "stderr": result.stderr[-5000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def cancel(self, task_id: str) -> bool:
        try:
            subprocess.run(["ssh", "mac", "pkill -f 'opencode run'"], timeout=10)
        except:
            pass
        return True


# Registry — which runner for which agent
RUNNERS = {
    "kilo-hermes": KiloRunner(),
    "hermes-opencode": HermesOpenCodeRunner(),
    "mac-opencode": MacOpenCodeRunner(),
}


def get_runner(name: str):
    return RUNNERS.get(name, KiloRunner())
