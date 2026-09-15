import time,discord
from discord.ext import commands
class Competitive(commands.Cog):
    def __init__(self,b):self.b=b
    @commands.hybrid_command(description="Crea tu clan")
    async def clan_crear(self,ctx,nombre:str):
        if len(nombre)>24:return await ctx.send("Nombre máximo: 24 caracteres.")
        if self.b.db.execute("SELECT 1 FROM clan_members WHERE guild_id=? AND user_id=?",(ctx.guild.id,ctx.author.id)).fetchone():return await ctx.send("Ya perteneces a un clan.")
        try:self.b.db.execute("INSERT INTO clans VALUES(?,?,?,?)",(ctx.guild.id,nombre,ctx.author.id,time.time()))
        except Exception:return await ctx.send("Ese nombre de clan ya existe.")
        self.b.db.execute("INSERT INTO clan_members VALUES(?,?,?,?)",(ctx.guild.id,nombre,ctx.author.id,time.time()));await ctx.send(f"🛡️ Clan **{nombre}** creado.")
    @commands.hybrid_command(description="Únete a un clan")
    async def clan_unir(self,ctx,nombre:str):
        if not self.b.db.execute("SELECT 1 FROM clans WHERE guild_id=? AND name=?",(ctx.guild.id,nombre)).fetchone():return await ctx.send("No existe ese clan.")
        if self.b.db.execute("SELECT 1 FROM clan_members WHERE guild_id=? AND user_id=?",(ctx.guild.id,ctx.author.id)).fetchone():return await ctx.send("Primero sal de tu clan actual.")
        self.b.db.execute("INSERT INTO clan_members VALUES(?,?,?,?)",(ctx.guild.id,nombre,ctx.author.id,time.time()));await ctx.send(f"✅ Te uniste a **{nombre}**.")
    @commands.hybrid_command(description="Sal de tu clan")
    async def clan_salir(self,ctx):
        row=self.b.db.execute("SELECT clan FROM clan_members WHERE guild_id=? AND user_id=?",(ctx.guild.id,ctx.author.id)).fetchone()
        if not row:return await ctx.send("No estás en un clan.")
        own=self.b.db.execute("SELECT owner_id FROM clans WHERE guild_id=? AND name=?",(ctx.guild.id,row[0])).fetchone()
        if own and own[0]==ctx.author.id:return await ctx.send("Eres el dueño. Transfiere/disuelve administrativamente antes de salir.")
        self.b.db.execute("DELETE FROM clan_members WHERE guild_id=? AND user_id=?",(ctx.guild.id,ctx.author.id));await ctx.send("👋 Saliste del clan.")
    @commands.hybrid_command(description="Información de un clan")
    async def clan_info(self,ctx,nombre:str):
        row=self.b.db.execute("SELECT owner_id FROM clans WHERE guild_id=? AND name=?",(ctx.guild.id,nombre)).fetchone()
        if not row:return await ctx.send("Clan no encontrado.")
        n=self.b.db.execute("SELECT COUNT(*) FROM clan_members WHERE guild_id=? AND clan=?",(ctx.guild.id,nombre)).fetchone()[0]
        await ctx.send(f"🛡️ **{nombre}** • Dueño <@{row[0]}> • **{n}** miembros.")
    @commands.hybrid_command(description="Publica búsqueda de grupo")
    async def lfg(self,ctx,juego:str,*,descripcion:str="Busco equipo"):
        self.b.db.execute("INSERT INTO lfg(guild_id,user_id,game,description,created) VALUES(?,?,?,?,?)",(ctx.guild.id,ctx.author.id,juego,descripcion,time.time()))
        await ctx.send(f"🎮 **LFG • {juego}**\n{ctx.author.mention}: {descripcion}")
    @commands.hybrid_command(description="Lista búsquedas de grupo activas")
    async def lfg_lista(self,ctx):
        rows=self.b.db.execute("SELECT user_id,game,description FROM lfg WHERE guild_id=? AND active=1 ORDER BY id DESC LIMIT 10",(ctx.guild.id,)).fetchall()
        await ctx.send("\n".join(f"• <@{u}> **{g}** — {d}" for u,g,d in rows) or "No hay LFG activos.")
    @commands.hybrid_command(description="Crea torneo (solo propietario)")
    async def torneo_crear(self,ctx,nombre:str,fecha:str):
        if ctx.author.id!=ctx.guild.owner_id:return await ctx.send("🔒 Solo el propietario.")
        self.b.db.execute("INSERT INTO tournaments(guild_id,name,event_at,created_by,created) VALUES(?,?,?,?,?)",(ctx.guild.id,nombre,fecha,ctx.author.id,time.time()))
        await ctx.send(f"🏆 Torneo **{nombre}** creado para **{fecha}**.")
    @commands.hybrid_command(description="Lista torneos")
    async def torneos(self,ctx):
        rows=self.b.db.execute("SELECT id,name,event_at,status FROM tournaments WHERE guild_id=? ORDER BY id DESC LIMIT 10",(ctx.guild.id,)).fetchall()
        await ctx.send("\n".join(f"`#{i}` **{n}** • {f} • {s}" for i,n,f,s in rows) or "No hay torneos.")
    @commands.hybrid_command(description="Publica resultado de torneo (solo propietario)")
    async def torneo_resultado(self,ctx,torneo_id:int,*,resultado:str):
        if ctx.author.id!=ctx.guild.owner_id:return await ctx.send("🔒 Solo el propietario.")
        row=self.b.db.execute("SELECT name FROM tournaments WHERE guild_id=? AND id=?",(ctx.guild.id,torneo_id)).fetchone()
        if not row:return await ctx.send("Torneo no encontrado.")
        self.b.db.execute("UPDATE tournaments SET status='closed' WHERE id=?",(torneo_id,));await ctx.send(f"🏆 **{row[0]} — Resultado**\n{resultado}")
    @commands.hybrid_command(description="Crea un evento del calendario (solo propietario)")
    async def evento_crear(self,ctx,nombre:str,fecha:str,*,descripcion:str=""):
        if ctx.author.id!=ctx.guild.owner_id:return await ctx.send("🔒 Solo el propietario.")
        self.b.db.execute("INSERT INTO community_events(guild_id,name,event_at,description,created_by,created) VALUES(?,?,?,?,?,?)",(ctx.guild.id,nombre,fecha,descripcion,ctx.author.id,time.time()))
        ch=discord.utils.get(ctx.guild.text_channels,name="eventos")
        text=f"📅 **{nombre}** • **{fecha}**\n{descripcion}"
        if ch and ch.id!=ctx.channel.id:await ch.send(text)
        await ctx.send("✅ Evento añadido al calendario." if ch and ch.id!=ctx.channel.id else text)
    @commands.hybrid_command(description="Lista próximos eventos")
    async def eventos_lista(self,ctx):
        rows=self.b.db.execute("SELECT id,name,event_at,description FROM community_events WHERE guild_id=? ORDER BY id DESC LIMIT 10",(ctx.guild.id,)).fetchall()
        await ctx.send("\n".join(f"`#{i}` 📅 **{n}** • {f} — {d}" for i,n,f,d in rows) or "No hay eventos registrados.")

async def setup(b):await b.add_cog(Competitive(b))
