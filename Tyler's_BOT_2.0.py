keep_alive()

# ===================== CONFIG =====================
GUILD_ID = 1452691239152521266
MAX_PLAYERS = 8
BEST_OF = 3
DEFAULT_ELO = 1000
ELO_GAIN = 25

TEAM1_VC = "Team 1"
TEAM2_VC = "Team 2"

MAP_POOL = [
    "Nuketown", "Firing Range", "Summit", "Grid",
    "Jungle", "Cracked", "Crisis", "Hanoi"
]

STATS_FILE = "stats.json"
HISTORY_FILE = "history.json"

# ===================== BOT =====================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
guild_obj = discord.Object(id=GUILD_ID)

# ===================== HELPERS =====================
def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def make_embed(title="", description="", color=0x00ff00):
    return discord.Embed(title=title, description=description, color=color)

# ===================== STATE =====================
STATS = load_json(STATS_FILE, {})
HISTORY = load_json(HISTORY_FILE, [])

class ScrimManager:
    def reset(self):
        self.queue = []
        self.captains = []
        self.teams = {"Team 1": [], "Team 2": []}
        self.scores = {"Team 1": 0, "Team 2": 0}
        self.locked = False
        self.pick_turn = None
        self.map_turn = None
        self.maps_left = MAP_POOL.copy()
        self.final_map = None

scrim = ScrimManager()
scrim.reset()

# ===================== STATS =====================
def ensure_player(pid):
    STATS.setdefault(pid, {"wins": 0, "losses": 0, "elo": DEFAULT_ELO})

def update_elo(winner):
    for team, players in scrim.teams.items():
        for p in players:
            pid = str(p.id)
            ensure_player(pid)
            if team == winner:
                STATS[pid]["wins"] += 1
                STATS[pid]["elo"] += ELO_GAIN
            else:
                STATS[pid]["losses"] += 1
                STATS[pid]["elo"] -= ELO_GAIN
    save_json(STATS_FILE, STATS)

def format_elo_change(player, old_elo, new_elo, wins, losses):
    diff = new_elo - old_elo
    sign = "+" if diff >= 0 else ""
    return f"{player.name}: {old_elo} → {new_elo} ({sign}{diff}) | W/L: {wins}/{losses}"

# ===================== VC MOVE =====================
async def move_teams(guild):
    vc1 = discord.utils.get(guild.voice_channels, name=TEAM1_VC)
    vc2 = discord.utils.get(guild.voice_channels, name=TEAM2_VC)
    if not vc1 or not vc2:
        return
    for p in scrim.teams["Team 1"]:
        if p.voice:
            await p.move_to(vc1)
    for p in scrim.teams["Team 2"]:
        if p.voice:
            await p.move_to(vc2)

# ===================== MAP VETO EMBED =====================
def map_veto_embed(current_captain):
    banned_maps = [m for m in MAP_POOL if m not in scrim.maps_left]
    embed = make_embed("🗺️ Map Veto Phase", f"Next ban: {current_captain.mention}", 0x9b59b6)
    embed.add_field(name="Remaining Maps", value="\n".join(scrim.maps_left) or "None", inline=True)
    embed.add_field(name="Banned Maps", value="\n".join(banned_maps) or "None", inline=True)
    return embed

