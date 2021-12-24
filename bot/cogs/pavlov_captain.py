import asyncio
import logging
import random
from datetime import datetime

import discord
import discord_components
from discord.ext import commands
from discord_components import Button, Select

from bot.utils import SteamPlayer, aliases, config, servers
from bot.utils.interactions import (
    spawn_iselect,
    spawn_mselect,
    spawn_pselect,
    spawn_serselect,
    spawn_tselect,
)
from bot.utils.pavlov import check_perm_captain, exec_server_command
from bot.utils.players import (
    exec_command_all_players,
    exec_command_all_players_on_team,
    parse_player_command_results,
)

MATCH_DELAY_RESETSND = 5
RCON_COMMAND_PAUSE = 100 / 1000  # milliseconds


class PavlovCaptain(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info(f"{type(self).__name__} Cog ready.")

    @commands.command()
    async def gamesetup(self, ctx, __interaction: discord_components.Interaction = None):
        async def actions(interact, msg, server_name: str = ""):
            gamesetup = self.bot.all_commands.get("gamesetup")
            await msg.edit(content="")
            if server_name == "":
                server_name = interact.values[0]
            elif server_name == "OFFLINE":
                embed = discord.Embed(title="Server is offline.")
                await interact.send(embed=embed)
                return
            if await check_perm_captain(ctx, server_name):
                ctx.interaction_exec = True
                matchsetup = self.bot.all_commands.get("matchsetup")
                resetsnd = self.bot.all_commands.get("resetsnd")
                switchmap = self.bot.all_commands.get("switchmap")
                embed = discord.Embed(title=f"**{server_name} Match Menu**")
                team_one, interact = await spawn_tselect(self, ctx, server_name, interact, "1")
                team_two, interact = await spawn_tselect(self, ctx, server_name, interact, "2")
                #               if team_one == "empty" and team_two == "empty":
                #                 embed.description = (
                #                        "**No teams defined in aliases.json! Team buttons disabled.**"
                #                    )
                #                    await i1.send(
                #                        embed=embed,
                #                        components=[
                #                            self.bot.components_manager.add_callback(
                #                                Button(label=f"ResetSND"),
                #                                lambda interaction: resetsnd(ctx, server_name, interaction),
                #                            )
                #                        ],
                #                    )
                if team_one == team_two:
                    embed.description = "**Duplicate teams detected! Team buttons disabled.**"
                    await interact.send(
                        embed=embed,
                        components=[
                            self.bot.components_manager.add_callback(
                                Button(
                                    label=f"ResetSND",
                                ),
                                lambda interaction: resetsnd(ctx, server_name, interaction),
                            ),
                            self.bot.components_manager.add_callback(
                                Button(
                                    label=f"Change Settings",
                                ),
                                lambda interaction: actions(interaction, msg, server_name),
                            ),
                        ],
                    )
                #               elif team_one == "empty":
                #                   embed.description = "**Missing team one! Team buttons disabled.**"
                #                   await i1.send(
                #                       embed=embed,
                #                       components=[
                #                           self.bot.components_manager.add_callback(
                #                               Button(label=f"ResetSND"),
                #                               lambda interaction: resetsnd(ctx, server_name, interaction),
                #                           ),
                #                           self.bot.components_manager.add_callback(
                #                               Button(label=f"Change Settings"),
                #                               lambda interaction: actions(interaction, msg, server_name),
                #                           ),
                #                       ],
                #                   )
                #               elif team_two == "empty":
                #                   embed.description = "**Missing team two! Team buttons disabled.**"
                #                   await i1.send(
                #                       embed=embed,
                #                       components=[
                #                           self.bot.components_manager.add_callback(
                #                               Button(label=f"ResetSND"),
                #                               lambda interaction: resetsnd(ctx, server_name, interaction),
                #                           ),
                #                           self.bot.components_manager.add_callback(
                #                               Button(label=f"Change Settings"),
                #                               lambda interaction: actions(interaction, msg, server_name),
                #                           ),
                #                      ],
                #                   )
                else:
                    await interact.send(
                        embed=embed,
                        components=[
                            self.bot.components_manager.add_callback(
                                Button(
                                    label=f"CT: {team_one} vs T: {team_two}",
                                ),
                                lambda interaction: matchsetup(
                                    ctx, team_one, team_two, server_name, interaction
                                ),
                            ),
                            self.bot.components_manager.add_callback(
                                Button(
                                    label=f"CT: {team_two} vs T: {team_one}",
                                ),
                                lambda interaction: matchsetup(
                                    ctx, team_two, team_one, server_name, interaction
                                ),
                            ),
                            self.bot.components_manager.add_callback(
                                Button(
                                    label=f"ResetSND",
                                ),
                                lambda interaction: resetsnd(ctx, server_name, interaction),
                            ),
                            self.bot.components_manager.add_callback(
                                Button(
                                    label=f"Change Settings",
                                ),
                                lambda interaction: gamesetup(ctx, interaction),
                            ),
                            self.bot.components_manager.add_callback(
                                Button(
                                    label=f"Switch Map",
                                ),
                                lambda interaction: switchmap(
                                    ctx, "", "", server_name, interaction
                                ),
                            ),
                        ],
                    )
            else:
                return
        options, embed = await spawn_serselect(self, ctx)
        if ctx.interaction_exec == True:
            message = await __interaction.send(
                embed=embed,
                components=[
                    self.bot.components_manager.add_callback(
                        Select(placeholder="Server", options=options),
                        lambda interaction: actions(interaction, message),
                    )
                ],
            )
        else:
            message = await ctx.send(
                embed=embed,
                components=[
                    self.bot.components_manager.add_callback(
                        Select(placeholder="Server", options=options),
                        lambda interaction: actions(interaction, message),
                    )
                ],
            )


    @commands.command(aliases=["map"])
    async def switchmap(
        self,
        ctx,
        map_name: str,
        game_mode: str,
        server_name: str = config.default_server,
        __interaction: discord_components.Interaction = None,
    ):
        """`{prefix}switchmap <map_name> <game_mode> <server_name>`

        **Requires**: Captain permissions or higher for the server
        **Example**: `{prefix}switchmap 89374583439127 servername`
        **Alias**: switchmap can be shortened to just map `{prefix}map 89374583439127 servername`
        """
        if ctx.interaction_exec:
            if not await check_perm_captain(__interaction, server_name):
                return
        else:
            if not await check_perm_captain(ctx, server_name):
                return
        if ctx.interaction_exec:
            map_name, __interaction = await spawn_mselect(self, ctx, server_name, __interaction)
            game_mode = "snd"
        gamesetup = self.bot.all_commands.get("gamesetup")
        resetsnd = self.bot.all_commands.get("resetsnd")
        map_label = aliases.get_map(map_name)
        if game_mode.upper() == "SND":
            ctx.interaction_exec = True
            components = [
                self.bot.components_manager.add_callback(
                    Button(label=f"Match Menu"),
                    lambda interaction: gamesetup(ctx, interaction),
                ),
                self.bot.components_manager.add_callback(
                    Button(label=f"ResetSND"),
                    lambda interaction: resetsnd(ctx, server_name, interaction),
                ),
            ]
        else:
            ctx.interaction_exec = True
            components = []
        data = await exec_server_command(
            ctx, server_name, f"SwitchMap {map_label} {game_mode.upper()}"
        )
        switch_map = data.get("SwitchMap")
        if ctx.batch_exec:
            return switch_map
        if not switch_map:
            embed = discord.Embed(
                title=f"**Failed** to switch map to {map_name} with game mode {game_mode.upper()} on {server_name}."
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title=f"Switched map to {map_name} with game mode {game_mode.upper()} on {server_name}."
            )
            await ctx.send(embed=embed, components=components)
        if ctx.interaction_exec:
            await __interaction.send(embed=embed)
            return

    @commands.command()
    async def resetsnd(
        self, ctx, server_name: str = config.default_server, __interaction: str = ""
    ):
        """`{prefix}resetsnd <server_name>`

        **Requires**: Captain permissions or higher for the server
        **Example**: `{prefix}resetsnd servername`
        """

        if ctx.interaction_exec:
            if not await check_perm_captain(__interaction, server_name):
                return
        else:
            if not await check_perm_captain(ctx, server_name):
                return
        data = await exec_server_command(ctx, server_name, "ResetSND")
        reset_snd = data.get("ResetSND")
        if not reset_snd:
            embed = discord.Embed(title=f"**Failed** to reset SND on {server_name}.")
        else:
            embed = discord.Embed(title=f"SND has been successfully reset on {server_name}.")
        if ctx.interaction_exec:
            await __interaction.send(embed=embed)
            return
        if ctx.batch_exec:
            return reset_snd
        await ctx.send(embed=embed)

    @commands.command()
    async def switchteam(
        self,
        ctx,
        player_arg: str,
        team_id: str,
        server_name: str = config.default_server,
    ):
        """`{prefix}switchteam <player_id> <team_id> <server_name>`

        **Requires**: Captain permissions or higher for the server
        **Example**: `{prefix}resetsnd 89374583439127 0 servername`
        """
        if not await check_perm_captain(ctx, server_name):
            return
        player = SteamPlayer.convert(player_arg)
        data = await exec_server_command(
            ctx, server_name, f"SwitchTeam {player.unique_id} {team_id}"
        )
        embed = discord.Embed(title=f"**SwitchTeam {player_arg} {team_id}** \n")
        embed = await parse_player_command_results(ctx, data, embed, server_name)
        await ctx.send(embed=embed)

    @commands.command(aliases=["next"])
    async def rotatemap(self, ctx, server_name: str = config.default_server):
        """`{prefix}rotatemap <server_name>`

        **Requires**: Captain permissions or higher for the server
        **Example**: `{prefix}rotatemap servername`
        **Aliases**: rotatemap can also be called as next `{prefix}next servername`
        """
        if not await check_perm_captain(ctx, server_name):
            return
        data = await exec_server_command(ctx, server_name, f"RotateMap")
        rotate_map = data.get("RotateMap")
        if ctx.batch_exec:
            return rotate_map
        if not rotate_map:
            embed = discord.Embed(title=f"**Failed** to rotate map on {server_name}.")
        else:
            embed = discord.Embed(title=f"Rotated map successfully on {server_name}.")
        await ctx.send(embed=embed)

    @commands.command()
    async def matchsetup(
        self,
        ctx,
        team_a_name: str,
        team_b_name: str,
        server_name: str = config.default_server,
        __interaction: discord_components.Interaction = None,
    ):
        """`{prefix}matchsetup <CT team name> <T team name> <server name>`

        **Requires**: Captain permissions or higher for the server
        **Example**: `{prefix}matchsetup ct_team t_team servername`
        """
        if ctx.interaction_exec:
            if not await check_perm_captain(__interaction, server_name):
                return
        else:
            if not await check_perm_captain(ctx, server_name):
                return
        before = datetime.now()
        teams = [aliases.get_team(team_a_name), aliases.get_team(team_b_name)]
        embed = discord.Embed()
        for team in teams:
            embed.add_field(name=f"{team.name} members", value=team.member_repr(), inline=False)
        if ctx.interaction_exec:
            await __interaction.send(embed=embed)
        else:
            await ctx.send(embed=embed)

        for index, team in enumerate(teams):
            for member in team.members:
                await exec_server_command(
                    ctx, server_name, f"SwitchTeam {member.unique_id} {index}"
                )
                await asyncio.sleep(RCON_COMMAND_PAUSE)
        embed = discord.Embed(
            title=f"Teams set up. Resetting SND in {MATCH_DELAY_RESETSND} seconds on {server_name}."
        )
        if ctx.interaction_exec:
            await __interaction.send(embed=embed)
        else:
            await ctx.send(embed=embed)
        await asyncio.sleep(MATCH_DELAY_RESETSND)
        await exec_server_command(ctx, server_name, "ResetSND")
        embed = discord.Embed(title=f"SND has been reset on {server_name}. Good luck!")
        embed.set_footer(text=f"Execution time: {datetime.now() - before}")
        if ctx.interaction_exec:
            await __interaction.send(embed=embed)
        else:
            await ctx.send(embed=embed)

    @commands.command()
    async def flush(self, ctx: commands.Context, server_name: str = config.default_server):
        """`{prefix}flush <servername>`
        **Requires**: Captain permissions or higher for the server
        **Example**: `{prefix}flush snd1`
        """
        if not await check_perm_captain(ctx, server_name):
            return
        data = await exec_server_command(ctx, server_name, "RefreshList")
        player_list = data.get("PlayerList")
        non_alias_player_ids = list()
        for player in player_list:
            check = aliases.find_player_alias(player.get("UniqueId"))
            if check is None:
                non_alias_player_ids.append(player.get("UniqueId"))
        if len(non_alias_player_ids) == 0:
            await ctx.send(embed=discord.Embed(title=f"No players to flush on `{server_name}`"))
            return
        to_kick_id = random.choice(non_alias_player_ids)
        data = await exec_server_command(ctx, server_name, f"Kick {to_kick_id}")
        kick = data.get("Kick")
        if not kick:
            await ctx.send(
                embed=discord.Embed(title=f"Encountered error while flushing on `{server_name}`")
            )
        else:
            await ctx.send(embed=discord.Embed(title=f"Successfully flushed `{server_name}`"))


def setup(bot):
    bot.add_cog(PavlovCaptain(bot))
