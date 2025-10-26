from opsdroid.skill import Skill
from opsdroid.matchers import match_regex

class CISkill(Skill):
    @match_regex(r"^/?hello$", case_sensitive=False)
    async def hello(self, message):
        await message.respond("Hi! I’m your DevOps bot.")