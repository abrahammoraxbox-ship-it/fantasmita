import os,discord
from discord.ext import commands
from views import OwnerPanel,TermsView,AccessRequestView
from core import ensure_panel
class Owner(commands.Cog):
    def __init__(self,b):
        self.b=b
        self.active_panels={}
    def own(self,c):return c.guild and c.author.id==c.guild.owner_id
    @commands.command()
    async def panel(self,ctx):
        if not self.own(ctx):
            return await ctx.send("🔒 Solo el propietario.",delete_after=5)
        try:
            await ctx.message.delete()
        except (discord.Forbidden,discord.HTTPException):
            pass
        key=(ctx.guild.id,ctx.author.id)
        old=self.active_panels.get(key)
        if old:
            try:
                await old.delete()
            except (discord.NotFound,discord.Forbidden,discord.HTTPException):
                pass
        msg=await ctx.send(
            embed=discord.Embed(
                title="👑 PANEL DE ROLES",
                description="👤 **Usuario:** —\n🎭 **Rol:** —\n\nSelecciona usuario y rol.",
                colour=0x8B5CF6),
            view=OwnerPanel(ctx.author.id),
            delete_after=300)
        self.active_panels[key]=msg
    @commands.command()
    async def reglas(self,ctx,*,texto=None):
        if not self.own(ctx):return
        if texto is None:return await ctx.send(self.b.db.execute("SELECT rules FROM guild_config WHERE guild_id=?",(ctx.guild.id,)).fetchone()[0])
        self.b.db.execute("UPDATE guild_config SET rules=? WHERE guild_id=?",(texto,ctx.guild.id))
        cfg=self.b.db.execute("SELECT access_ch FROM guild_config WHERE guild_id=?",(ctx.guild.id,)).fetchone();ch=ctx.guild.get_channel(cfg[0]) if cfg else None
        if ch:
            await ensure_panel(self.b,ch,"TERMS",discord.Embed(title="📜 TÉRMINOS Y CONDICIONES",description=texto+"\n\nPulsa **Aceptar términos y continuar**.",colour=0x8B5CF6),TermsView(self.b))
            await ensure_panel(self.b,ch,"ACCESS",discord.Embed(title="👻 SOLICITAR ACCESO",description="Acepta los términos y después solicita acceso.",colour=0x7C3AED),AccessRequestView(self.b))
        await ctx.send("✅ Reglas y términos actualizados.")
    @commands.command()
    async def seguridad(self,ctx,nivel:int):
        if not self.own(ctx):return
        nivel=max(0,min(3,nivel));self.b.db.execute("UPDATE guild_config SET security_level=? WHERE guild_id=?",(nivel,ctx.guild.id));await ctx.send(f"🛡️ Seguridad nivel {nivel}.")
    @commands.command()
    async def backup(self,ctx):
        if not self.own(ctx):return
        p=self.b.db.backup(os.path.join(os.path.dirname(os.path.dirname(__file__)),"backups"));await ctx.send(f"💾 Backup creado: `{os.path.basename(p)}`")
    @commands.command()
    async def panico(self,ctx,estado:str):
        if not self.own(ctx):return await ctx.send("🔒 Solo el propietario.")
        on=estado.lower() in {"on","activar","1","si","sí"}
        gamer=discord.utils.get(ctx.guild.roles,name="🎮 Gamer")
        protected={"bienvenida-y-acceso","solicitudes-acceso","logs","panel-fundador","auditoria-fundador"}
        changed=0
        for ch in ctx.guild.text_channels:
            if ch.name in protected:continue
            try:
                if gamer:await ch.set_permissions(gamer,send_messages=False if on else None)
                changed+=1
            except (discord.Forbidden,discord.HTTPException) as e:print("PANIC:",ch.id,repr(e))
        await ctx.send(f"{'🚨 MODO PÁNICO ACTIVADO' if on else '✅ Modo pánico desactivado'} • {changed} canales procesados.")
    @commands.command()
    async def instalarbranding(self,ctx):
        if not self.own(ctx):return await ctx.send("🔒 Solo el propietario.")
        if discord.utils.get(ctx.guild.emojis,name="fantasmita"):return await ctx.send("👻 El emoji `fantasmita` ya existe.")
        path=os.path.join(os.path.dirname(os.path.dirname(__file__)),"assets","fantasmita.gif")
        try:
            data=open(path,"rb").read();e=await ctx.guild.create_custom_emoji(name="fantasmita",image=data,reason="Branding El Eco del Vacío")
            await ctx.send(f"👻 Branding instalado: {e}")
        except (discord.Forbidden,discord.HTTPException,OSError) as e:
            print("BRANDING:",repr(e));await ctx.send("❌ No pude instalar el emoji. Revisa permisos/espacios de emojis.")

async def setup(b):await b.add_cog(Owner(b))
