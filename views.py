import asyncio
import discord,time

class TermsView(discord.ui.View):
    def __init__(self,bot): super().__init__(timeout=None); self.bot=bot
    @discord.ui.button(label="Aceptar términos y continuar",style=discord.ButtonStyle.success,emoji="✅",custom_id="eco:terms:accept")
    async def accept_terms(self,i,b):
        g=i.guild
        self.bot.db.execute("INSERT OR REPLACE INTO terms_acceptance(guild_id,user_id,accepted) VALUES(?,?,?)",(g.id,i.user.id,time.time()))
        pending=discord.utils.get(g.roles,name="⏳ Pendiente")
        gamer=discord.utils.get(g.roles,name="🎮 Gamer")
        if gamer and gamer in i.user.roles:
            return await i.response.send_message("✅ Ya tienes acceso.",ephemeral=True)
        if pending and pending not in i.user.roles:
            try: await i.user.add_roles(pending,reason="Aceptó términos")
            except discord.Forbidden:
                return await i.response.send_message("❌ El bot no puede asignar ⏳ Pendiente. Revisa jerarquía.",ephemeral=True)
        await i.response.send_message("✅ Términos aceptados. Ahora pulsa **Solicitar acceso**.",ephemeral=True)

class AccessRequestView(discord.ui.View):
    def __init__(self,bot): super().__init__(timeout=None); self.bot=bot
    @discord.ui.button(label="Solicitar acceso",style=discord.ButtonStyle.success,emoji="👻",custom_id="eco:access")
    async def request(self,i,b):
        g=i.guild
        gamer=discord.utils.get(g.roles,name="🎮 Gamer")
        if gamer and gamer in i.user.roles:
            return await i.response.send_message("✅ Ya tienes acceso.",ephemeral=True)
        accepted=self.bot.db.execute("SELECT accepted FROM terms_acceptance WHERE guild_id=? AND user_id=?",(g.id,i.user.id)).fetchone()
        if not accepted:
            return await i.response.send_message("📜 Primero acepta los términos y condiciones.",ephemeral=True)
        row=self.bot.db.execute("SELECT status,message_id FROM access_requests WHERE guild_id=? AND user_id=?",(g.id,i.user.id)).fetchone()
        # La base de datos es la autoridad: un usuario ya aprobado no puede volver a solicitar
        # acceso aunque su rol Gamer haya sido retirado manualmente por accidente.
        if row and row[0]=="approved":
            return await i.response.send_message("✅ Ya tienes acceso a **El Eco del Vacío**.",ephemeral=True)
        if row and row[0]=="pending" and not row[1]:
            return await i.response.send_message("⏳ Ya tienes una solicitud pendiente.",ephemeral=True)
        cfg=self.bot.db.execute("SELECT requests_ch FROM guild_config WHERE guild_id=?",(g.id,)).fetchone()
        ch=g.get_channel(cfg[0]) if cfg else None
        if not ch:return await i.response.send_message("⚠️ No encuentro el canal de revisión.",ephemeral=True)
        # Reconcile stale pending record if its Discord message was deleted.
        if row and row[0]=="pending" and row[1]:
            try:
                await ch.fetch_message(row[1])
                return await i.response.send_message("⏳ Ya tienes una solicitud pendiente.",ephemeral=True)
            except discord.NotFound:
                self.bot.db.execute("DELETE FROM access_requests WHERE guild_id=? AND user_id=?",(g.id,i.user.id))
            except (discord.Forbidden,discord.HTTPException):
                return await i.response.send_message("⏳ Tu solicitud sigue pendiente.",ephemeral=True)
        e=discord.Embed(title="🛂 SOLICITUD DE ACCESO",description=f"{i.user.mention}\nID `{i.user.id}`\nCuenta: <t:{int(i.user.created_at.timestamp())}:R>",colour=0xF59E0B)
        msg=await ch.send(embed=e,view=DecisionView(self.bot,i.user.id))
        self.bot.db.execute("INSERT OR REPLACE INTO access_requests VALUES(?,?,?,?,?,?,?)",(g.id,i.user.id,"pending",msg.id,time.time(),0,0))
        await i.response.send_message("📨 Solicitud enviada al propietario.",ephemeral=True)

