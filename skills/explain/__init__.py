import os, io, zipfile, json, re, urllib.request
from urllib.parse import quote
from opsdroid.skill import Skill
from opsdroid.matchers import match_regex

def _req(url, token, as_bytes=False):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read() if as_bytes else json.loads(r.read().decode("utf-8"))

def _detect(findings: str):
    """Return (title, advice) based on simple patterns."""
    text = findings

    rules = [
        (r"Traceback \(most recent call last\)", 
         "Python exception",
         "A Python stack trace was detected. Check the last exception line for the exact error type and file. "
         "Common fixes: import the missing module, correct the path, or handle None values."),
        (r"ModuleNotFoundError: ([\w\.\-]+)", 
         "Python module not found",
         "Install the missing dependency (e.g., `pip install {0}`) or add it to your requirements."),
        (r"pytest (?:FAILURES|ERRORS)",
         "Pytest failures",
         "Unit tests failed. Open the failing test names shown above. Re-run locally with `pytest -q` to reproduce."),
        (r"AssertionError(:.*)?",
         "AssertionError in tests",
         "An assertion failed in tests. Compare expected vs actual values printed nearby."),
        (r"npm ERR! (?P<err>.*)",
         "npm error",
         "A Node.js/npm command failed. Read the first npm ERR! lines for the root cause; try `npm ci` to reset deps."),
        (r"command not found: ([\w\-\_\.]+)",
         "Command not found",
         "The CI runner couldn’t find this command. Install it first or add the tool to PATH."),
        (r"No such file or directory: ['\"]?([^'\"]+)['\"]?",
         "Missing file/path",
         "A file path is missing. Verify the path and ensure the file is checked out or generated earlier."),
        (r"Permission denied",
         "Permission denied",
         "File/command lacked permissions. Use `chmod +x` for scripts or adjust runner permissions."),
        (r"exit\s+1\b",
         "Process exited with code 1",
         "A generic failure occurred. Look a few lines above for the specific error message."),
    ]

    for pattern, title, advice in rules:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            # Include captured value if available
            captured = ""
            if m.groups():
                # Try first non-empty capture for personalization
                for g in m.groups():
                    if g:
                        captured = str(g).strip(": ").strip()
                        break
            hint = advice
            if "{0}" in advice and captured:
                hint = advice.format(captured)
            return title, hint
    return ("Couldn’t auto-detect the exact cause",
            "Scan the last lines above for the first clear error. "
            "Next step: enable the LLM summary to get a concise explanation.")

class ExplainSkill(Skill):
    @match_regex(r"^/?explain$", case_sensitive=False)
    async def explain(self, message):
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        owner = os.environ.get("GH_OWNER", "").strip()
        repo  = os.environ.get("GH_REPO",  "").strip()

        if not token:
            await message.respond("❌ Missing GITHUB_TOKEN.")
            return
        if not owner or not repo:
            await message.respond("❌ Missing GH_OWNER / GH_REPO.")
            return

        owner_q, repo_q = quote(owner, safe=""), quote(repo, safe="")
        runs_url = f"https://api.github.com/repos/{owner_q}/{repo_q}/actions/runs?status=failure&per_page=1"
        await message.respond("🧠 Analyzing the latest *failed* run…")

        try:
            runs = _req(runs_url, token).get("workflow_runs", [])
            if not runs:
                await message.respond("✅ No failed runs found recently.")
                return

            run = runs[0]
            await message.respond(f"📦 Failed run: {run['html_url']}")

            logs_url = f"https://api.github.com/repos/{owner_q}/{repo_q}/actions/runs/{run['id']}/logs"
            zip_bytes = _req(logs_url, token, as_bytes=True)

            # Read and combine the biggest few files to get good context
            import heapq
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                largest = heapq.nlargest(3, zf.infolist(), key=lambda i: i.file_size)
                combined = ""
                for f in largest:
                    combined += zf.read(f).decode("utf-8", errors="replace") + "\n"

            # Look at the last ~300 lines for signal
            lines = combined.splitlines()
            window = "\n".join(lines[-300:])

            title, advice = _detect(window)
            snippet = "\n".join(lines[-40:])  # small tail for reference

            await message.respond(f"🔎 **Detected:** {title}\n💡 **Likely fix:** {advice}")
            await message.respond(f"🧾 Context (last lines):\n```{snippet}```")

        except Exception as e:
            await message.respond("❌ Error while analyzing logs.")
            await message.respond(f"Details:\n```{str(e)[:1000]}```")