#!/usr/bin/env python3
"""Research Agent — daily GitHub/Reddit/HF monitoring."""
import os, sys, json, logging, subprocess
from datetime import datetime
sys.path.insert(0, "/home/hermes")
from cortex.lib.email import send_email

logging.basicConfig(level=logging.INFO, format="%(asctime)s [research] %(levelname)s: %(message)s")
log = logging.getLogger("research")

SOURCES = [
    ("github", "sst/opencode releases"),
    ("github", "langchain-ai/langgraph releases"),
    ("github", "firecrawl/firecrawl releases"),
    ("reddit", "r/LocalLLaMA new model"),
    ("reddit", "r/AI_Agents framework"),
    ("huggingface", "text-generation models trending"),
]

def firecrawl_search(query):
    try:
        r = subprocess.run(["firecrawl","search", query, "--limit","3"],
            capture_output=True, text=True, timeout=30)
        return r.stdout[:2000] if r.returncode == 0 else ""
    except:
        return ""

def run_daily():
    log.info("Research scan started")
    findings = []
    today = datetime.now().strftime("%Y-%m-%d")
    
    for source, query in SOURCES:
        result = firecrawl_search(query)
        if result.strip():
            findings.append("### " + source + ": " + query + "\n" + result[:500])
    
    report = "# Research Digest - " + today + "\n\n" + "\n\n".join(findings) if findings else "No notable findings today."
    
    kb_path = "/home/hermes/obsidian-kb/06-ai-context/cortex/research/" + today + ".md"
    os.makedirs(os.path.dirname(kb_path), exist_ok=True)
    with open(kb_path, "w") as f:
        f.write(report)
    
    send_email(to="gono4enko@gmail.com",
               subject="AI Research Digest - " + today,
               body=report[:3000], priority="info")
    
    log.info("Research complete: " + str(len(findings)) + " findings")

if __name__ == "__main__":
    run_daily()
