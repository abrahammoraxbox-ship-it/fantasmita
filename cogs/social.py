import random,discord
from discord.ext import commands
class Social(commands.Cog):
 def __init__(self,b):self.b=b
 @commands.hybrid_command(description='Publica una sugerencia')
 async def sugerir(self,ctx,*,texto):
  cfg=self.b.db.execute('SELECT suggest_ch FROM guild_config WHERE guild_id=?',(ctx.guild.id,)).fetchone();ch=ctx.guild.get_channel(cfg[0]) if cfg else None
  if not ch:return await ctx.send('No encuentro el canal de sugerencias.')
  e=discord.Embed(title='💡 SUGERENCIA • PENDIENTE',description=texto,colour=0x7C3AED);e.set_author(name=ctx.author.display_name,icon_url=ctx.author.display_avatar.url)
  m=await ch.send(embed=e);await m.add_reaction('👍');await m.add_reaction('👎')
  self.b.db.execute('INSERT OR REPLACE INTO suggestions VALUES(?,?,?,?,?)',(m.id,ctx.guild.id,ctx.author.id,'pending',texto));await ctx.send('✅ Publicada.')
 @commands.command()
 @commands.has_guild_permissions(manage_messages=True)
 async def sugerenciaestado(self,ctx,message_id:int,estado:str):
  estado=estado.lower()
  if estado not in {'pendiente','revision','aceptada','rechazada','implementada'}:return await ctx.send('Usa: pendiente, revision, aceptada, rechazada o implementada.')
  row=self.b.db.execute('SELECT text FROM suggestions WHERE message_id=? AND guild_id=?',(message_id,ctx.guild.id)).fetchone()
  if not row:return await ctx.send('❌ No encuentro esa sugerencia.')
  self.b.db.execute('UPDATE suggestions SET status=? WHERE message_id=?',(estado,message_id))
  try:
   cfg=self.b.db.execute('SELECT suggest_ch FROM guild_config WHERE guild_id=?',(ctx.guild.id,)).fetchone()
   sch=ctx.guild.get_channel(cfg[0]) if cfg and cfg[0] else None
   if sch:
    m=await sch.fetch_message(message_id)
    await m.edit(embed=discord.Embed(title=f'💡 SUGERENCIA • {estado.upper()}',description=row[0],colour=0x7C3AED))
  except discord.HTTPException as e:print('SUGGESTION:',repr(e))
  await ctx.send(f'✅ Estado: **{estado}**.')
 @commands.hybrid_command(description='Dado')
 async def dado(self,ctx):await ctx.send(f'🎲 **{random.randint(1,6)}**')
 @commands.hybrid_command(name='8ball',description='Bola del Vacío')
 async def eight(self,ctx,*,pregunta):await ctx.send('🎱 '+random.choice(['Sí.','No.','Probablemente.','Pregunta luego.','Definitivamente.']))
async def setup(b):await b.add_cog(Social(b))
