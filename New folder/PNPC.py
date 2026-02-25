import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import asyncio
import time
import os
from datetime import datetime as dt, timedelta
from collections import defaultdict
from dotenv import load_dotenv
import os
from keep_alive import keep_alive
keep_alive()
# ================= CONFIG =================
load_dotenv()
TOKEN = os.getenv("TOKEN")


GUILD_ID = 1475595580066762762

LOG_CHANNEL_ID = 1475596749044191362
STAFF_UPDATES_CHANNEL_ID = 1475602070479568936

TICKET_PANEL_CHANNEL = 1475615742434218138
TICKET_CATEGORY_ID = 1475601312644206793

DUEL_REQUEST_CHANNEL_ID = 1475806613532180500
DUEL_CATEGORY_ID = TICKET_CATEGORY_ID

DUEL_TIMEOUT_MINUTES = 5
DUEL_INACTIVITY_TIMEOUT_MIN = 5
DUEL_DELETE_DELAY_MIN = 2

STAFF_ROLE_IDS = [
    1475598374874120374,
    1475595775328391269,
    1475619922972250305
]

APPLICATION_PING_ROLE_IDS = [
    1475595775328391269,   # Admin
    1475598374874120374,   # Manager
    1475923450798543029    # Owner
]

SELF_ROLE_IDS = [
    1475621346284277966, 1475621467495338035, 1475622463982403705,
    1475622573311000748, 1475622651887354110, 1475622765494145095,
    1475622847681531975, 1475623014250053703, 1475623089315381278,
    1475621440794398852, 1475621499531558912, 1475622494986698753,
    1475622607855554742, 1475622715602763858, 1475622813216805025,
    1475622886877298790, 1475623048513065061
]

OWNER_ID = 894164727595421736

# ==========================================

intents = discord.Intents.all()

bot = commands.Bot(command_prefix="!", intents=intents)

guild_obj = discord.Object(id=GUILD_ID)

duel_voice_last_active = defaultdict(float)

# ================= UTIL =================

async def send_log(guild, message):
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(message)

def is_staff(member: discord.Member):
    return any(role.id in STAFF_ROLE_IDS for role in member.roles)

def is_owner(user_id):
    return user_id == OWNER_ID

# ================= TICKET VIEWS =================

class TicketTypeView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    async def create_ticket(self, interaction, ticket_type):
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            self.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(view_channel=True)
        }

        for role_id in STAFF_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        channel_name = f"{ticket_type}-{self.user.name}".lower()

        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        await channel.send(
            f"{self.user.mention} Ticket created.\nStaff will assist you shortly.",
            view=TicketCloseView()
        )

        if ticket_type == "application":
            try:
                existing = [ch for ch in category.channels if isinstance(ch, discord.TextChannel) and "application-private" in ch.name]
                num = len(existing) + 1

                private_overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                    self.user: discord.PermissionOverwrite(view_channel=False)
                }

                for role_id in STAFF_ROLE_IDS + APPLICATION_PING_ROLE_IDS:
                    role = guild.get_role(role_id)
                    if role:
                        private_overwrites[role] = discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            read_message_history=True
                        )

                private_channel = await guild.create_text_channel(
                    name=f"application-private-{num}",
                    category=category,
                    overwrites=private_overwrites,
                    reason=f"Private channel for staff application by {self.user}"
                )

                ping_mentions = " ".join([f"<@&{rid}>" for rid in APPLICATION_PING_ROLE_IDS])
                await private_channel.send(
                    f"{ping_mentions}\nNew staff application from {self.user.mention} → {channel.mention}\n"
                    "Please review and discuss here."
                )

                await channel.send(
                    f"Private application review channel created: {private_channel.mention} (staff only)"
                )

            except discord.Forbidden as e:
                print(f"[PERM ERROR] Private application channel: {e}")
                await channel.send("⚠ Failed to create private application channel (bot missing permissions).")
            except Exception as e:
                print(f"[ERROR] Private application channel failed: {e}")
                await channel.send("⚠ An error occurred while creating the private application channel.")

        await interaction.followup.send("Ticket created successfully.", ephemeral=True)

    @discord.ui.button(label="Support Ticket", style=discord.ButtonStyle.green)
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.create_ticket(interaction, "support")
        except Exception as e:
            print(f"Support ticket error: {e}")
            await interaction.followup.send(
                "Sorry, something went wrong. Please try again or contact staff.",
                ephemeral=True
            )

    @discord.ui.button(label="Staff Application", style=discord.ButtonStyle.blurple)
    async def staff_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.create_ticket(interaction, "application")
        except Exception as e:
            print(f"Staff application ticket error: {e}")
            await interaction.followup.send(
                "Sorry, something went wrong. Please try again or contact staff.",
                ephemeral=True
            )