# ===================== PICK BUTTONS =====================
class PickButton(Button):
    def __init__(self, player):
        super().__init__(label=player.name, style=discord.ButtonStyle.primary)
        self.player = player

    async def callback(self, i: discord.Interaction):
        if i.user != scrim.pick_turn:
            return await i.response.send_message(embed=make_embed("Not your pick", "Wait for your turn!", 0xf1c40f), ephemeral=True)
        team = "Team 1" if i.user == scrim.captains[0] else "Team 2"
        scrim.teams[team].append(self.player)
        scrim.queue.remove(self.player)
        self.disabled = True
        self.style = discord.ButtonStyle.secondary
        if scrim.queue:
            scrim.pick_turn = scrim.captains[1] if scrim.pick_turn == scrim.captains[0] else scrim.captains[0]
            embed = make_embed(f"Pick: {team}", f"{self.player.mention} → **{team}**\nNext pick: {scrim.pick_turn.mention}", 0x3498db if team=="Team 1" else 0xe74c3c)
            embed.add_field(name="Team 1", value="\n".join(p.name for p in scrim.teams["Team 1"]), inline=True)
            embed.add_field(name="Team 2", value="\n".join(p.name for p in scrim.teams["Team 2"]), inline=True)
            await i.response.edit_message(embed=embed, view=PickView())
        else:
            scrim.map_turn = random.choice(scrim.captains)
            embed = map_veto_embed(scrim.map_turn)
            await i.response.edit_message(embed=embed, view=MapView())

class PickView(View):
    def __init__(self):
        super().__init__(timeout=None)
        for p in scrim.queue:
            self.add_item(PickButton(p))

# ===================== MAP BUTTONS =====================
class MapButton(Button):
    def __init__(self, map_name):
        super().__init__(label=map_name, style=discord.ButtonStyle.secondary)
        self.map_name = map_name

    async def callback(self, i: discord.Interaction):
        scrim.maps_left.remove(self.map_name)
        if len(scrim.maps_left) == 1:
            scrim.final_map = scrim.maps_left[0]
            await move_teams(i.guild)
            embed = make_embed("🗺️ Final Map", f"**{scrim.final_map}**", 0x2ecc71)
            await i.response.edit_message(embed=embed, view=None)
            return
        scrim.map_turn = scrim.captains[1] if scrim.map_turn == scrim.captains[0] else scrim.captains[0]
        embed = map_veto_embed(scrim.map_turn)
        await i.response.edit_message(embed=embed, view=MapView())

class MapView(View):
    def __init__(self):
        super().__init__(timeout=None)
        for m in scrim.maps_left:
            self.add_item(MapButton(m))

# ===================== EVENTS =====================
@bot.event
async def on_ready():
    await tree.sync(guild=guild_obj)
    print(f"✅ Logged in as {bot.user}")

# ===================== COMMANDS =====================
@tree.command(name="join", description="Join scrim queue", guild=guild_obj)
async def join(i: discord.Interaction):
    if scrim.locked:
        return await i.response.send_message(embed=make_embed("Queue Locked", "You can't join now.", 0xf1c40f), ephemeral=True)
    if i.user in scrim.queue:
        return await i.response.send_message(embed=make_embed("Already in queue", f"{i.user.mention} is already queued.", 0xf1c40f), ephemeral=True)
    scrim.queue.append(i.user)
    embed = make_embed("Queue Update", f"{i.user.mention} joined! ({len(scrim.queue)}/{MAX_PLAYERS})", 0x2ecc71)
    embed.add_field(name="Current Queue", value="\n".join([p.name for p in scrim.queue]), inline=False)
    await i.response.send_message(embed=embed)
    if len(scrim.queue) == MAX_PLAYERS:
        scrim.locked = True
        scrim.queue.sort(key=lambda p: STATS.get(str(p.id), {"elo": DEFAULT_ELO})["elo"], reverse=True)
        scrim.captains = [scrim.queue.pop(0), scrim.queue.pop(0)]
        scrim.teams["Team 1"].append(scrim.captains[0])
        scrim.teams["Team 2"].append(scrim.captains[1])
        scrim.pick_turn = random.choice(scrim.captains)
        embed = make_embed("🧢 Captains", f"Team 1: {scrim.captains[0].mention}\nTeam 2: {scrim.captains[1].mention}\nFirst pick: {scrim.pick_turn.mention}", 0x9b59b6)
        await i.channel.send(embed=embed, view=PickView())

