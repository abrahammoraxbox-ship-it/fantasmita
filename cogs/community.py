import time,random,discord
from discord.ext import commands
def level(x):return int((x/100)**0.5)
class Community(commands.Cog):
 def __init__(self,b):self.b=b;self.last_text={}
 @commands.Cog.listener()
 async def on_member_join(self,m):
  # Auto-repara los paneles de entrada antes de dejar al usuario en Pendiente.
  try:
   from core import repair_onboarding
   await repair_onboarding(self.b,m.guild)
  except Exception as e:print('ONBOARDING REPAIR:',repr(e))
  gamer=discord.utils.get(m.guild.roles,name='🎮 Gamer');p=discord.utils.get(m.guild.roles,name='⏳ Pendiente')
  if gamer and gamer in m.roles:return
  if p:
   try:await m.add_roles(p)
   except discord.Forbidden as e:print('JOIN ROLE:',repr(e))
 @commands.Cog.listener()
 async def on_message(self,m):
  if m.author.bot or not m.guild or m.content.startswith('!'):return
  gamer=discord.utils.get(m.guild.roles,name='🎮 Gamer')
  if not gamer or gamer not in m.author.roles:return
  txt=' '.join(m.content.lower().split())
  if len(txt)<8 or self.last_text.get((m.guild.id,m.author.id))==txt:return
  self.last_text[(m.guild.id,m.author.id)]=txt
  xp,c,msg,d,s,r,last,lr=self.b.db.stats(m.guild.id,m.author.id);now=time.time()
  self.b.db.execute('UPDATE users SET messages=messages+1 WHERE guild_id=? AND user_id=?',(m.guild.id,m.author.id))
  if now-last<60:return
  gain=random.randint(8,14);new=xp+gain;self.b.db.execute('UPDATE users SET xp=?,coins=coins+?,last_xp=? WHERE guild_id=? AND user_id=?',(new,random.randint(1,3),now,m.guild.id,m.author.id))
  if level(new)>level(xp):await m.channel.send(f'🔥 {m.author.mention} subió a **Nivel {level(new)}**.',delete_after=120)
 @commands.hybrid_command(description='Tu perfil gamer')
 async def perfil(self,ctx,m:discord.Member=None):
  m=m or ctx.author;xp,c,msg,d,s,r,last,lr=self.b.db.stats(ctx.guild.id,m.id);e=discord.Embed(title=f'👻 {m.display_name}',colour=0x8B5CF6);e.set_thumbnail(url=m.display_avatar.url)
  for n,v in [('⭐ Nivel',level(xp)),('✨ XP',xp),('🪙 Coins',c),('🔥 Racha',s),('🤝 Reputación',r),('💬 Mensajes',msg)]:e.add_field(name=n,value=v)
  await ctx.send(embed=e)
 @commands.hybrid_command(description='Da reputación a otra persona')
 async def reputacion(self,ctx,m:discord.Member):
  if m.id==ctx.author.id or m.bot:return await ctx.send('❌ No puedes darte reputación a ti mismo ni a bots.')
  *_,lastrep=self.b.db.stats(ctx.guild.id,ctx.author.id);now=time.time()
  if now-lastrep<86400:return await ctx.send('⏳ Puedes dar reputación una vez cada 24 horas.')
  self.b.db.execute('UPDATE users SET reputation=reputation+1 WHERE guild_id=? AND user_id=?',(ctx.guild.id,m.id));self.b.db.execute('UPDATE users SET last_rep=? WHERE guild_id=? AND user_id=?',(now,ctx.guild.id,ctx.author.id));await ctx.send(f'🤝 +1 reputación para {m.mention}.')
 @commands.hybrid_command(description='Ranking')
 async def top(self,ctx):
  rows=self.b.db.execute('SELECT user_id,xp FROM users WHERE guild_id=? ORDER BY xp DESC LIMIT 10',(ctx.guild.id,)).fetchall();await ctx.send(embed=discord.Embed(title='🏆 TOP',description='\n'.join(f'`#{i}` <@{u}> • {x} XP' for i,(u,x) in enumerate(rows,1)) or 'Sin datos.',colour=0xF59E0B))
 @commands.hybrid_command(description='Centro de ayuda')
 async def comandos(self,ctx):
  text="""**Perfil:** `/perfil` `/top` `/reputacion` `/logros` `/temporada`
**Economía:** `/daily` `/saldo` `/coinflip` `/tienda` `/comprar` `/inventario`
**Misiones:** `/mision` `/semanal`
**Música:** `/play` `/pause` `/resume` `/skip` `/queue` `/volume` `/nowplaying` `/stop`
**Clanes/LFG:** `/clan_crear` `/clan_unir` `/clan_salir` `/clan_info` `/lfg` `/lfg_lista`
**Torneos:** `/torneo_crear` `/torneos` `/torneo_resultado`
**Social:** `/vincular` `/vinculos`
🎫 Tickets • 🎧 Salas privadas • 👑 `!panel` `!panico` `!seguridad` `!backup`"""
  await ctx.send(embed=discord.Embed(title="🧠 CENTRO DE COMANDOS",description=text,colour=0x7C3AED))

async def setup(b):await b.add_cog(Community(b))
