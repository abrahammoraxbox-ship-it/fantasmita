import time,random
from discord.ext import commands
class Economy(commands.Cog):
 def __init__(self,b):self.b=b
 @commands.hybrid_command(description="Tus Void Coins")
 async def saldo(self,ctx):
  _,c,*_=self.b.db.stats(ctx.guild.id,ctx.author.id);await ctx.send(f"🪙 **{c} Void Coins**")
 @commands.hybrid_command(description="Premio diario")
 async def daily(self,ctx):
  xp,c,msg,last,streak,rep,lx,lastrep=self.b.db.stats(ctx.guild.id,ctx.author.id);now=time.time()
  if now-last<86400:
   left=max(0,int(86400-(now-last)));return await ctx.send(f"⏳ Vuelve en **{left//3600}h {(left%3600)//60}m**.")
  new_streak=(streak+1) if last and (now-last)<172800 else 1
  reward=random.randint(150,350)+min(new_streak,7)*10
  self.b.db.execute("UPDATE users SET coins=coins+?,last_daily=?,streak=? WHERE guild_id=? AND user_id=?",(reward,now,new_streak,ctx.guild.id,ctx.author.id))
  await ctx.send(f"🎁 Recibiste **{reward} Void Coins**. 🔥 Racha: **{new_streak}**.")
 @commands.hybrid_command(description="Apuesta cara/cruz")
 async def coinflip(self,ctx,cantidad:int):
  _,c,*_=self.b.db.stats(ctx.guild.id,ctx.author.id)
  if cantidad<=0 or cantidad>c:return await ctx.send("❌ Cantidad inválida.")
  win=random.choice([False,True]);delta=cantidad if win else -cantidad
  self.b.db.execute("UPDATE users SET coins=coins+? WHERE guild_id=? AND user_id=?",(delta,ctx.guild.id,ctx.author.id))
  await ctx.send(("🔥 Ganaste " if win else "💀 Perdiste ")+f"**{cantidad}**.")
 @commands.hybrid_command(description="Tienda del Vacío")
 async def tienda(self,ctx):
  rows=self.b.db.execute("SELECT item,price,description FROM shop ORDER BY price").fetchall()
  await ctx.send("🛒 **TIENDA DEL VACÍO**\n"+"\n".join(f"• **{i}** — 🪙{p} — {d}" for i,p,d in rows))
 @commands.hybrid_command(description="Compra un objeto de la tienda")
 async def comprar(self,ctx,*,objeto:str):
  row=self.b.db.execute("SELECT item,price FROM shop WHERE lower(item)=lower(?)",(objeto,)).fetchone()
  if not row:return await ctx.send("❌ No encuentro ese objeto. Usa `/tienda`.")
  item,price=row;_,coins,*_=self.b.db.stats(ctx.guild.id,ctx.author.id)
  if coins<price:return await ctx.send("❌ No tienes suficientes Void Coins.")
  self.b.db.execute("UPDATE users SET coins=coins-? WHERE guild_id=? AND user_id=?",(price,ctx.guild.id,ctx.author.id))
  self.b.db.execute("""INSERT INTO inventory(guild_id,user_id,item,qty) VALUES(?,?,?,1)
  ON CONFLICT(guild_id,user_id,item) DO UPDATE SET qty=qty+1""",(ctx.guild.id,ctx.author.id,item))
  await ctx.send(f"✅ Compraste **{item}** por 🪙{price}.")
 @commands.hybrid_command(description="Muestra tu inventario")
 async def inventario(self,ctx):
  rows=self.b.db.execute("SELECT item,qty FROM inventory WHERE guild_id=? AND user_id=? ORDER BY item",(ctx.guild.id,ctx.author.id)).fetchall()
  await ctx.send("🎒 **INVENTARIO**\n"+("\n".join(f"• {i} ×{q}" for i,q in rows) if rows else "Vacío."))
async def setup(b):await b.add_cog(Economy(b))
