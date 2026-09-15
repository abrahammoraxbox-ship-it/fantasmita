import time,discord
from discord.ext import commands
class M(commands.Cog):
 def __init__(self,b):self.b=b
 async def log(self,g,t):
  row=self.b.db.execute("SELECT logs_ch FROM guild_config WHERE guild_id=?",(g.id,)).fetchone()
  ch=g.get_channel(row[0]) if row and row[0] else None
  if ch:await ch.send(t)
 @commands.hybrid_command(description="Advertir")
 @commands.has_guild_permissions(moderate_members=True)
 async def warn(self,ctx,m:discord.Member,*,razon="Sin razón"):
  self.b.db.execute("INSERT INTO warnings(guild_id,user_id,moderator_id,reason,created) VALUES(?,?,?,?,?)",(ctx.guild.id,m.id,ctx.author.id,razon,time.time()))
  await ctx.send(f"⚠️ {m.mention}: {razon}");await self.log(ctx.guild,f"⚠️ {ctx.author} → {m}: {razon}")
 @commands.hybrid_command(description="Limpiar mensajes")
 @commands.has_guild_permissions(manage_messages=True)
 async def limpiar(self,ctx,cantidad:int=10):await ctx.channel.purge(limit=max(1,min(cantidad,100))+1)
 @commands.command()
 @commands.has_guild_permissions(kick_members=True)
 async def expulsar(self,ctx,m:discord.Member,*,razon="Sin razón"):await m.kick(reason=razon)
 @commands.command()
 @commands.has_guild_permissions(ban_members=True)
 async def ban(self,ctx,m:discord.Member,*,razon="Sin razón"):await m.ban(reason=razon)
async def setup(b):await b.add_cog(M(b))
