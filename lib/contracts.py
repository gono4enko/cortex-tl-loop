"""Task contract rendering from YAML/Jinja2."""
from __future__ import annotations
import yaml, os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent.parent / "contracts"


def render_contract(template_name: str, context: dict) -> str:
    """Render a Jinja2 template with context."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template(template_name)
    return template.render(**context)


def parse_wave_plan(yaml_text: str) -> dict:
    """Parse wave_plan YAML into dict."""
    return yaml.safe_load(yaml_text)


def validate_wave_plan(plan: dict) -> list[str]:
    """Validate wave plan. Returns list of errors (empty = valid)."""
    errors = []
    tasks = plan.get("tasks", [])
    all_files = {}
    for task in tasks:
        for f in task.get("touched_files", []):
            if f in all_files:
                errors.append(f"File collision: '{f}' touched by both '{task['id']}' and '{all_files[f]}'")
            all_files[f] = task["id"]
    return errors
