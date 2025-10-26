import os, io, zipfile, json, urllib.request
from opsdroid.skill import Skill
from opsdroid.matchers import match_regex

OWNER = "ShanmukhsaiDevina"
REPO  = "CHATOPS-BOT "

def _req(url, token, bytes_=False):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read() if bytes_ else json.loads(r.read().decode("utf-8"))

class LogSkill(Skill):
    @match_regex(r"^/?logs$", case_sensitive=False)
    async def logs(self, message):
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            await message.respond("❌ Missing GitHub token. Run Docker with -e GITHUB_TOKEN=…")
            return

        await message.respond("🔍 Searching latest *failed* GitHub Actions run…")
        runs = _req(f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs?status=failure&per_page=1", token).get("workflow_runs", [])
        if not runs:
            await message.respond("✅ No failed runs found recently.")
            return

        run = runs[0]
        await message.respond(f"📦 Failed run: {run['html_url']}")
        zip_bytes = _req(f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs/{run['id']}/logs", token, bytes_=True)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            files = sorted(zf.infolist(), key=lambda i: i.file_size, reverse=True)
            if not files:
                await message.respond("⚠️ Log archive is empty.")
                return
            content = zf.read(files[0]).decode("utf-8", errors="replace")
            tail = "\n".join(content.splitlines()[-25:])
            await message.respond(f"🧾 Last 25 lines:\n```{tail}```")