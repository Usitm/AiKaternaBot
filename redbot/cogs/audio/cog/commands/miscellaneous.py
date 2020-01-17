import asyncio
import datetime
import heapq
import logging
import random

import discord
import lavalink
import math

from redbot.cogs.audio.cog import MixinMeta
from redbot.core import commands
from redbot.core.utils.chat_formatting import pagify, humanize_number
from redbot.core.utils.menus import DEFAULT_CONTROLS, menu
from ..utils import _
from ...audio_dataclasses import Query

log = logging.getLogger("red.cogs.Audio.cog.commands.Miscellaneous")


class MiscellaneousCommands(MixinMeta):
    """
    All Miscellaneous commands.
    """

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def sing(self, ctx: commands.Context):
        """Make Red sing one of her songs."""
        ids = (
            "zGTkAVsrfg8",
            "cGMWL8cOeAU",
            "vFrjMq4aL-g",
            "WROI5WYBU_A",
            "41tIUr_ex3g",
            "f9O2Rjn1azc",
        )
        url = f"https://www.youtube.com/watch?v={random.choice(ids)}"
        await ctx.invoke(self.play, query=url)

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True)
    async def percent(self, ctx: commands.Context):
        """Queue percentage."""
        if not self._player_check(ctx):
            return await self._embed_msg(ctx, title=_("Nothing playing."))
        player = lavalink.get_player(ctx.guild.id)
        queue_tracks = player.queue
        requesters = {"total": 0, "users": {}}

        async def _usercount(req_username):
            if req_username in requesters["users"]:
                requesters["users"][req_username]["songcount"] += 1
                requesters["total"] += 1
            else:
                requesters["users"][req_username] = {}
                requesters["users"][req_username]["songcount"] = 1
                requesters["total"] += 1

        for track in queue_tracks:
            req_username = "{}#{}".format(track.requester.name, track.requester.discriminator)
            await _usercount(req_username)
            await asyncio.sleep(0)

        try:
            req_username = "{}#{}".format(
                player.current.requester.name, player.current.requester.discriminator
            )
            await _usercount(req_username)
        except AttributeError:
            return await self._embed_msg(ctx, title=_("There's  nothing in the queue."))

        for req_username in requesters["users"]:
            percentage = float(requesters["users"][req_username]["songcount"]) / float(
                requesters["total"]
            )
            requesters["users"][req_username]["percent"] = round(percentage * 100, 1)
            await asyncio.sleep(0)

        top_queue_users = heapq.nlargest(
            20,
            [
                (x, requesters["users"][x][y])
                for x in requesters["users"]
                for y in requesters["users"][x]
                if y == "percent"
            ],
            key=lambda x: x[1],
        )
        queue_user = ["{}: {:g}%".format(x[0], x[1]) for x in top_queue_users]
        queue_user_list = "\n".join(queue_user)
        await self._embed_msg(
            ctx, title=_("Queued and playing tracks:"), description=queue_user_list
        )

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(embed_links=True, add_reactions=True)
    async def audiostats(self, ctx: commands.Context):
        """Audio stats."""
        server_num = len(lavalink.active_players())
        total_num = len(lavalink.all_players())
        localtracks = await self.config.localpath()

        msg = ""
        for p in lavalink.all_players():
            connect_start = p.fetch("connect")
            connect_dur = self.dynamic_time(
                int((datetime.datetime.utcnow() - connect_start).total_seconds())
            )
            try:
                query = Query.process_input(p.current.uri)
                if query.is_local:
                    if p.current.title == "Unknown title":
                        current_title = localtracks.LocalPath(p.current.uri).to_string_user()
                        msg += "{} [`{}`]: **{}**\n".format(
                            p.channel.guild.name, connect_dur, current_title
                        )
                    else:
                        current_title = p.current.title
                        msg += "{} [`{}`]: **{} - {}**\n".format(
                            p.channel.guild.name, connect_dur, p.current.author, current_title
                        )
                else:
                    msg += "{} [`{}`]: **[{}]({})**\n".format(
                        p.channel.guild.name, connect_dur, p.current.title, p.current.uri
                    )
            except AttributeError:
                msg += "{} [`{}`]: **{}**\n".format(
                    p.channel.guild.name, connect_dur, _("Nothing playing.")
                )

        if total_num == 0:
            return await self._embed_msg(ctx, title=_("Not connected anywhere."))
        servers_embed = []
        pages = 1
        for page in pagify(msg, delims=["\n"], page_length=1500):
            em = discord.Embed(
                colour=await ctx.embed_colour(),
                title=_("Playing in {num}/{total} servers:").format(
                    num=humanize_number(server_num), total=humanize_number(total_num)
                ),
                description=page,
            )
            em.set_footer(
                text="Page {}/{}".format(
                    humanize_number(pages), humanize_number((math.ceil(len(msg) / 1500)))
                )
            )
            pages += 1
            servers_embed.append(em)

        await menu(ctx, servers_embed, DEFAULT_CONTROLS)

    @commands.command()
    @commands.guild_only()
    @commands.cooldown(1, 15, commands.BucketType.guild)
    @commands.bot_has_permissions(embed_links=True)
    async def summon(self, ctx: commands.Context):
        """Summon the bot to a voice channel."""
        dj_enabled = self._dj_status_cache.setdefault(
            ctx.guild.id, await self.config.guild(ctx.guild).dj_enabled()
        )
        vote_enabled = await self.config.guild(ctx.guild).vote_enabled()
        is_alone = await self._is_alone(ctx)
        is_requester = await self.is_requester(ctx, ctx.author)
        can_skip = await self._can_instaskip(ctx, ctx.author)
        if vote_enabled or (vote_enabled and dj_enabled):
            if not can_skip and not is_alone:
                ctx.command.reset_cooldown(ctx)
                return await self._embed_msg(
                    ctx,
                    title=_("Unable To Join Voice Channel"),
                    description=_("There are other people listening."),
                )
        if dj_enabled and not vote_enabled:
            if not (can_skip or is_requester) and not is_alone:
                ctx.command.reset_cooldown(ctx)
                return await self._embed_msg(
                    ctx,
                    title=_("Unable To Join Voice Channel"),
                    description=_("You need the DJ role to summon the bot."),
                )

        try:
            if (
                not ctx.author.voice.channel.permissions_for(ctx.me).connect
                or not ctx.author.voice.channel.permissions_for(ctx.me).move_members
                and self.userlimit(ctx.author.voice.channel)
            ):
                ctx.command.reset_cooldown(ctx)
                return await self._embed_msg(
                    ctx,
                    title=_("Unable To Join Voice Channel"),
                    description=_("I don't have permission to connect to your channel."),
                )
            if not self._player_check(ctx):
                await lavalink.connect(ctx.author.voice.channel)
                player = lavalink.get_player(ctx.guild.id)
                player.store("connect", datetime.datetime.utcnow())
            else:
                player = lavalink.get_player(ctx.guild.id)
                if ctx.author.voice.channel == player.channel:
                    ctx.command.reset_cooldown(ctx)
                    return
                await player.move_to(ctx.author.voice.channel)
        except AttributeError:
            ctx.command.reset_cooldown(ctx)
            return await self._embed_msg(
                ctx,
                title=_("Unable To Join Voice Channel"),
                description=_("Connect to a voice channel first."),
            )
        except IndexError:
            ctx.command.reset_cooldown(ctx)
            return await self._embed_msg(
                ctx,
                title=_("Unable To Join Voice Channel"),
                description=_("Connection to Lavalink has not yet been established."),
            )