class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket_button")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Choose ticket type:",
            view=TicketTypeView(interaction.user),
            ephemeral=True
        )


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket_button")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            await interaction.response.send_message("Only staff can close tickets.", ephemeral=True)
            return

        channel = interaction.channel

        await interaction.response.send_message("Closing ticket in 5 seconds...", ephemeral=False)
        await asyncio.sleep(5)
        try:
            await channel.delete(reason=f"Closed by {interaction.user}")
        except:
            pass


# ================= DUEL VIEWS =================

class DuelAcceptView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="duel_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        # No DB check anymore — just accept and create channels
        # (you can add manual duplicate check logic later if needed)

        # Fake duel number (simple counter in memory - resets on restart)
        duel_num = len(duel_voice_last_active) + 1

        category = interaction.guild.get_channel(DUEL_CATEGORY_ID)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, connect=True, speak=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
        }
        for r_id in STAFF_ROLE_IDS:
            r = interaction.guild.get_role(r_id)
            if r:
                overwrites[r] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, connect=True, speak=True)

        text_channel = await interaction.guild.create_text_channel(name=f"duel-{duel_num}", category=category, overwrites=overwrites)
        voice_channel = await interaction.guild.create_voice_channel(name=f"duel-{duel_num}", category=category, overwrites=overwrites)

        duel_voice_last_active[voice_channel.id] = time.time()

        embed = interaction.message.embeds[0]
        embed.description = f"{interaction.user.mention} accepted the duel request!"
        embed.color = discord.Color.green()
        await interaction.message.edit(embed=embed, view=None)

        await text_channel.send(
            f"{interaction.user.mention}\n"
            f"**Duel accepted!**\nVoice: {voice_channel.mention}\n"
            f"(will be cleaned up if no one joins voice for {DUEL_INACTIVITY_TIMEOUT_MIN} minutes)"
        )

        await interaction.response.send_message("Duel accepted! Channels created.", ephemeral=True)


# ================= BACKGROUND TASKS =================

@tasks.loop(minutes=1)
async def check_inactive_duels():
    now = time.time()
    to_check = list(duel_voice_last_active.items())

    for vc_id, last_active in to_check:
        voice_ch = bot.get_channel(vc_id)
        if not voice_ch:
            del duel_voice_last_active[vc_id]
            continue

        if len(voice_ch.members) > 0:
            duel_voice_last_active[vc_id] = now
            continue

        inactive_time = now - last_active

        if inactive_time >= DUEL_INACTIVITY_TIMEOUT_MIN * 60 and last_active > 0:
            # Find text channel by name pattern (since no DB)
            for ch in voice_ch.category.channels:
                if isinstance(ch, discord.TextChannel) and ch.name == voice_ch.name:
                    text_ch = ch
                    await text_ch.send(
                        f"⚠ **Inactivity Warning**\n"
                        f"No one has been in the voice channel for {DUEL_INACTIVITY_TIMEOUT_MIN} minutes.\n"
                        f"Channels will be deleted in {DUEL_DELETE_DELAY_MIN} minutes if still empty."
                    )
                    break

            duel_voice_last_active[vc_id] = -1

        elif last_active < 0 and inactive_time >= (DUEL_INACTIVITY_TIMEOUT_MIN + DUEL_DELETE_DELAY_MIN) * 60:
            for ch in voice_ch.category.channels:
                if isinstance(ch, discord.TextChannel) and ch.name == voice_ch.name:
                    text_ch = ch
                    await text_ch.send("Deleting channels due to prolonged inactivity.")
                    await asyncio.sleep(1.5)
                    await text_ch.delete(reason="Duel inactive - no voice activity")
                    break

            await voice_ch.delete(reason="Duel inactive - no voice activity")
            del duel_voice_last_active[vc_id]


