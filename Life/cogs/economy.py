#  Life
#  Copyright (C) 2020 Axel#3456
#
#  Life is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software
#  Foundation, either version 3 of the License, or (at your option) any later version.
#
#  Life is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
#  PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License along with Life. If not, see https://www.gnu.org/licenses/.
#

import typing

import discord
import pendulum
from discord.ext import commands

from bot import Life
from utilities import context, exceptions, objects
from utilities.enums import Editables, Operations


class Economy(commands.Cog):

    def __init__(self, bot: Life) -> None:
        self.bot = bot

        self.claim_types = {
            'daily':   Editables.daily_collected,
            'weekly':  Editables.weekly_collected,
            'monthly': Editables.monthly_collected
        }

        self.claim_type_times = {
            'daily':   (1, 2),
            'weekly':  (7, 14),
            'monthly': (30, 60)
        }

        self.claim_type_coins = {
            'daily':   200,
            'weekly':  2000,
            'monthly': 20000
        }

        self.claim_type_streaks = {
            'daily':   Editables.daily_streak,
            'weekly':  Editables.weekly_streak,
            'monthly': Editables.monthly_streak
        }

        self.claim_type_streak_thresholds = {
            'daily':   7,
            'weekly':  4,
            'monthly': 3
        }

        self.claim_type_streak_bonuses = {
            'daily':   500,
            'weekly':  5000,
            'monthly': 50000
        }

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:

        if message.author.bot:
            return

        await self.bot.user_manager.add_xp(user_id=message.author.id)

    @commands.Cog.listener()
    async def on_xp_level_up(self, user_id: int, user_config: objects.UserConfig) -> None:

        if user_config.level_up_notifications is False:
            return

        user = self.bot.get_user(id=user_id)
        try:
            await user.send(f'Congrats, you are now level `{user_config.level}`!')
        except discord.Forbidden:
            return

    #

    @commands.command(name='claim')
    async def claim(self, ctx: context.Context, claim: typing.Literal['daily', 'weekly', 'monthly'] = 'daily') -> None:

        user_config = self.bot.user_manager.get_user_config(user_id=ctx.author.id)
        if isinstance(user_config, objects.DefaultUserConfig):
            user_config = await self.bot.user_manager.create_user_config(user_id=ctx.author.id)

        now = pendulum.now(tz='UTC')

        if now < getattr(user_config, self.claim_types[claim].name).add(days=self.claim_type_times[claim][0]):
            time_until_reset = self.bot.utils.format_difference(datetime=getattr(user_config, self.claim_types[claim].name).add(days=self.claim_type_times[claim][0]), suppress=[])
            raise exceptions.ArgumentError(f'Your `{claim}` is currently on cooldown. Retry the command in `{time_until_reset}`')

        coins = self.claim_type_coins[claim]

        if now < getattr(user_config, self.claim_types[claim].name).add(days=self.claim_type_times[claim][1]):

            await self.bot.user_manager.edit_user_config(user_id=ctx.author.id, editable=self.claim_type_streaks[claim], operation=Operations.add)

            if getattr(user_config, self.claim_type_streaks[claim].name) >= self.claim_type_streak_thresholds[claim]:
                coins += self.claim_type_streak_bonuses[claim]
                await self.bot.user_manager.edit_user_config(user_id=ctx.author.id, editable=self.claim_type_streaks[claim], operation=Operations.reset)

        else:
            await self.bot.user_manager.edit_user_config(user_id=ctx.author.id, editable=self.claim_type_streaks[claim], operation=Operations.reset)

        await self.bot.user_manager.edit_user_config(user_id=ctx.author.id, editable=Editables.coins, operation=Operations.add, value=coins)
        await self.bot.user_manager.edit_user_config(user_id=ctx.author.id, editable=self.claim_types[claim], operation=Operations.reset)

        await ctx.send(f'You collected your {claim} `{coins}` credits.')

    @commands.command(name='profile')
    async def profile(self, ctx: context.Context, member: discord.Member = None) -> None:

        if not member:
            member = ctx.author

        user_config = self.bot.user_manager.get_user_config(user_id=member.id)

        embed = discord.Embed(colour=user_config.colour,
                              title=f'{member}\'s profile',
                              description=f'`Total xp:` {user_config.xp}\n'
                                          f'`Next level xp:` {user_config.next_level_xp}\n'
                                          f'`Level:` {user_config.level}\n'
                                          f'`Coins:` {user_config.coins}\n'
                                          f'`Rank (server):` {self.bot.user_manager.rank(user_id=member.id, guild_id=ctx.guild.id)}\n'
                                          f'`Rank (global):` {self.bot.user_manager.rank(user_id=member.id)}')

        await ctx.send(embed=embed)

    @commands.command(name='leaderboard', aliases=['lb'])
    async def leaderboard(self, ctx: context.Context, leaderboard_type: typing.Literal['xp', 'level', 'coins'] = 'xp', global_leaderboard: bool = False) -> None:

        if global_leaderboard is True:
            leaderboard = self.bot.user_manager.leaderboard(leaderboard_type=leaderboard_type)
            title = f'`{leaderboard_type.title()}` leaderboard across the whole bot.'
        else:
            leaderboard = self.bot.user_manager.leaderboard(leaderboard_type=leaderboard_type, guild_id=ctx.guild.id)
            title = f'`{leaderboard_type.title()}` leaderboard in `{ctx.guild}`'

        if not leaderboard:
            raise exceptions.ArgumentError(f'There are no leaderboard stats.')

        entries = []
        for index, (user_id, user_config) in enumerate(leaderboard):
            entries.append(f'{index + 1:<6} |{getattr(user_config, leaderboard_type):<10} |{ctx.bot.get_user(user_id)}')

        header = f'Rank   |{leaderboard_type.title():<10} |Name\n'
        await ctx.paginate_embed(entries=entries, per_page=10, header=header, title=title, codeblock=True)

    @commands.command(name='rank')
    async def rank(self, ctx: context.Context, member: typing.Optional[discord.Member], global_rank: bool = False) -> None:

        if not member:
            member = ctx.author

        if global_rank is True:
            rank = self.bot.user_manager.rank(user_id=member.id)
            message = f'{member} is rank `{rank}` across the whole bot.'
        else:
            rank = self.bot.user_manager.rank(user_id=member.id, guild_id=ctx.guild.id)
            message = f'{member} is rank `{rank}` in this server.'

        await ctx.send(message)

    #

    @commands.command(name='coins', aliases=['money', 'cash'])
    async def coins(self, ctx: context.Context, member: discord.Member = None) -> None:

        if not member:
            member = ctx.author

        await ctx.send(f'{member} has `{self.bot.user_manager.get_user_config(user_id=member.id).coins}` coins.')

    @commands.command(name='xp')
    async def xp(self, ctx: context.Context, member: discord.Member = None) -> None:

        if not member:
            member = ctx.author

        await ctx.send(f'{member} has `{self.bot.user_manager.get_user_config(user_id=member.id).xp}` xp.')

    @commands.command(name='level')
    async def level(self, ctx: context.Context, member: discord.Member = None) -> None:

        if not member:
            member = ctx.author

        await ctx.send(f'{member} is level `{self.bot.user_manager.get_user_config(user_id=member.id).level}`.')


def setup(bot):
    bot.add_cog(Economy(bot))
