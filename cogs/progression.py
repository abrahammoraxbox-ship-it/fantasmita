import datetime,time,discord
from discord.ext import commands

ACH=[("primeros_pasos",10,"🌱 Primeros pasos"),("activo",100,"🔥 Activo"),("veterano",500,"🌙 Veterano")]

class Progression(commands.Cog):
    def __init__(self,b):self.b=b;self.last={}

    async def sync_auto_roles(self,member,message_count):
        """Roles automáticos de progreso. No toca VIP/Creador/Campeón/Staff: esos siguen siendo reconocimientos manuales."""
        targets=[]
        if message_count>=100:
            r=discord.utils.get(member.guild.roles,name="🏆 Élite")
            if r:targets.append(r)
        if message_count>=500:
            r=discord.utils.get(member.guild.roles,name="🌙 Veterano")
            if r:targets.append(r)
        missing=[r for r in targets if r not in member.roles]
        if missing:
            try:await member.add_roles(*missing,reason="Progresión automática Eco")
            except discord.Forbidden as e:print("AUTO ROLE:",repr(e))
            except discord.HTTPException as e:print("AUTO ROLE HTTP:",repr(e))
    @commands.Cog.listener()
    async def on_message(self,m):
        if m.author.bot or not m.guild or m.content.startswith("!"):return
        gamer=discord.utils.get(m.guild.roles,name="🎮 Gamer")
        if not gamer or gamer not in m.author.roles:return
        norm=" ".join(m.content.lower().split());key=(m.guild.id,m.author.id)
        old=self.last.get(key)
        if len(norm)<8 or (old and (old[0]==norm or time.time()-old[1]<10)):return
        self.last[key]=(norm,time.time())
        week=f"{datetime.date.today().isocalendar().year}-W{datetime.date.today().isocalendar().week:02}"
        self.b.db.execute("INSERT OR IGNORE INTO weekly_missions(guild_id,user_id,week) VALUES(?,?,?)",(m.guild.id,m.author.id,week))
        self.b.db.execute("UPDATE weekly_missions SET progress=MIN(target,progress+1) WHERE guild_id=? AND user_id=? AND week=?",(m.guild.id,m.author.id,week))
        self.b.db.ensure_user(m.guild.id,m.author.id)
        count=self.b.db.execute("SELECT messages FROM users WHERE guild_id=? AND user_id=?",(m.guild.id,m.author.id)).fetchone()[0]
        for code,target,name in ACH:
            if count>=target:self.b.db.execute("INSERT OR IGNORE INTO achievements VALUES(?,?,?,?)",(m.guild.id,m.author.id,code,time.time()))
        await self.sync_auto_roles(m.author,count)
    @commands.hybrid_command(description="Misión semanal")
    async def semanal(self,ctx):
        iso=datetime.date.today().isocalendar();week=f"{iso.year}-W{iso.week:02}"
        self.b.db.execute("INSERT OR IGNORE INTO weekly_missions(guild_id,user_id,week) VALUES(?,?,?)",(ctx.guild.id,ctx.author.id,week))
        p,t,c=self.b.db.execute("SELECT progress,target,claimed FROM weekly_missions WHERE guild_id=? AND user_id=? AND week=?",(ctx.guild.id,ctx.author.id,week)).fetchone()
        if p>=t and not c:
            self.b.db.execute("UPDATE weekly_missions SET claimed=1 WHERE guild_id=? AND user_id=? AND week=?",(ctx.guild.id,ctx.author.id,week))
            self.b.db.ensure_user(ctx.guild.id,ctx.author.id);self.b.db.execute("UPDATE users SET xp=xp+250,coins=coins+500 WHERE guild_id=? AND user_id=?",(ctx.guild.id,ctx.author.id))
            return await ctx.send("🏆 Semanal completada: **+250 XP +500 Void Coins**.")
        await ctx.send(f"📅 Misión semanal: **{p}/{t}** mensajes válidos."+(" ✅ Reclamada." if c else ""))
    @commands.hybrid_command(description="Tus logros y medallas")
    async def logros(self,ctx):
        rows=self.b.db.execute("SELECT code FROM achievements WHERE guild_id=? AND user_id=?",(ctx.guild.id,ctx.author.id)).fetchall();codes={r[0] for r in rows}
        lines=[f"{'✅' if c in codes else '⬛'} {name} — {target} mensajes" for c,target,name in ACH]
        await ctx.send(embed=discord.Embed(title="🏅 LOGROS",description="\n".join(lines),colour=0xFBBF24))
    @commands.hybrid_command(description="Temporada actual")
    async def temporada(self,ctx):
        row=self.b.db.execute("SELECT name,start,end FROM seasons WHERE guild_id=?",(ctx.guild.id,)).fetchone()
        if not row:
            now=time.time();end=now+90*86400;self.b.db.execute("INSERT INTO seasons VALUES(?,?,?,?)",(ctx.guild.id,"Temporada del Vacío I",now,end));row=("Temporada del Vacío I",now,end)
        top=self.b.db.execute("SELECT user_id,xp FROM users WHERE guild_id=? ORDER BY xp DESC LIMIT 5",(ctx.guild.id,)).fetchall()
        text="\n".join(f"{n}. <@{u}> — {xp} XP" for n,(u,xp) in enumerate(top,1)) or "Sin clasificación todavía."
        await ctx.send(embed=discord.Embed(title=f"🌌 {row[0]}",description=text,colour=0x7C3AED))
async def setup(b):await b.add_cog(Progression(b))