# ================= EVENTS =================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    bot.add_view(TicketPanel())
    bot.add_view(TicketCloseView())
    bot.add_view(DuelAcceptView())

    try:
        await bot.tree.sync(guild=guild_obj)
        print(f"Synced {len(await bot.tree.fetch_commands(guild=guild_obj))} commands")
    except Exception as e:
        print(e)

    if not check_inactive_duels.is_running():
        check_inactive_duels.start()


@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel == after.channel:
        return

    vc_id = None
    if after.channel and after.channel.id in duel_voice_last_active:
        vc_id = after.channel.id
    elif before.channel and before.channel.id in duel_voice_last_active:
        vc_id = before.channel.id

    if vc_id and len(bot.get_channel(vc_id).members) > 0:
        duel_voice_last_active[vc_id] = time.time()


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    if is_staff(message.author):
        # No DB tracking anymore — you can add print or log if you want
        pass

    await bot.process_commands(message)


# ================= SLASH COMMANDS =================

@app_commands.command(name="duel", description="Request a duel against players with a specific role")
@app_commands.describe(role="Choose the role you want to duel against")
async def duel(interaction: discord.Interaction, role: discord.Role):
    if role.id not in SELF_ROLE_IDS:
        await interaction.response.send_message("This role cannot be challenged for duels.", ephemeral=True)
        return

    request_channel = interaction.guild.get_channel(DUEL_REQUEST_CHANNEL_ID)
    if not request_channel:
        await interaction.response.send_message("Duel request channel not found.", ephemeral=True)
        return

    expires_at = dt.utcnow() + timedelta(minutes=DUEL_TIMEOUT_MINUTES)

    embed = discord.Embed(
        title="Duel Request",
        description=f"**{interaction.user.mention}** has requested a duel!\nRole: {role.mention}\n\nAccept within {DUEL_TIMEOUT_MINUTES} minutes.",
        color=discord.Color.orange(),
        timestamp=dt.utcnow()
    )
    embed.set_footer(text=f"Expires • {expires_at.strftime('%H:%M UTC')}")

    view = DuelAcceptView()
    msg = await request_channel.send(
        content=role.mention,
        embed=embed,
        view=view,
        allowed_mentions=discord.AllowedMentions(roles=True)
    )

    await interaction.response.send_message(f"Duel request sent in {request_channel.mention}!", ephemeral=True)


@app_commands.command(name="staff", description="Staff update command")
@app_commands.checks.has_permissions(administrator=True)
async def staff_cmd(interaction: discord.Interaction, action: str, rank: str, user: discord.Member):
    channel = interaction.guild.get_channel(STAFF_UPDATES_CHANNEL_ID)
    embed = discord.Embed(title="Staff Update", color=discord.Color.blue(), timestamp=dt.utcnow())
    embed.add_field(name="User", value=user.mention, inline=False)
    embed.add_field(name="Action", value=action, inline=True)
    embed.add_field(name="Rank", value=rank, inline=True)
    embed.set_footer(text=f"By {interaction.user}")
    await channel.send(embed=embed)
    await interaction.response.send_message("Sent.", ephemeral=True)