@tree.command(name="score", description="Add a point", guild=guild_obj)
@app_commands.choices(team=[
    app_commands.Choice(name="Team 1", value="Team 1"),
    app_commands.Choice(name="Team 2", value="Team 2"),
])
async def score(i: discord.Interaction, team: app_commands.Choice[str]):
    scrim.scores[team.value] += 1
    if scrim.scores[team.value] >= (BEST_OF // 2 + 1):
        old_elos = {p.id: STATS.get(str(p.id), {"elo": DEFAULT_ELO})["elo"] for team in scrim.teams.values() for p in team}
        update_elo(team.value)
        embed = make_embed(f"🏆 Match Finished — {team.value}", f"Map: {scrim.final_map}", 0x3498db if team.value=="Team 1" else 0xe74c3c)
        embed.add_field(name="Team 1", value="\n".join([p.name for p in scrim.teams["Team 1"]]), inline=True)
        embed.add_field(name="Team 2", value="\n".join([p.name for p in scrim.teams["Team 2"]]), inline=True)
        elo_lines = []
        for team_name, players in scrim.teams.items():
            for p in players:
                pid = str(p.id)
                new_elo = STATS[pid]["elo"]
                wins = STATS[pid]["wins"]
                losses = STATS[pid]["losses"]
                elo_lines.append(format_elo_change(p, old_elos[p.id], new_elo, wins, losses))
        embed.add_field(name="Elo Changes", value="\n".join(elo_lines), inline=False)
        HISTORY.append({
            "map": scrim.final_map,
            "winner": team.value,
            "teams": { "Team 1": [p.name for p in scrim.teams["Team 1"]],
                       "Team 2": [p.name for p in scrim.teams["Team 2"]] },
            "elo_changes": elo_lines
        })
        save_json(HISTORY_FILE, HISTORY)
        scrim.reset()
    else:
        embed = make_embed(f"Score Update", f"Team 1: {scrim.scores['Team 1']}\nTeam 2: {scrim.scores['Team 2']}", 0x2ecc71)
    await i.response.send_message(embed=embed)

@tree.command(name="rank", description="Your Elo", guild=guild_obj)
async def rank(i: discord.Interaction):
    ensure_player(str(i.user.id))
    s = STATS[str(i.user.id)]
    embed = make_embed(f"{i.user.name}'s Stats", f"Elo: **{s['elo']}**\nW/L: {s['wins']} / {s['losses']}", 0x2ecc71)
    await i.response.send_message(embed=embed)

@tree.command(name="top", description="Top 10 Elo", guild=guild_obj)
async def top(i: discord.Interaction):
    ranked = sorted(STATS.items(), key=lambda x: x[1]["elo"], reverse=True)[:10]
    embed = make_embed("🏆 Top 10 Elo", "", 0x9b59b6)
    for idx, (pid, data) in enumerate(ranked, 1):
        member = i.guild.get_member(int(pid))
        name = member.name if member else "Unknown"
        embed.add_field(name=f"{idx}. {name}", value=f"Elo: {data['elo']} | W/L: {data['wins']}/{data['losses']}", inline=False)
    await i.response.send_message(embed=embed)

@tree.command(name="history", description="Recent matches", guild=guild_obj)
async def history(i: discord.Interaction):
    if not HISTORY:
        return await i.response.send_message(embed=make_embed("No Matches", "No match history yet.", 0xf1c40f))
    embed = make_embed("📜 Recent Matches", "", 0x1abc9c)
    last = HISTORY[-5:]
    for idx, m in enumerate(last, 1):
        embed.add_field(name=f"Match {idx} — {m['map']}", value=f"Winner: **{m['winner']}**", inline=False)
    await i.response.send_message(embed=embed)

@tree.command(name="reset", description="Admin reset", guild=guild_obj)
async def reset(i: discord.Interaction):
    if not i.user.guild_permissions.administrator:
        return await i.response.send_message(embed=make_embed("Admin Only", "You need admin permissions.", 0xf1c40f), ephemeral=True)
    scrim.reset()
    await i.response.send_message(embed=make_embed("Scrim Reset", "All scrim data has been reset.", 0x2ecc71))

# ===================== RUN =====================
bot.run(os.environ["TOKEN"])