class DecisionView(discord.ui.View):
    def __init__(self,bot,uid,persistent=True):
        super().__init__(timeout=None if persistent else 86400); self.bot=bot; self.uid=int(uid)
        self.yes.custom_id=f"eco:access:approve:{self.uid}"; self.no.custom_id=f"eco:access:reject:{self.uid}"
    async def interaction_check(self,i):
        ok=i.user.id==i.guild.owner_id
        if not ok: await i.response.send_message("🔒 Solo el propietario del servidor puede decidir accesos.",ephemeral=True)
        return ok
    async def decide(self,i,status):
        row=self.bot.db.execute("SELECT status FROM access_requests WHERE guild_id=? AND user_id=?",(i.guild.id,self.uid)).fetchone()
        if not row or row[0]!="pending": return await i.response.send_message("Esta solicitud ya fue resuelta.",ephemeral=True)
        m=i.guild.get_member(self.uid)
        if not m:
            return await i.response.send_message("⚠️ Ese usuario ya no está en el servidor. La solicitud queda pendiente para no aprobar a alguien ausente.",ephemeral=True)
        if status=="approved":
            p=discord.utils.get(i.guild.roles,name="⏳ Pendiente"); gamer=discord.utils.get(i.guild.roles,name="🎮 Gamer")
            try:
                if p: await m.remove_roles(p,reason="Acceso aprobado")
                if gamer: await m.add_roles(gamer,reason="Acceso aprobado")
            except discord.Forbidden:
                return await i.response.send_message("❌ El rol del bot debe estar por encima de Gamer/Pendiente.",ephemeral=True)
        self.bot.db.execute("UPDATE access_requests SET status=?,decided_by=?,decided=? WHERE guild_id=? AND user_id=?",(status,i.user.id,time.time(),i.guild.id,self.uid))
        cfg=self.bot.db.execute("SELECT audit_ch FROM guild_config WHERE guild_id=?",(i.guild.id,)).fetchone()
        audit=i.guild.get_channel(cfg[0]) if cfg and cfg[0] else None
        if audit:
            try: await audit.send(f"{'✅ APROBADO' if status=='approved' else '❌ RECHAZADO'} • {m.mention} • por {i.user.mention}")
            except discord.HTTPException as e: print("AUDIT:",repr(e))
        await i.response.send_message("✅ Decisión registrada.",ephemeral=True)
        try: await i.message.delete()
        except discord.HTTPException as e: print("ACCESS DELETE:",repr(e))
        if status=="rejected":
            try: await m.kick(reason="Acceso rechazado por propietario")
            except discord.Forbidden as e: print("ACCESS KICK:",repr(e))
    @discord.ui.button(label="ACEPTAR",style=discord.ButtonStyle.success,emoji="✅",custom_id="eco:access:approve")
    async def yes(self,i,b): await self.decide(i,"approved")
    @discord.ui.button(label="RECHAZAR",style=discord.ButtonStyle.danger,emoji="❌",custom_id="eco:access:reject")
    async def no(self,i,b): await self.decide(i,"rejected")

