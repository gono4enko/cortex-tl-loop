"""MCP Adapter interface + GitHub + Firecrawl implementations."""
from __future__ import annotations
import subprocess, logging, os

logger = logging.getLogger(__name__)

class FirecrawlAdapter:
    """Firecrawl search via CLI or API."""
    name = "firecrawl"
    
    def search(self, query: str) -> list[dict]:
        try:
            result = subprocess.run(
                ["firecrawl", "search", query, "--limit", "3"],
                capture_output=True, text=True, timeout=30,
            )
            return [{"title": l, "url": ""} for l in result.stdout.strip().split("\n") if l]
        except Exception as e:
            logger.warning(f"Firecrawl: {e}")
            return []
    
    def health(self) -> bool:
        try:
            r = subprocess.run(["firecrawl", "--version"], capture_output=True, timeout=5)
            return r.returncode == 0
        except:
            return False

class GitHubAdapter:
    """GitHub operations via gh CLI."""
    name = "github"
    
    def create_pr(self, branch: str, title: str, body: str) -> dict:
        try:
            r = subprocess.run(
                ["gh", "pr", "create", "--head", branch, "--title", title, "--body", body],
                capture_output=True, text=True, timeout=30,
            )
            return {"ok": r.returncode == 0, "url": r.stdout.strip()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def merge_pr(self, pr_number: int) -> bool:
        try:
            r = subprocess.run(["gh", "pr", "merge", str(pr_number), "--squash", "--auto"],
                capture_output=True, text=True, timeout=30)
            return r.returncode == 0
        except:
            return False
    
    def health(self) -> bool:
        try:
            r = subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=5)
            return r.returncode == 0
        except:
            return False


class Context7Adapter:
    """Context7 documentation search for PLAN phase."""
    name = "context7"

    def search_docs(self, query: str, library: str = "") -> list[dict]:
        try:
            import urllib.request, json
            from urllib.parse import quote
            url = f"https://context7.com/api/search?q={quote(query)}"  # ponytail: simple REST
            r = urllib.request.urlopen(url, timeout=15)
            return json.loads(r.read()).get("results", [])[:5]
        except Exception as e:
            logger.warning(f"Context7: {e}")
            return []

    def health(self) -> bool:
        try:
            import urllib.request, json
            r = urllib.request.urlopen("https://context7.com/api/search?q=test", timeout=5)
            return r.status == 200
        except:
            return False


class SerenaAdapter:
    """Serena semantic code analysis for REVIEW phase."""
    name = "serena"

    def analyze(self, file_path: str) -> dict:
        try:
            r = subprocess.run(
                ["uvx", "serena-agent", "analyze", file_path],
                capture_output=True, text=True, timeout=60,
            )
            return {"ok": r.returncode == 0, "output": r.stdout[:2000]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def health(self) -> bool:
        try:
            r = subprocess.run(["uvx", "serena-agent", "--version"], capture_output=True, timeout=10)
            return r.returncode == 0
        except:
            return False
