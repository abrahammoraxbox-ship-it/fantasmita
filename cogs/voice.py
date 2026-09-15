import time,discord
from discord.ext import commands

class Voice(commands.Cog):
    def __init__(self,b):self.b=b
    @commands.Cog.listener()
    async def on_ready(self):
        for gid,chid,owner in self.b.db.execute("SELECT guild_id,channel_id,owner_id FROM temp_voice").fetchall():
            g=self.b.get_guild(gid); ch=g.get_channel(chid) if g else None
            if not ch or not ch.members:
                if ch:
                    try:await ch.delete(reason="Limpieza de sala temporal vacía")
                    except (discord.Forbidden,discord.HTTPException) as e:print("VOICE START CLEAN:",repr(e))
                self.b.db.execute("DELETE FROM temp_voice WHERE channel_id=?",(chid,))
    @commands.Cog.listener()
    async def on_voice_state_update(self,m,before,after):
        if m.bot:return
        g=m.guild
        cfg=self.b.db.execute("SELECT voice_lobby,voice_panel_ch FROM guild_config WHERE guild_id=?",(g.id,)).fetchone()
        if not cfg:return
        lobby_id,panel_id=cfg
        if after.channel and after.channel.id==lobby_id:
            row=self.b.db.execute("SELECT channel_id FROM temp_voice WHERE guild_id=? AND owner_id=?",(g.id,m.id)).fetchone()
            if row:
                old=g.get_channel(row[0])
                if old:
                    try:await m.move_to(old);await self.notice(m,old,panel_id,True);return
                    except (discord.Forbidden,discord.HTTPException) as e:print("VOICE MOVE:",repr(e))
                self.b.db.execute("DELETE FROM temp_voice WHERE guild_id=? AND owner_id=?",(g.id,m.id))
            try:
                ch=await after.channel.category.create_voice_channel(f"🎮 Sala de {m.display_name}",user_limit=5,reason=f"Sala privada de {m}")
                self.b.db.execute("INSERT OR REPLACE INTO temp_voice VALUES(?,?,?,?)",(g.id,ch.id,m.id,time.time()))
                await m.move_to(ch);await self.notice(m,ch,panel_id,False)
            except (discord.Forbidden,discord.HTTPException) as e:print("VOICE CREATE:",repr(e))
        if before.channel and before.channel.id!=lobby_id:
            row=self.b.db.execute("SELECT owner_id FROM temp_voice WHERE guild_id=? AND channel_id=?",(g.id,before.channel.id)).fetchone()
            if row:
                members=[x for x in before.channel.members if not x.bot]
                if not members:
                    try:await before.channel.delete(reason="Sala temporal vacía")
                    except (discord.NotFound,discord.Forbidden,discord.HTTPException) as e:print("VOICE DELETE:",repr(e))
                    self.b.db.execute("DELETE FROM temp_voice WHERE channel_id=?",(before.channel.id,))
                elif row[0]==m.id:
                    # Owner left while people remain: hand room to first remaining member.
                    new_owner=members[0]
                    self.b.db.execute("UPDATE temp_voice SET owner_id=? WHERE channel_id=?",(new_owner.id,before.channel.id))
                    panel=g.get_channel(panel_id)
                    if panel:
                        try:await panel.send(f"👑 {new_owner.mention} ahora controla **{before.channel.name}** porque el propietario salió.",delete_after=45)
                        except discord.HTTPException as e:print("VOICE TRANSFER NOTICE:",repr(e))
    async def notice(self,m,ch,panel_id,existing):
        panel=m.guild.get_channel(panel_id)
        if panel:
            try:await panel.send(f"{m.mention} • {'♻️ Volviste a' if existing else '🎧 Se creó'} **{ch.name}**. Usa el panel para bloquear, renombrar, permitir/expulsar, transferir y cambiar límite.",delete_after=45)
            except discord.HTTPException as e:print("VOICE NOTICE:",repr(e))
async def setup(b):await b.add_cog(Voice(b))