class TicketView(discord.ui.View):
    def __init__(self,bot): super().__init__(timeout=None); self.bot=bot
    async def make(self,i,kind):
        g=i.guild
        old=self.bot.db.execute("SELECT channel_id FROM tickets WHERE guild_id=? AND user_id=? AND closed=0 ORDER BY created DESC LIMIT 1",(g.id,i.user.id)).fetchone()
        if old:
            ch=g.get_channel(old[0])
            if ch:return await i.response.send_message(f"Ya tienes {ch.mention}.",ephemeral=True)
            self.bot.db.execute("UPDATE tickets SET closed=? WHERE channel_id=?",(time.time(),old[0]))
        cat=discord.utils.get(g.categories,name="🆘 SOPORTE")
        guard=discord.utils.get(g.roles,name="⚔️ Guardián"); admin=discord.utils.get(g.roles,name="🛡️ Administrador"); founder=discord.utils.get(g.roles,name="👑 Fundador")
        ow={g.default_role:discord.PermissionOverwrite(view_channel=False),i.user:discord.PermissionOverwrite(view_channel=True,send_messages=True)}
        for role in (guard,admin,founder):
            if role:ow[role]=discord.PermissionOverwrite(view_channel=True,send_messages=True)
        ch=await g.create_text_channel(f"{kind}-{i.user.id}",category=cat,overwrites=ow,reason=f"Ticket {kind}")
        self.bot.db.execute("INSERT OR REPLACE INTO tickets(guild_id,user_id,channel_id,created,type) VALUES(?,?,?,?,?)",(g.id,i.user.id,ch.id,time.time(),kind))
        await ch.send(f"🎫 {i.user.mention}, describe tu caso de **{kind}**.",view=TicketCloseView(self.bot))
        await i.response.send_message(f"✅ {ch.mention}",ephemeral=True)
    @discord.ui.button(label="Soporte",style=discord.ButtonStyle.primary,emoji="🎫",custom_id="eco:ticket:support")
    async def support(self,i,b):await self.make(i,"soporte")
    @discord.ui.button(label="Reporte",style=discord.ButtonStyle.secondary,emoji="🛡️",custom_id="eco:ticket:report")
    async def report(self,i,b):await self.make(i,"reporte")
    @discord.ui.button(label="Apelación",style=discord.ButtonStyle.secondary,emoji="⚖️",custom_id="eco:ticket:appeal")
    async def appeal(self,i,b):await self.make(i,"apelacion")

class TicketCloseView(discord.ui.View):
    def __init__(self,bot):super().__init__(timeout=None);self.bot=bot
    @discord.ui.button(label="Cerrar ticket",style=discord.ButtonStyle.danger,emoji="🔒",custom_id="eco:ticket:close")
    async def close(self,i,b):
        from cogs.tickets import close_ticket
        row=self.bot.db.execute("SELECT user_id FROM tickets WHERE channel_id=? AND guild_id=?",(i.channel.id,i.guild.id)).fetchone()
        if not row:return await i.response.send_message("⚠️ No es un ticket registrado.",ephemeral=True)
        if not (i.user.id in {i.guild.owner_id,row[0]} or i.user.guild_permissions.manage_messages):
            return await i.response.send_message("🔒 Sin permiso.",ephemeral=True)
        await i.response.send_message("🔒 Cerrando y guardando registro...",ephemeral=True)
        ok,msg=await close_ticket(self.bot,i.channel,i.user,"Cerrado desde el botón")
        if not ok:
            try:await i.followup.send(msg,ephemeral=True)
            except discord.HTTPException as e:print("TICKET FOLLOWUP:",repr(e))

class RenameModal(discord.ui.Modal,title="Renombrar sala"):
    name=discord.ui.TextInput(label="Nuevo nombre",min_length=2,max_length=40)
    def __init__(self,bot):super().__init__();self.bot=bot
    async def on_submit(self,i):
        ch=owned_room(self.bot,i)
        if not ch:return await i.response.send_message("Solo puedes controlar tu sala.",ephemeral=True)
        await ch.edit(name=str(self.name));await i.response.send_message("✏️ Sala renombrada.",ephemeral=True)

class VoiceMemberSelect(discord.ui.Select):
    def __init__(self,bot,action,channel,members):
        self.bot=bot;self.action=action;self.channel_id=channel.id
        labels={"permit":"Selecciona a quien permitir","kick":"Selecciona a quien expulsar","transfer":"Selecciona al nuevo propietario"}
        options=[discord.SelectOption(label=m.display_name[:100],value=str(m.id),description=str(m)[:100]) for m in members[:25]]
        super().__init__(placeholder=labels[action],min_values=1,max_values=1,options=options)
    async def callback(self,i):
        ch=owned_room(self.bot,i)
        if not ch or ch.id!=self.channel_id:return await i.response.send_message("Solo puedes controlar tu sala.",ephemeral=True)
        m=i.guild.get_member(int(self.values[0]))
        if not m:return await i.response.send_message("⚠️ Ese usuario ya no está disponible.",ephemeral=True)
        if m.bot:return await i.response.send_message("⚠️ Selecciona una persona, no un bot.",ephemeral=True)
        if m.id==i.user.id:return await i.response.send_message("⚠️ No puedes realizar esa acción sobre ti mismo.",ephemeral=True)
        if self.action=="permit":
            try:await ch.set_permissions(m,connect=True,view_channel=True)
            except (discord.Forbidden,discord.HTTPException):return await i.response.send_message("❌ Discord no permitió cambiar los permisos de ese usuario.",ephemeral=True)
            msg=f"✅ {m.mention} puede entrar."
        elif self.action=="kick":
            if not (m.voice and m.voice.channel==ch):return await i.response.send_message("⚠️ Ese usuario ya no está dentro de tu sala.",ephemeral=True)
            try:
                await ch.set_permissions(m,connect=False)
                await m.move_to(None,reason=f"Expulsado de sala privada por {i.user}")
            except (discord.Forbidden,discord.HTTPException):return await i.response.send_message("❌ Discord no permitió expulsar a ese usuario.",ephemeral=True)
            msg=f"🚪 {m.mention} fue expulsado y no puede volver a entrar hasta que lo permitas."
        else:
            if not (m.voice and m.voice.channel==ch):return await i.response.send_message("⚠️ El nuevo propietario debe estar dentro de la sala.",ephemeral=True)
            self.bot.db.execute("UPDATE temp_voice SET owner_id=? WHERE channel_id=?",(m.id,ch.id))
            msg=f"👑 Propiedad transferida a {m.mention}."
        await i.response.edit_message(content=msg,view=None)

