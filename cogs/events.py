import datetime,time
from discord.ext import commands
class Events(commands.Cog):
 def __init__(self,b):self.b=b;self.last={}
 @commands.Cog.listener()
 async def on_message(self,m):
  if m.author.bot or not m.guild or m.content.startswith('!'):return
  import discord
  gamer=discord.utils.get(m.guild.roles,name='🎮 Gamer')
  if not gamer or gamer not in m.author.roles:return
  norm=' '.join(m.content.lower().split());key=(m.guild.id,m.author.id);old=self.last.get(key)
  if len(norm)<8 or (old and (old[0]==norm or time.time()-old[1]<10)):return
  self.last[key]=(norm,time.time())
  day=datetime.date.today().isoformat()
  self.b.db.execute("INSERT OR IGNORE INTO missions(guild_id,user_id,day) VALUES(?,?,?)",(m.guild.id,m.author.id,day))
  self.b.db.execute("UPDATE missions SET progress=MIN(target,progress+1) WHERE guild_id=? AND user_id=? AND day=?",(m.guild.id,m.author.id,day))
 @commands.hybrid_command(description="Tu misión diaria")
 async def mision(self,ctx):
  day=datetime.date.today().isoformat()
  self.b.db.execute("INSERT OR IGNORE INTO missions(guild_id,user_id,day) VALUES(?,?,?)",(ctx.guild.id,ctx.author.id,day))
  p,t,c=self.b.db.execute("SELECT progress,target,claimed FROM missions WHERE guild_id=? AND user_id=? AND day=?",(ctx.guild.id,ctx.author.id,day)).fetchone()
  if p>=t and not c:
   self.b.db.execute("UPDATE missions SET claimed=1 WHERE guild_id=? AND user_id=? AND day=?",(ctx.guild.id,ctx.author.id,day))
   self.b.db.execute("UPDATE users SET coins=coins+100,xp=xp+50 WHERE guild_id=? AND user_id=?",(ctx.guild.id,ctx.author.id))
   return await ctx.send("🎯 **Misión completada:** +50 XP y +100 Void Coins.")
  await ctx.send(f"🎯 **Misión diaria:** participa con {t} mensajes. Progreso **{p}/{t}**."+(" ✅ Recompensa ya reclamada." if c else ""))
async def setup(b):await b.add_cog(Events(b))
