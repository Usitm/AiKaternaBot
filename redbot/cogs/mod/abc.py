from abc import ABC, abstractmethod
from typing import List, Tuple, Optional

import discord
from bluebot.core import Config, commands
from bluebot.core.bot import Blue


class MixinMeta(ABC):
    """
    Base class for well behaved type hint detection with composite class.

    Basically, to keep developers sane when not all attributes are defined in each mixin.
    """

    def __init__(self, *_args):
        self.config: Config
        self.bot: Blue
        self.cache: dict

    @staticmethod
    @abstractmethod
    async def _voice_perm_check(
        ctx: commands.Context, user_voice_state: Optional[discord.VoiceState], **perms: bool
    ) -> bool:
        raise NotImplementedError()
