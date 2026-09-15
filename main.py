import os, asyncio, traceback
from selftest import run as run_selftest
run_selftest()

import discord
from discord.ext import commands
from core import Database, ensure_structure
from views import TermsView, AccessRequestView, TicketView, TicketCloseView, VoiceControlView, MusicControlView, DecisionView

BASE=os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(BASE,"data"),exist_ok=True)
os.makedirs(os.path.join(BASE,"backups"),exist_ok=True)
TOKEN=os.getenv("DISCORD_TOKEN")
if not TOKEN: raise RuntimeError("Falta DISCORD_TOKEN. Usa INICIAR_ESTABLE.bat")

intents=discord.Intents.default()
intents.guilds=True; intents.members=True; intents.message_content=True

class EcoBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!",intents=intents,help_command=None)
        self.db=Database(os.path.join(BASE,"data","eco_estable.db"))
        self.locks={}
    async def setup_hook(self):
        exts=["cogs.community","cogs.economy","cogs.moderation","cogs.owner",
              "cogs.voice","cogs.social","cogs.tickets","cogs.security","cogs.events","cogs.cleanup",
              "cogs.music","cogs.progression","cogs.competitive","cogs.integrations"]
        for ext in exts:
            print("Cargando:",ext)
            await self.load_extension(ext)
        self.add_view(TermsView(self))
        self.add_view(AccessRequestView(self))
        self.add_view(TicketView(self))
        self.add_view(TicketCloseView(self))
        self.add_view(VoiceControlView(self))
        self.add_view(MusicControlView(self))
        for gid,uid,msgid in self.db.execute(
            "SELECT guild_id,user_id,message_id FROM access_requests WHERE status='pending' AND message_id>0"
        ).fetchall():
            try: self.add_view(DecisionView(self,uid,persistent=True),message_id=msgid)
            except Exception as e: print("PENDING VIEW",gid,uid,repr(e))
        try:
            synced=await self.tree.sync()
            print(f"✅ Slash commands sincronizados: {len(synced)}")
        except Exception as e: print("⚠️ Slash sync:",repr(e))

bot=EcoBot()

async def configure(g):
    lock=bot.locks.setdefault(g.id,asyncio.Lock())
    async with lock: await ensure_structure(bot,g)

@bot.event
async def on_ready():
    print("="*78)
    print(f"👻 EL ECO DEL VACÍO • INTEGRADO PRO | {bot.user}")
    for g in bot.guilds:
        try:
            await configure(g)
            print(f"✅ {g.name}: verificado y operativo")
        except Exception:
            traceback.print_exc()
    await bot.change_presence(activity=discord.Game(name="🌌 El Eco del Vacío • INTEGRADO"))

@bot.event
async def on_guild_join(g): await configure(g)

@bot.event
async def on_command_error(ctx,error):
    if isinstance(error,commands.CommandNotFound): return
    if isinstance(error,commands.MissingPermissions): return await ctx.send("🔒 No tienes permisos para esa acción.")
    if isinstance(error,commands.MissingRequiredArgument): return await ctx.send("⚠️ Falta información en el comando. Usa `!comandos`.")
    print("ERROR DE COMANDO:",repr(error))
    try: await ctx.send("⚠️ Ocurrió un error y quedó registrado en consola.")
    except discord.HTTPException as e: print("ERROR RESPUESTA:",repr(e))

async def main():
    async with bot: await bot.start(TOKEN)
asyncio.run(main())
