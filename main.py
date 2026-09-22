import os, asyncio, traceback
from selftest import run as run_selftest
run_selftest()

import discord
from discord.ext import commands
from core import Database, ensure_structure
from views import TermsView, AccessRequestView, TicketView, TicketCloseView, VoiceControlView, DecisionView, OwnerPanel

# Limpieza anti-spam: toda respuesta normal enviada con ctx.send desaparece en 2 minutos.
# Los paneles persistentes usan channel.send/ensure_panel y NO pasan por esta regla.
COMMAND_MESSAGE_TTL = 120
_original_context_send = commands.Context.send
async def _clean_context_send(self, *args, **kwargs):
    kwargs.setdefault("delete_after", COMMAND_MESSAGE_TTL)
    return await _original_context_send(self, *args, **kwargs)
commands.Context.send = _clean_context_send

BASE=os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(BASE,"data"),exist_ok=True)
os.makedirs(os.path.join(BASE,"backups"),exist_ok=True)

# En hosting, cargar DISCORD_TOKEN desde .env si no existe como variable del sistema
TOKEN=os.getenv("DISCORD_TOKEN")

if not TOKEN:
    env_path=os.path.join(BASE,".env")
    if os.path.exists(env_path):
        with open(env_path,"r",encoding="utf-8") as f:
            for line in f:
                line=line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key,value=line.split("=",1)
                if key.strip()=="DISCORD_TOKEN":
                    TOKEN=value.strip().strip('"').strip("'")
                    break

if not TOKEN:
    raise RuntimeError("Falta DISCORD_TOKEN")

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
        # Panel del fundador: registrar callbacks persistentes tras reinicios.
        self.add_view(OwnerPanel())
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
async def on_command(ctx):
    # También limpia el texto !comando escrito por el usuario. No afecta mensajes normales.
    try:
        await ctx.message.delete(delay=COMMAND_MESSAGE_TTL)
    except (discord.NotFound,discord.Forbidden,discord.HTTPException):
        pass

@bot.event
async def on_raw_message_delete(payload):
    # Si alguien elimina un panel estructural, se reconstruye sin crear duplicados.
    if not payload.guild_id:return
    row=bot.db.execute(
        "SELECT panel_key FROM panel_messages WHERE guild_id=? AND message_id=?",
        (payload.guild_id,payload.message_id)
    ).fetchone()
    if not row:return
    if row[0] not in {"TERMS","ACCESS","ROLES","HELP","TICKET","VOICE","OWNER","MUSIC"}:return
    g=bot.get_guild(payload.guild_id)
    if not g:return
    print(f"♻️ Panel persistente eliminado ({row[0]}). Reparando...")
    # Borra primero el ID muerto; así ensure_panel crea/encuentra el reemplazo sin consultar 404 repetidamente.
    bot.db.execute("DELETE FROM panel_messages WHERE guild_id=? AND message_id=?",
                   (payload.guild_id,payload.message_id))
    try:
        await configure(g)
    except Exception:
        traceback.print_exc()

@bot.event
async def on_raw_bulk_message_delete(payload):
    # Discord puede borrar varios mensajes de una vez (purge). Si uno era un panel
    # persistente, reconstruimos la estructura una sola vez.
    if not payload.guild_id:return
    ids=tuple(payload.message_ids)
    if not ids:return
    placeholders=",".join("?" for _ in ids)
    row=bot.db.execute(
        f"SELECT panel_key FROM panel_messages WHERE guild_id=? AND message_id IN ({placeholders}) LIMIT 1",
        (payload.guild_id,*ids)
    ).fetchone()
    if not row:return
    g=bot.get_guild(payload.guild_id)
    if not g:return
    bot.db.execute(
        f"DELETE FROM panel_messages WHERE guild_id=? AND message_id IN ({placeholders})",
        (payload.guild_id,*ids)
    )
    try:await configure(g)
    except Exception:traceback.print_exc()

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
