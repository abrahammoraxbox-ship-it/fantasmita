import discord
from discord.ext import commands
VALID={"twitch":"https://twitch.tv/{}","youtube":"https://youtube.com/@{}","facebook":"https://facebook.com/{}"}
class Integrations(commands.Cog):
    def __init__(self,b):self.b=b
    @commands.hybrid_command(description="Vincula un perfil público Twitch/YouTube/Facebook")
    async def vincular(self,ctx,plataforma:str,usuario:str):
        p=plataforma.lower()
        if p not in VALID:return await ctx.send("Usa: `twitch`, `youtube` o `facebook`.")
        clean=usuario.strip().lstrip("@").replace("/","")
        self.b.db.execute("INSERT OR REPLACE INTO social_links VALUES(?,?,?,?)",(ctx.guild.id,ctx.author.id,p,clean))
        await ctx.send(f"🔗 {p.title()} guardado: {VALID[p].format(clean)}")
    @commands.hybrid_command(description="Muestra tus perfiles públicos vinculados")
    async def vinculos(self,ctx):
        rows=self.b.db.execute("SELECT platform,handle FROM social_links WHERE guild_id=? AND user_id=?",(ctx.guild.id,ctx.author.id)).fetchall()
        await ctx.send("\n".join(f"• **{p.title()}**: {VALID[p].format(h)}" for p,h in rows) or "No tienes perfiles vinculados.")
async def setup(b):await b.add_cog(Integrations(b))
