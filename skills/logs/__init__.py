import os, io, zipfile, json, urllib.request, urllib.error
from urllib.parse import quote
from opsdroid.skill import Skill
from opsdroid.matchers import match_regex

def _req(url, token, as_bytes=False):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read() if as_bytes else json.loads(r.read().decode("utf-8"))

class LogSkill(Skill):
    @match_regex(r"^/?logs?$", case_sensitive=False)
    async def logs(self, message):
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        owner = os.environ.get("GH_OWNER", "").strip()
        repo  = os.environ.get("GH_REPO",  "").strip()

        if not token:
            await message.respond("❌ Missing GITHUB_TOKEN.")
            return
        if not owner or not repo:
            await message.respond("❌ Missing GH_OWNER / GH_REPO.")
            return

        # Build clean, encoded URLs (no spaces/newlines)
        owner_q = quote(owner, safe="")
        repo_q  = quote(repo,  safe="")
        runs_url = f"https://api.github.com/repos/{owner_q}/{repo_q}/actions/runs?status=failure&per_page=5"

        await message.respond("🔎 Searching latest *failed* GitHub Actions run…")

        try:
            data = _req(runs_url, token)
            runs = data.get("workflow_runs", [])
            if not runs:
                await message.respond("✅ No failed runs found recently.")
                return

            run = runs[0]
            await message.respond(f"📦 Failed run: {run['html_url']}")

            logs_url = f"https://api.github.com/repos/{owner_q}/{repo_q}/actions/runs/{run['id']}/logs"
            zip_bytes = _req(logs_url, token, as_bytes=True)

            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                files = sorted(zf.infolist(), key=lambda i: i.file_size, reverse=True)
                if not files:
                    await message.respond("⚠️ Log archive is empty.")
                    return
                text = zf.read(files[0]).decode("utf-8", errors="replace")
                tail = "\n".join(text.splitlines()[-30:])
                await message.respond(f"🧾 Last 30 lines:\n```{tail}```")

        except Exception as e:
            await message.respond(f"❌ Error:\n```{str(e)[:1200]}```")