class VoiceMemberActionView(discord.ui.View):
    def __init__(self,bot,action,channel,members):
        super().__init__(timeout=120);self.add_item(VoiceMemberSelect(bot,action,channel,members))


def owned_room(bot,i):
    ch=i.user.voice.channel if i.user.voice else None
    if not ch:return None
    row=bot.db.execute("SELECT owner_id FROM temp_voice WHERE guild_id=? AND channel_id=?",(i.guild.id,ch.id)).fetchone()
    return ch if row and row[0]==i.user.id else None

class VoiceControlView(discord.ui.View):
    def __init__(self,bot):super().__init__(timeout=None);self.bot=bot
    @discord.ui.button(label="Bloquear",style=discord.ButtonStyle.danger,emoji="🔒",custom_id="eco:vlock")
    async def lock(self,i,b):
        ch=owned_room(self.bot,i)
        if not ch:return await i.response.send_message("Solo puedes controlar tu sala.",ephemeral=True)
        await ch.set_permissions(i.guild.default_role,connect=False);await i.response.send_message("🔒 Sala bloqueada.",ephemeral=True)
    @discord.ui.button(label="Desbloquear",style=discord.ButtonStyle.success,emoji="🔓",custom_id="eco:vopen")
    async def open(self,i,b):
        ch=owned_room(self.bot,i)
        if not ch:return await i.response.send_message("Solo puedes controlar tu sala.",ephemeral=True)
        await ch.set_permissions(i.guild.default_role,connect=True);await i.response.send_message("🔓 Sala abierta.",ephemeral=True)
    @discord.ui.button(label="Renombrar",style=discord.ButtonStyle.secondary,emoji="✏️",custom_id="eco:vrename")
    async def rename(self,i,b):await i.response.send_modal(RenameModal(self.bot))
    @discord.ui.button(label="Permitir",style=discord.ButtonStyle.secondary,emoji="➕",custom_id="eco:vpermit")
    async def permit(self,i,b):
        ch=owned_room(self.bot,i)
        if not ch:return await i.response.send_message("Solo puedes controlar tu sala.",ephemeral=True)
        members=[]
        for m in i.guild.members:
            if m.bot or m.id==i.user.id:continue
            ow=ch.overwrites_for(m)
            if ow.connect is False:members.append(m)
        if not members:return await i.response.send_message("ℹ️ No hay usuarios bloqueados para permitir.",ephemeral=True)
        await i.response.send_message("➕ Selecciona el usuario que podrá entrar:",view=VoiceMemberActionView(self.bot,"permit",ch,members),ephemeral=True)
    @discord.ui.button(label="Expulsar",style=discord.ButtonStyle.secondary,emoji="🚪",custom_id="eco:vkick")
    async def kick(self,i,b):
        ch=owned_room(self.bot,i)
        if not ch:return await i.response.send_message("Solo puedes controlar tu sala.",ephemeral=True)
        members=[m for m in ch.members if not m.bot and m.id!=i.user.id]
        if not members:return await i.response.send_message("ℹ️ No hay otra persona dentro de tu sala para expulsar.",ephemeral=True)
        await i.response.send_message("🚪 Selecciona a la persona que quieres expulsar:",view=VoiceMemberActionView(self.bot,"kick",ch,members),ephemeral=True)
    @discord.ui.button(label="Transferir",style=discord.ButtonStyle.secondary,emoji="👑",custom_id="eco:vtransfer")
    async def transfer(self,i,b):
        ch=owned_room(self.bot,i)
        if not ch:return await i.response.send_message("Solo puedes controlar tu sala.",ephemeral=True)
        members=[m for m in ch.members if not m.bot and m.id!=i.user.id]
        if not members:return await i.response.send_message("ℹ️ No hay otra persona dentro de tu sala para transferirla.",ephemeral=True)
        await i.response.send_message("👑 Selecciona al nuevo propietario:",view=VoiceMemberActionView(self.bot,"transfer",ch,members),ephemeral=True)
    @discord.ui.button(label="Eliminar sala",style=discord.ButtonStyle.danger,emoji="🗑️",custom_id="eco:vdelete")
    async def delete_room(self,i,b):
        ch=owned_room(self.bot,i)
        if not ch:return await i.response.send_message("Solo puedes eliminar tu sala.",ephemeral=True)
        await i.response.defer(ephemeral=True)
        try:
            await ch.delete(reason=f"Sala temporal eliminada por {i.user}")
        except discord.NotFound:
            pass
        except (discord.Forbidden,discord.HTTPException) as e:
            print("VOICE MANUAL DELETE:",repr(e))
            return await i.followup.send("❌ Discord no permitió eliminar la sala.",ephemeral=True)
        self.bot.db.execute("DELETE FROM temp_voice WHERE channel_id=?",(ch.id,))
        await i.followup.send("🗑️ Sala eliminada.",ephemeral=True)
    @discord.ui.select(placeholder="Límite 1–10",options=[discord.SelectOption(label=str(x),value=str(x)) for x in range(1,11)],custom_id="eco:vlimit")
    async def limit(self,i,s):
        ch=owned_room(self.bot,i)
        if not ch:return await i.response.send_message("Solo puedes controlar tu sala.",ephemeral=True)
        await ch.edit(user_limit=int(s.values[0]));await i.response.send_message(f"👥 Límite: {s.values[0]}.",ephemeral=True)


