from opsdroid.skill import Skill
from opsdroid.matchers import match_regex

class ExplainSkill(Skill):
    @match_regex(r"^/?explain$", case_sensitive=False)
    async def explain(self, message):
        await message.respond(
            "Soon: I’ll analyze the CI logs and give plain-English fixes. "
            "Phase 1 = rules (tracebacks/npm/pytest). Phase 2 = LLM summary."
        )