@app_commands.command(name="pgamemode", description="Give yourself a self-assignable role")
@app_commands.describe(role="The role you want to get")
async def pgamemode(interaction: discord.Interaction, role: discord.Role):
    if role.id not in SELF_ROLE_IDS:
        await interaction.response.send_message("This role is not self-assignable.", ephemeral=True)
        return

    if role in interaction.user.roles:
        await interaction.response.send_message(f"You already have **{role.name}**.", ephemeral=True)
        return

    try:
        await interaction.user.add_roles(role)
        await interaction.response.send_message(f"**{role.name}** added to you.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to assign that role.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message("Failed to assign role.", ephemeral=True)


@app_commands.command(name="botsay", description="Send an embedded message as the bot")
@app_commands.describe(
    channel="Where to send the message",
    content="The message text",
    title="Embed title (optional)",
    color="Embed color (optional)"
)
@app_commands.choices(color=[
    app_commands.Choice(name="Blue", value="blue"),
    app_commands.Choice(name="Red", value="red"),
    app_commands.Choice(name="Green", value="green"),
    app_commands.Choice(name="Yellow", value="yellow"),
    app_commands.Choice(name="Purple", value="purple"),
    app_commands.Choice(name="Orange", value="orange"),
    app_commands.Choice(name="Dark", value="dark")
])
@app_commands.checks.has_permissions(administrator=True)
async def botsay(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    content: str,
    title: str = "Announcement",
    color: str = "blue"
):
    color_map = {
        "blue": discord.Color.blue(),
        "red": discord.Color.red(),
        "green": discord.Color.green(),
        "yellow": discord.Color.yellow(),
        "purple": discord.Color.purple(),
        "orange": discord.Color.orange(),
        "dark": discord.Color.dark_grey()
    }

    embed_color = color_map.get(color, discord.Color.blue())

    embed = discord.Embed(
        title=title,
        description=content,
        color=embed_color,
        timestamp=dt.utcnow()
    )
    embed.set_footer(text=f"Posted by {interaction.user}")

    try:
        await channel.send(embed=embed)
        await interaction.response.send_message(f"Embedded message sent to {channel.mention} with color **{color}**", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Missing permissions to send embeds there.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Failed to send: {str(e)}", ephemeral=True)


@app_commands.command(name="sendticketpanel", description="Send the ticket panel (staff only)")
async def send_ticket_panel(interaction: discord.Interaction):
    if not is_staff(interaction.user):
        await interaction.response.send_message("Staff only.", ephemeral=True)
        return
    embed = discord.Embed(title="Create a Ticket", description="Click below to open a ticket.", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=TicketPanel())
    await interaction.response.send_message("Panel sent.", ephemeral=True)


@app_commands.command(name="warn", description="Warn a member")
@app_commands.describe(user="Target member", reason="Reason for warning")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not is_staff(interaction.user):
        await interaction.response.send_message("Staff only.", ephemeral=True)
        return

    embed = discord.Embed(title="Warning Issued", color=0xffaa00, timestamp=dt.utcnow())
    embed.add_field(name="User", value=user.mention)
    embed.add_field(name="Reason", value=reason)
    embed.set_footer(text=f"By {interaction.user}")
    await interaction.response.send_message(embed=embed)


@app_commands.command(name="tempmute", description="Temporarily mute a member")
@app_commands.describe(user="Member", minutes="Duration (minutes)", reason="Reason (optional)")
async def tempmute(interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str = "No reason given"):
    if not is_staff(interaction.user):
        await interaction.response.send_message("Staff only.", ephemeral=True)
        return
    if minutes < 1 or minutes > 10080:
        await interaction.response.send_message("Duration: 1–10080 minutes.", ephemeral=True)
        return

    muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not muted_role:
        await interaction.response.send_message("Muted role not found.", ephemeral=True)
        return

    await user.add_roles(muted_role, reason=f"Temp mute • {reason}")

    await interaction.response.send_message(f"{user.mention} muted for **{minutes}** minutes.", ephemeral=False)


@app_commands.command(name="tempban", description="Temporarily ban a member")
@app_commands.describe(user="Member", minutes="Duration (minutes)", reason="Reason (optional)")
async def tempban(interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str = "No reason given"):
    if not is_staff(interaction.user):
        await interaction.response.send_message("Staff only.", ephemeral=True)
        return
    if minutes < 1 or minutes > 10080:
        await interaction.response.send_message("Duration: 1–10080 minutes.", ephemeral=True)
        return

    await interaction.guild.ban(user, reason=f"Temp ban • {reason}")

    await interaction.response.send_message(f"{user.mention} banned for **{minutes}** minutes.", ephemeral=False)


@app_commands.command(name="staffstats", description="View your staff statistics (owner only)")
async def staffstats(interaction: discord.Interaction):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("This command is restricted.", ephemeral=True)
        return

    await interaction.response.send_message("Staff statistics tracking has been removed.", ephemeral=True)


# ================= REGISTER ALL COMMANDS =================

bot.tree.add_command(duel, guild=guild_obj)
bot.tree.add_command(staff_cmd, guild=guild_obj)
bot.tree.add_command(pgamemode, guild=guild_obj)
bot.tree.add_command(botsay, guild=guild_obj)
bot.tree.add_command(send_ticket_panel, guild=guild_obj)
bot.tree.add_command(warn, guild=guild_obj)
bot.tree.add_command(tempmute, guild=guild_obj)
bot.tree.add_command(tempban, guild=guild_obj)
bot.tree.add_command(staffstats, guild=guild_obj)

# ==========================================


bot.run(TOKEN)
