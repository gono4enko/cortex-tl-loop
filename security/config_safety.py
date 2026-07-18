"""Cortex pre-task config safety gate."""
from __future__ import annotations
import json, re, subprocess
from pathlib import Path
from typing import Any

VALIDATOR = Path("/home/hermes/cortex/security/validate_config_v2.py")
CRITICAL_PATTERNS = [
    re.compile(r"kilo\.jsonc", re.I), re.compile(r"opencode\.json", re.I),
    re.compile(r"config\.ya?ml", re.I), re.compile(r"\.env\b", re.I),
    re.compile(r"ecosystem\.(config|cortex\.config)\.js", re.I),
]

def task_touches_configs(body: str, touched_files: list[str] | None = None) -> bool:
    text = body + " " + " ".join(touched_files or [])
    return any(p.search(text) for p in CRITICAL_PATTERNS)

def run_validator(file_arg: str = "--all") -> dict[str, Any]:
    try:
        out = subprocess.run(["python3", str(VALIDATOR), file_arg, "--format", "json"],
            capture_output=True, text=True, timeout=30)
        return json.loads(out.stdout) if out.stdout.strip() else {"ok":False,"errors":1,"issues":[{"severity":"ERROR","rule":"validator.runtime","message":out.stderr[:500]}]}
    except Exception as e:
        return {"ok":False,"errors":1,"issues":[{"severity":"ERROR","rule":"validator.exception","message":str(e)[:300]}]}

def pre_task_check(body: str = "", touched_files: list[str] | None = None, config_path: str | None = None) -> dict:
    touches = task_touches_configs(body, touched_files)
    if not touches and not config_path:
        return {"touches_configs":False,"ok":True,"severity":"INFO","issues":[],"fix_hints":[]}
    result = run_validator(config_path or "--all")
    errors = result.get("errors",0)
    severity = "ERROR" if errors>0 else ("WARN" if result.get("warnings",0)>0 else "INFO")
    fix_hints = [i.get("fix_hint") for i in result.get("issues",[]) if i.get("fix_hint")]
    return {"touches_configs":True,"ok":result.get("ok",False),"severity":severity,"errors":errors,"warnings":result.get("warnings",0),"issues":result.get("issues",[]),"fix_hints":fix_hints,"fixes_applied":result.get("fixes_applied",[])}
