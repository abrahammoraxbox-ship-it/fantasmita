import time,collections,discord
from discord.ext import commands
class Security(commands.Cog):
    def __init__(self,b):self.b=b;self.msgs=collections.defaultdict(list);self.last={};self.joins=collections.defaultdict(list)
    @commands.Cog.listener()
    async def on_member_join(self,m):
        now=time.time();arr=[x for x in self.joins[m.guild.id] if now-x<15]+[now];self.joins[m.guild.id]=arr
        if len(arr)>=8:
            self.b.db.execute("UPDATE guild_config SET security_level=3 WHERE guild_id=?",(m.guild.id,))
            cfg=self.b.db.execute("SELECT logs_ch FROM guild_config WHERE guild_id=?",(m.guild.id,)).fetchone();ch=m.guild.get_channel(cfg[0]) if cfg else None
            if ch:
                try:await ch.send("🚨 **ANTI-RAID:** 8+ entradas en 15 s. Seguridad elevada automáticamente a nivel 3.")
                except discord.HTTPException as e:print("ANTIRAID LOG:",repr(e))
            self.joins[m.guild.id]=[]
    @commands.Cog.listener()
    async def on_message(self,m):
        if m.author.bot or not m.guild or m.author.guild_permissions.manage_messages:return
        row=self.b.db.execute("SELECT security_level FROM guild_config WHERE guild_id=?",(m.guild.id,)).fetchone();level=row[0] if row else 2
        if level==0:return
        now=time.time();k=(m.guild.id,m.author.id);self.msgs[k]=[x for x in self.msgs[k] if now-x<8]+[now]
        threshold={1:10,2:7,3:5}[level];norm=" ".join(m.content.lower().split())
        repeated=self.last.get(k)==norm and len(norm)>5;self.last[k]=norm
        mass=m.content.count("<@")>={1:8,2:6,3:4}[level]
        suspicious=any(x in norm for x in ["discord.gift/","free nitro","steamcommunity-gift"]) if level>=2 else False
        if len(self.msgs[k])>=threshold or repeated or mass or suspicious:
            try:await m.delete();await m.channel.send(f"🛡️ {m.author.mention}, actividad bloqueada por seguridad.",delete_after=5)
            except (discord.Forbidden,discord.HTTPException) as e:print("SECURITY:",repr(e))
            self.msgs[k].clear()
async def setup(b):await b.add_cog(Security(b))
