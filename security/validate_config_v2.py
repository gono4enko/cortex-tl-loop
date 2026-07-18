#!/usr/bin/env python3
"""Config safety validator v2 — Kilo/OpenCode/Hermes/Cortex (Mac+Server)."""
from __future__ import annotations
import argparse, json, os, re, stat, sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable

try:
    import yaml
    HAVE_YAML = True
except Exception:
    HAVE_YAML = False

HOME = Path.home()

DEFAULT_TARGETS: list[Path] = [
    HOME / ".config/kilo/kilo.jsonc",
    HOME / ".config/opencode/opencode.json",
    HOME / ".hermes/config.yaml",
    HOME / ".hermes/.env",
    HOME / "hermes-assistant/.env",
    HOME / "cortex/.env",
    HOME / "cortex/ecosystem.cortex.config.js",
]

KNOWN_PROVIDER_KEYS = {
    "openai-compatible": ["baseUrl","apiKey"], "openai": ["apiKey"],
    "ollama": ["baseUrl"], "mistral": ["apiKey"], "gemini": ["apiKey"],
    "vercel-ai-gateway": ["apiKey"], "voyage": ["apiKey"],
    "openrouter": ["apiKey","specificProvider"], "aws-bedrock": ["apiKey"],
}

CAMEL_MAP = {"openaiCompatible":"openai-compatible","vercelAiGateway":"vercel-ai-gateway","awsBedrock":"aws-bedrock"}

