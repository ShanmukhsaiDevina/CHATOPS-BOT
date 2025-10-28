import os, io, zipfile, json, re, urllib.request, urllib.error
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

def _detect(text: str):
    rules = [
        (r"Traceback \(most recent call last\)", "Python exception",
         "A Python traceback was detected. Check the last exception line and fix the root cause (missing import/path/None)."),
        (r"ModuleNotFoundError: ([\w\.\-]+)", "Python module not found",
         "Install the missing package (e.g., `pip install {0}`) or add it to your requirements."),
        (r"pytest (?:FAILURES|ERRORS)", "Pytest failures",
         "Unit tests failed. Re-run locally with `pytest -q` and fix the failing tests."),
        (r"AssertionError(:.*)?", "Assertion in tests",
         "An assertion failed. Compare expected vs actual in the lines above."),
        (r"npm ERR! (?P<err>.*)", "npm error",
         "An npm command failed. Read the first npm ERR! lines; try `npm ci` to reset dependencies."),
        (r"command not found: ([\w\-\_\.]+)", "Command not found",
         "The CI runner couldn’t find this command. Install it or add it to PATH."),
        (r"No such file or directory: ['\"]?([^'\"]+)['\"]?", "Missing file/path",
         "A required file/path is missing. Verify the path and ensure it is checked out or generated."),
        (r"Permission denied", "Permission denied",
         "A file/command lacked permissions. Use `chmod +x` for scripts or adjust permissions."),
        (r"exit\s+1\b", "Process exited with code 1",
         "Generic failure. Look a few lines above for the real error."),
    ]
    for pat, title, advice in rules:
        m = re.search(pat, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            captured = ""
            if m.groups():
                for g in m.groups():
                    if g:
                        captured = str(g).strip(": ").strip()
                        break
            if "{0}" in advice and captured:
                advice = advice.format(captured)
            return title, advice
    return ("Couldn’t auto-detect the exact cause",
            "Scan the last lines above for the first clear error. Next: enable the LLM summary for a concise explanation.")

class ExplainSkill(Skill):
    # Accept:
    #   "explain"
    #   "explain 2"               -> Nth recent failed run (max 10)
    #   "explain id 18823013212"  -> specific run id
    @match_regex(r"^/?explain(?:\s+(id)\s+(\d+)|\s+(\d+))?$", case_sensitive=False)
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
        m = message.regex
        by_id = (m and m.group(1) == "id")
        run_id = m.group(2) if m and m.group(2) else None
        index  = int(m.group(3)) if m and m.group(3) else 1
        index  = max(1, min(10, index))  # 1..10

        try:
            if by_id and run_id:
                run = _req(f"https://api.github.com/repos/{owner_q}/{repo_q}/actions/runs/{run_id}", token)
            else:
                data = _req(f"https://api.github.com/repos/{owner_q}/{repo_q}/actions/runs?status=failure&per_page={index}", token)
                runs = data.get("workflow_runs", [])
                if len(runs) < index:
                    await message.respond(f"⚠️ Only {len(runs)} failed runs found. Try a smaller number.")
                    return
                run = runs[index - 1]

            await message.respond(f"📦 Failed run: {run['html_url']}")

            logs_url = f"https://api.github.com/repos/{owner_q}/{repo_q}/actions/runs/{run['id']}/logs"
            zip_bytes = _req(logs_url, token, as_bytes=True)

            # Combine the biggest few files for context
            import heapq
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                largest = heapq.nlargest(3, zf.infolist(), key=lambda i: i.file_size)
                combined = ""
                for f in largest:
                    combined += zf.read(f).decode("utf-8", errors="replace") + "\n"

            lines = combined.splitlines()
            window = "\n".join(lines[-300:])
            title, advice = _detect(window)
            snippet = "\n".join(lines[-40:])

            await message.respond(f"🔎 **Detected:** {title}\n💡 **Likely fix:** {advice}")
            await message.respond(f"🧾 Context (last lines):\n```{snippet}```")

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            await message.respond(f"❌ HTTP {e.code} while fetching/analyzing:\n```{body[:600]}```")
        except Exception as e:
            await message.respond(f"❌ Error:\n```{str(e)[:1000]}```")