import io,time,discord
from discord.ext import commands
async def close_ticket(bot,channel,actor,reason="Resuelto"):
    row=bot.db.execute("SELECT user_id,closed,type FROM tickets WHERE channel_id=? AND guild_id=?",(channel.id,channel.guild.id)).fetchone()
    if not row:return False,"Este canal no es un ticket registrado."
    owner_id,closed,kind=row
    if not (actor.id in {channel.guild.owner_id,owner_id} or actor.guild_permissions.manage_messages):return False,"🔒 Sin permiso."
    if closed:return False,"Ya está cerrado."
    # Transcript before deletion.
    lines=[]
    try:
        async for m in channel.history(limit=500,oldest_first=True):
            lines.append(f"[{m.created_at.isoformat()}] {m.author} ({m.author.id}): {m.clean_content}")
    except (discord.Forbidden,discord.HTTPException) as e:print("TRANSCRIPT READ:",repr(e))
    cfg=bot.db.execute("SELECT logs_ch FROM guild_config WHERE guild_id=?",(channel.guild.id,)).fetchone()
    log=channel.guild.get_channel(cfg[0]) if cfg else None
    if log:
        try:
            data="\n".join(lines).encode("utf-8")
            await log.send(f"🎫 **{kind}** `{channel.name}` cerrado por {actor.mention}. Razón: **{reason}**",file=discord.File(io.BytesIO(data),filename=f"{channel.name}-transcript.txt"))
        except (discord.Forbidden,discord.HTTPException) as e:print("TRANSCRIPT LOG:",repr(e))
    bot.db.execute("UPDATE tickets SET closed=?,closed_by=?,reason=? WHERE channel_id=?",(time.time(),actor.id,reason,channel.id))
    try:await channel.delete(reason=f"Ticket cerrado por {actor}: {reason}");return True,"Ticket cerrado."
    except (discord.Forbidden,discord.HTTPException) as e:
        bot.db.execute("UPDATE tickets SET closed=0,closed_by=0,reason='' WHERE channel_id=?",(channel.id,));print("TICKET DELETE:",repr(e));return False,"❌ No pude borrar el canal."
class Tickets(commands.Cog):
    def __init__(self,b):self.b=b
    @commands.command()
    async def cerrarticket(self,ctx,*,razon="Resuelto"):
        ok,msg=await close_ticket(self.b,ctx.channel,ctx.author,razon)
        if not ok:await ctx.send(msg)
async def setup(b):await b.add_cog(Tickets(b))