class OwnerPanel(discord.ui.View):
    def __init__(self,owner):
        # El panel se crea con !panel y permanece activo mientras el bot siga encendido.
        # No se registra como vista persistente global: conserva el diseño original.
        super().__init__(timeout=None)
        self.owner=int(owner)
        # Estado local del panel. Cada !panel mantiene su propia selección.
        self.member_id=None
        self.role_id=None

    async def on_error(self, interaction, error, item):
        # Si Discord.py rechaza una interacción, deja el error visible en Wispbyte.
        print(f"OWNER PANEL ERROR | item={type(item).__name__} | error={error!r}")
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(
                    "❌ Ocurrió un error en el panel. Revisa la consola de Fantasmita.",
                    ephemeral=True
                )
            except discord.HTTPException:
                pass

    async def interaction_check(self,i):
        if i.user.id!=self.owner:
            await i.response.send_message("🔒 Solo el propietario.",ephemeral=True,delete_after=4)
            return False
        return True

    def resolve(self,i):
        member=i.guild.get_member(self.member_id) if self.member_id else None
        role=i.guild.get_role(self.role_id) if self.role_id else None
        return member,role

    def clear(self,i):
        self.member_id=None
        self.role_id=None

    def role_allowed(self,i,role):
        """El fundador puede gestionar roles propios y personalizados seguros bajo Fantasmita."""
        if not role or role==i.guild.default_role:return False
        if role.name in PROTECTED_OWNER_ROLES:return False
        if role.managed:return False
        me=i.guild.me
        if not me or role>=me.top_role:return False
        return True

    def make_embed(self,i,status=None):
        member,role=self.resolve(i)
        who=member.mention if member else "—"
        role_text=role.mention if role else "—"
        text=f"👤 **Usuario:** {who}\n🎭 **Rol:** {role_text}"
        if role:
            text+=f"\n👥 **Miembros con este rol:** {len(role.members)}"
        text+="\n\nPuedes usar los roles de Fantasmita o roles personalizados que estén debajo del bot."
        if status:text+=f"\n\n{status}"
        return discord.Embed(title="👑 PANEL DE ROLES",description=text,colour=0x8B5CF6)

    async def refresh(self,i,status=None,autoclear=False):
        try:
            await i.response.edit_message(embed=self.make_embed(i,status),view=self)
        except discord.InteractionResponded:
            await i.edit_original_response(embed=self.make_embed(i,status),view=self)
        if autoclear and status:
            msg=i.message
            async def clear_status():
                await asyncio.sleep(4)
                try:await msg.edit(embed=self.make_embed(i),view=self)
                except (discord.NotFound,discord.Forbidden,discord.HTTPException):pass
            asyncio.create_task(clear_status())

    @discord.ui.select(cls=discord.ui.UserSelect,placeholder="Seleccionar usuario",row=0)
    async def us(self,i,s):
        self.member_id=s.values[0].id
        await self.refresh(i)

    @discord.ui.select(cls=discord.ui.RoleSelect,placeholder="Seleccionar rol",row=1)
    async def ro(self,i,s):
        self.role_id=s.values[0].id
        await self.refresh(i)

    @discord.ui.button(label="DAR",style=discord.ButtonStyle.success,row=2)
    async def add(self,i,b):
        member,role=self.resolve(i)
        if not member or not self.role_allowed(i,role):
            return await self.refresh(i,"⚠️ Selecciona usuario y un rol administrable. Fundador/Pendiente y roles por encima del bot están protegidos.")
        if role in member.roles:
            self.clear(i)
            return await self.refresh(i,f"ℹ️ **{member.display_name}** ya tiene **{role.name}**.",autoclear=True)
        try:
            await member.add_roles(role,reason=f"Panel Fundador: {i.user}")
            # Verificación contra Discord: no informa éxito si el rol no quedó realmente aplicado.
            fresh=await i.guild.fetch_member(member.id)
            if role.id not in {r.id for r in fresh.roles}:
                return await self.refresh(i,"❌ Discord no confirmó la asignación del rol.")
            count=sum(1 for m in i.guild.members if role in m.roles)
            self.clear(i)
            await self.refresh(i,f"✅ **{role.name}** asignado a **{member.display_name}**. Miembros con el rol: **{count}**.",autoclear=True)
        except discord.Forbidden:
            await self.refresh(i,"❌ Fantasmita debe estar por encima de ese rol y tener Administrar roles.")
        except discord.HTTPException as e:
            print("OWNER ROLE ADD:",repr(e));await self.refresh(i,"❌ Discord no permitió asignar el rol.")

    @discord.ui.button(label="QUITAR",style=discord.ButtonStyle.danger,row=2)
    async def rem(self,i,b):
        member,role=self.resolve(i)
        if not member or not self.role_allowed(i,role):
            return await self.refresh(i,"⚠️ Selecciona usuario y un rol administrable. Fundador/Pendiente y roles por encima del bot están protegidos.")
        if role not in member.roles:
            self.clear(i)
            return await self.refresh(i,f"ℹ️ **{member.display_name}** no tiene **{role.name}**.",autoclear=True)
        try:
            await member.remove_roles(role,reason=f"Panel Fundador: {i.user}")
            fresh=await i.guild.fetch_member(member.id)
            if role.id in {r.id for r in fresh.roles}:
                return await self.refresh(i,"❌ Discord todavía muestra el rol en el usuario; no se confirmó la eliminación.")
            # member.remove_roles actualiza la caché; el conteo se calcula de nuevo, nunca se guarda.
            count=sum(1 for m in i.guild.members if role in m.roles)
            self.clear(i)
            await self.refresh(i,f"🗑️ **{role.name}** retirado de **{member.display_name}**. Miembros con el rol: **{count}**.",autoclear=True)
        except discord.Forbidden:
            await self.refresh(i,"❌ Fantasmita debe estar por encima de ese rol y tener Administrar roles.")
        except discord.HTTPException as e:
            print("OWNER ROLE REMOVE:",repr(e));await self.refresh(i,"❌ Discord no permitió retirar el rol.")

