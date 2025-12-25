import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
import json

# ---------------- TOKEN (dummy) ----------------
TOKEN = "jtlzf6DWWVJCRpjkIRP38EFZ-CczFPrw"
GUILD_ID = 1452691239152521266  

# ---------------- CONFIG ----------------
MAX_PLAYERS = 8
WIN_SCORE = 2
PICK_TIMEOUT = 30  # seconds per pick

MAP_POOL = [
    "Nuketown", "Firing Range", "Summit", "Grid",
    "Jungle", "Cracked", "Crisis", "Hanoi",
    "Havana", "Launch", "Radiation", "WMD"
]

TEAM1_VC = "Team 1"
TEAM2_VC = "Team 2"

# ---------------- STATE ----------------
QUEUE = []
CAPTAINS = []
TEAMS = {"Team 1": [], "Team 2": []}
SCORES = {"Team 1": 0, "Team 2": 0}
MAPS_LEFT = []
LOCKED = False
PICK_TURN = None
DRAFT_MSG = None

# ---------------- STATS ----------------
STATS_FILE = "stats.json"
try:
    with open(STATS_FILE, "r") as f:
        STATS = json.load(f)
except:
    STATS = {}

def save_stats():
    with open(STATS_FILE, "w") as f:
        json.dump(STATS, f, indent=2)

# ---------------- BOT ----------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---------------- HELPERS ----------------
def is_admin(i: discord.Interaction):
    return i.user.guild_permissions.administrator

def reset_match():
    global QUEUE, CAPTAINS, TEAMS, SCORES, MAPS_LEFT, LOCKED, PICK_TURN, DRAFT_MSG
    QUEUE.clear()
    CAPTAINS.clear()
    TEAMS = {"Team 1": [], "Team 2": []}
    SCORES = {"Team 1": 0, "Team 2": 0}
    MAPS_LEFT = MAP_POOL.copy()
    LOCKED = False
    PICK_TURN = None
    DRAFT_MSG = None

# ---------------- AUTOCOMPLETE ----------------
async def player_auto(i, current: str):
    return [
        app_commands.Choice(name=p.name, value=str(p.id))
        for p in QUEUE if current.lower() in p.name.lower()
    ][:25]

async def map_auto(i, current: str):
    return [
        app_commands.Choice(name=m, value=m)
        for m in MAPS_LEFT if current.lower() in m.lower()
    ][:25]

# ---------------- EVENTS ----------------
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    print(f"✅ Logged in as {bot.user}")
    print(f"Slash commands synced for guild {GUILD_ID}")

# ---------------- QUEUE COMMANDS ----------------
@tree.command(name="join", description="Join the scrim queue")
async def join(i: discord.Interaction):
    global LOCKED
    if LOCKED:
        return await i.response.send_message("🔒 Queue locked", ephemeral=True)
    if i.user in QUEUE:
        return await i.response.send_message("Already in the queue", ephemeral=True)
    QUEUE.append(i.user)
    await i.response.send_message(f"✅ {i.user.mention} joined ({len(QUEUE)}/{MAX_PLAYERS})")

@tree.command(name="leave", description="Leave the scrim queue")
async def leave(i: discord.Interaction):
    removed = False
    if i.user in QUEUE:
        QUEUE.remove(i.user)
        removed = True
        await i.response.send_message("❌ Left queue")
    for team_name, members in TEAMS.items():
        if i.user in members:
            members.remove(i.user)
            removed = True
            await i.channel.send(f"❌ {i.user.mention} left **{team_name}**")
            break
    if not removed:
        await i.response.send_message("You are not in the queue or any team", ephemeral=True)

# ---------------- SCRIM / DRAFT ----------------
async def start_scrim(channel):
    global LOCKED, CAPTAINS, PICK_TURN, MAPS_LEFT
    LOCKED = True
    MAPS_LEFT = MAP_POOL.copy()
    random.shuffle(QUEUE)
    CAPTAINS = [QUEUE.pop(0), QUEUE.pop(0)]
    TEAMS["Team 1"].append(CAPTAINS[0])
    TEAMS["Team 2"].append(CAPTAINS[1])
    PICK_TURN = random.choice(CAPTAINS)
    await channel.send(
        f"🧢 **Captains**\n"
        f"Team 1: {CAPTAINS[0].mention}\n"
        f"Team 2: {CAPTAINS[1].mention}\n\n"
        f"🎯 First pick: {PICK_TURN.mention}"
    )

# ---------------- PICK ----------------
@tree.command(name="pick", description="Captain pick a player")
@app_commands.autocomplete(player=player_auto)
async def pick(i: discord.Interaction, player: str):
    global PICK_TURN
    if i.user != PICK_TURN:
        return await i.response.send_message("❌ Not your turn", ephemeral=True)
    member = i.guild.get_member(int(player))
    if not member or member not in QUEUE:
        return await i.response.send_message("Invalid player", ephemeral=True)
    team = "Team 1" if i.user == CAPTAINS[0] else "Team 2"
    TEAMS[team].append(member)
    QUEUE.remove(member)
    PICK_TURN = CAPTAINS[1] if PICK_TURN == CAPTAINS[0] else CAPTAINS[0] if QUEUE else None
    await i.response.send_message(f"✅ {member.mention} joined **{team}**")

# ---------------- SCORE ----------------
@tree.command(name="score", description="Update team score")
@app_commands.choices(team=[
    app_commands.Choice(name="Team 1", value="Team 1"),
    app_commands.Choice(name="Team 2", value="Team 2")
])
async def score(i: discord.Interaction, team: app_commands.Choice[str]):
    t = team.value
    SCORES[t] += 1
    if SCORES[t] >= WIN_SCORE:
        await i.response.send_message(f"🏆 **{t} WINS!**")
        reset_match()
    else:
        await i.response.send_message(f"📊 Current score: {SCORES}")

# ---------------- RESET ----------------
@tree.command(name="reset", description="Reset the current match")
async def reset(i: discord.Interaction):
    if not is_admin(i):
        return await i.response.send_message("Admin only", ephemeral=True)
    reset_match()
    await i.response.send_message("♻️ Match reset")

# ---------------- RUN BOT ----------------
bot.run(os.environ["TOKEN"])