SECRET_PATTERNS = [
    ("deepseek", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("deepinfra", re.compile(r"IF[0-9A-Za-z]{16,}")),
    ("openai", re.compile(r"sk-[A-Za-zA-Z0-9]{40,}")),
]

CRITICAL_ENV_KEYS = {"DEEPSEEK_API_KEY","DEEPINFRA_API_KEY","OPENAI_API_KEY","SMTP_PASS","GITHUB_PERSONAL_ACCESS_TOKEN","JINA_API_KEY","FIRECRAWL_API_KEY"}

@dataclass
class Issue:
    severity: str; file: str; rule: str; message: str; fix_hint: str = ""

def strip_jsonc(text: str) -> str:
    out = []
    for line in text.split("\n"):
        in_s, i, res = False, 0, []
        while i < len(line):
            c = line[i]
            if c == '"' and (i==0 or line[i-1]!="\\"): in_s = not in_s; res.append('"')
            elif not in_s and line[i:i+2] == "//": break
            else: res.append(c)
            i += 1
        out.append("".join(res))
    return "\n".join(out)

def load_jsonc(p: Path):
    try: return json.loads(strip_jsonc(p.read_text())), None
    except Exception as e: return None, f"invalid JSONC: {e}"

def load_json(p: Path):
    try: return json.loads(p.read_text()), None
    except Exception as e: return None, f"invalid JSON: {e}"

def load_yaml(p: Path):
    if not HAVE_YAML: return None, "yaml unavailable"
    try: return yaml.safe_load(p.read_text()) or {}, None
    except Exception as e: return None, f"invalid YAML: {e}"

def load_dotenv(p: Path):
    data = {}
    try:
        for ln in p.read_text().splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"): continue
            if "=" in ln:
                k, v = ln.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
        return data, None
    except Exception as e: return None, f"dotenv error: {e}"

def load_ecosystem_js(p: Path):
    try:
        text = p.read_text()
        apps = []
        for m in re.finditer(r"name:\s*[\"']([^\"']+)[\"']", text):
            window = text[max(0,m.start()-200):m.start()+1500]
            ports = [int(x) for x in re.findall(r"(?:--port\s+|port:\s*)(\d{2,5})", window)]
            apps.append({"name": m.group(1), "ports": ports})
        return {"apps": apps}, None
    except Exception as e: return None, f"ecosystem parse error: {e}"

LOADER = {".jsonc":load_jsonc,".json":load_json,".yaml":load_yaml,".yml":load_yaml,".env":load_dotenv,".js":load_ecosystem_js}

def check_indexing(cfg, fn):
    out = []
    if "indexing" not in cfg:
        return [Issue("WARN",fn,"indexing.missing","no indexing block","add indexing {enabled,provider,vectorStore,...}")]
    idx = cfg["indexing"]
    if not idx.get("enabled"): out.append(Issue("WARN",fn,"indexing.disabled","enabled is not true"))
    p = idx.get("provider")
    if not p: out.append(Issue("ERROR",fn,"indexing.provider","provider missing"))
    elif p not in KNOWN_PROVIDER_KEYS: out.append(Issue("ERROR",fn,"indexing.provider.unknown",f"unknown provider '{p}'"))
    vs = idx.get("vectorStore")
    if not vs: out.append(Issue("ERROR",fn,"indexing.vectorStore","vectorStore missing"))
    if p and p not in idx: out.append(Issue("ERROR",fn,"indexing.provider_block",f"missing '{p}' block",f'add "{p}": {{baseUrl,apiKey}}'))
    for w, c in CAMEL_MAP.items():
        if w in idx: out.append(Issue("ERROR",fn,"indexing.camelCase",f"'{w}'→'{c}' (hyphens)",f"rename to \"{c}\""))
    if vs and vs not in idx: out.append(Issue("ERROR",fn,"indexing.vs_block",f"missing '{vs}' block",f'add "{vs}": {{}}'))
    return out

def check_mcp(cfg, fn):
    out = []
    for name, e in cfg.get("mcp",{}).items():
        if not isinstance(e,dict): continue
        if e.get("type")=="local":
            if isinstance(e.get("command"),str): out.append(Issue("ERROR",fn,"mcp.command_str",f"mcp.{name}.command must be array"))
            if "env" in e and "environment" not in e: out.append(Issue("ERROR",fn,"mcp.env_deprecated",f"mcp.{name}: env→environment"))
    return out

def check_secrets(cfg, fn, raw=None):
    if not raw: return []
    out = []
    for name, pat in SECRET_PATTERNS:
        if name=="generic_long_token": continue
        for _ in pat.finditer(raw): out.append(Issue("WARN",fn,f"secret.{name}",f"naked {name} key","move to .env"))
    return out

def check_dotenv(data, p, fn):
    out = []
    try:
        mode = p.stat().st_mode
        if mode & stat.S_IROTH: out.append(Issue("ERROR",fn,"dotenv.perms","world-readable","chmod 600"))
    except: pass
    for k in CRITICAL_ENV_KEYS:
        if k not in data: out.append(Issue("INFO",fn,"dotenv.missing",f"optional key: {k}"))
    for k, v in data.items():
        if v == "": out.append(Issue("WARN",fn,"dotenv.empty",f"empty: {k}"))
    return out

def check_port_conflicts(cfg, fn):
    apps, seen = cfg.get("apps",[]), {}
    out = []
    for a in apps:
        for port in a.get("ports",[]):
            if port in seen: out.append(Issue("ERROR",fn,"port.conflict",f"port {port}: '{seen[port]}' vs '{a['name']}'"))
            else: seen[port] = a["name"]
    return out

def dispatch(p: Path):
    ext, name = p.suffix.lower(), p.name
    if not p.exists(): return [Issue("INFO",str(p),"file.missing","skipped")]
    try: raw = p.read_text()
    except Exception as e: return [Issue("ERROR",str(p),"io",str(e))]
    loader = LOADER.get(ext, load_json)
    data, err = loader(p)
    if err: return [Issue("ERROR",str(p),"parse",err)]
    issues = []
    if name=="kilo.jsonc": issues += check_indexing(data,str(p)) + check_mcp(data,str(p)) + check_secrets(data,str(p),raw)
    elif name=="opencode.json": issues += check_mcp(data,str(p)) + check_secrets(data,str(p),raw)
    elif name=="config.yaml": issues += check_secrets(data,str(p),raw)
    elif name==".env": issues += check_dotenv(data,p,str(p))
    elif name.endswith("ecosystem.config.js"): issues += check_port_conflicts(data,str(p))
    return issues

def apply_fixes(p, issues):
    if not p.exists() or p.suffix not in (".jsonc",".json"): return []
    try: raw = p.read_text()
    except: return []
    changed, applied = raw, []
    for iss in issues:
        if iss.rule=="indexing.vs_block":
            m = re.search(r"'indexing\.\"(\w+)\"'", iss.message)
            if m:
                changed = re.sub(rf'("vectorStore"\s*:\s*"{m.group(1)}"\s*,?)',rf'\1\n    "{m.group(1)}": {{}},', changed, count=1)
                applied.append(f"added '{m.group(1)}': {{}}")
        if iss.rule=="indexing.camelCase":
            for w, c in CAMEL_MAP.items():
                if w in changed:
                    changed = changed.replace(f'"{w}"', f'"{c}"')
                    applied.append(f"renamed '{w}'→'{c}'")
    if changed != raw: p.write_text(changed)
    return applied

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", default="--all")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--format", choices=["text","json"], default="text")
    ap.add_argument("--fix", action="store_true")
    args = ap.parse_args()
    files = [Path(args.file)] if args.file!="--all" and not args.all else [t for t in DEFAULT_TARGETS]
    all_issues, fixes = [], []
    for f in files:
        iss = dispatch(f)
        if args.fix:
            applied = apply_fixes(f, [i for i in iss if i.severity=="ERROR"])
            fixes.extend({"file":str(f),"fix":a} for a in applied)
            if applied: iss = dispatch(f)
        all_issues.extend(iss)
    errors = [i for i in all_issues if i.severity=="ERROR"]
    if args.format=="json":
        print(json.dumps({"ok":len(errors)==0,"errors":len(errors),"warnings":sum(1 for i in all_issues if i.severity=="WARN"),"info":sum(1 for i in all_issues if i.severity=="INFO"),"issues":[asdict(i) for i in all_issues],"fixes_applied":fixes},ensure_ascii=False,indent=2))
    else:
        if not all_issues: print("All configs valid")
        else:
            for i in all_issues:
                g = {"ERROR":"","WARN":"","INFO":""}[i.severity]
                print(f"  {g} [{i.rule}] {Path(i.file).name}: {i.message}")
                if i.fix_hint: print(f"       fix: {i.fix_hint}")
    return 1 if errors else 0

if __name__=="__main__": sys.exit(main())
